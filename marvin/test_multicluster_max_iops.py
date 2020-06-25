# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

# Import Local Modules
import pprint
import random
import subprocess
import time
import json

from marvin.cloudstackAPI import (listOsTypes,
                                  listTemplates,
                                  listHosts,
                                  createTemplate,
                                  createVolume,
                                  resizeVolume,
                                  revertSnapshot,
                                  startVirtualMachine,
                                  deployVirtualMachine,
                                  destroyVirtualMachine,
                                  )
from marvin.cloudstackTestCase import cloudstackTestCase
from marvin.codes import FAILED, KVM, PASS, XEN_SERVER, RUNNING
from marvin.configGenerator import configuration, cluster
from marvin.lib.base import (Account,
                             Configurations,
                             ServiceOffering,
                             Snapshot,
                             StoragePool,
                             Template,
                             Tag,
                             VirtualMachine,
                             VmSnapshot,
                             Volume,
                             DiskOffering,
                             )
from marvin.lib.common import (get_zone,
                               get_domain,
                               get_template,
                               list_disk_offering,
                               list_snapshots,
                               list_storage_pools,
                               list_volumes,
                               list_virtual_machines,
                               list_configurations,
                               list_service_offering,
                               list_clusters,
                               list_accounts,
                               )
from marvin.lib.utils import random_gen, cleanup_resources, validateList, is_snapshot_on_nfs, isAlmostEqual
from nose.plugins.attrib import attr

from storpool import spapi
import uuid
from logs_and_commands import (TestData, HelperUtil, cfg,)

class TestResizeVolumes(cloudstackTestCase):
    vm = ""
    vm2 = ""
    data_disk_1 = ""
    data_disk_2 = ""

    @classmethod
    def setUpClass(cls):
        cls.spapi = spapi.Api.fromConfig(multiCluster=True)
        testClient = super(TestResizeVolumes, cls).getClsTestClient()
        cls.apiclient = testClient.getApiClient()
        cls.helper = HelperUtil(cls)
        cls.unsupportedHypervisor = False
        cls.hypervisor = testClient.getHypervisorInfo()
        if cls.hypervisor.lower() in ("hyperv", "lxc"):
            cls.unsupportedHypervisor = True
            return

        cls.services = testClient.getParsedTestDataConfig()
        # Get Zone, Domain and templates
        cls.domain = get_domain(cls.apiclient)
        cls.zone = get_zone(cls.apiclient, testClient.getZoneForTests())

        storpool_primary_storage = {
            "name" : "ssd",
            "zoneid": cls.zone.id,
            "url": "ssd",
            "scope": "zone",
            "capacitybytes": 15546641111121,
            "hypervisor": "kvm",
            "provider": "StorPool",
            "tags": "ssd"
            }

        storpool_service_offerings = {
            "name": "iops",
            "displaytext": "Testing IOPS on StorPool",
            "cpunumber": 1,
            "cpuspeed": 500,
            "memory": 512,
            "storagetype": "shared",
            "customizediops": True,
            "tags": "ssd",
            }

        storpool_disk_offerings = {
            "name": "iops",
            "displaytext": "Testing IOPS on StorPool",
            "customizediops": True,
            "storagetype": "shared",
            "tags" : "ssd",
            }

        storage_pool = list_storage_pools(
            cls.apiclient,
            name='ssd'
            )

        service_offerings = list_service_offering(
            cls.apiclient,
            name='iops'
            )

        disk_offerings = list_disk_offering(
            cls.apiclient,
            name="iops"
            )

        if disk_offerings is None:
            disk_offerings = DiskOffering.create(cls.apiclient, storpool_disk_offerings, custom = True)
        else:
            disk_offerings = disk_offerings[0]
        cls.disk_offerings = disk_offerings
        if storage_pool is None:
            storage_pool = StoragePool.create(cls.apiclient, storpool_primary_storage)
        else:
            storage_pool = storage_pool[0]
        cls.storage_pool = storage_pool
        cls.debug(pprint.pformat(storage_pool))
        if service_offerings is None:
            service_offerings = ServiceOffering.create(cls.apiclient, storpool_service_offerings)
        else:
            service_offerings = service_offerings[0]

        template = get_template(
             cls.apiclient,
            cls.zone.id,
            account = "system"
        )

        cls.debug(pprint.pformat(template))
        cls.debug(pprint.pformat(cls.hypervisor))

        if template == FAILED:
            assert False, "get_template() failed to return template\
                    with description %s" % cls.services["ostype"]

        cls.services["domainid"] = cls.domain.id
        cls.services["small"]["zoneid"] = cls.zone.id
        cls.services["templates"]["ostypeid"] = template.ostypeid
        cls.services["zoneid"] = cls.zone.id


        cls.service_offering = service_offerings
        cls.debug(pprint.pformat(cls.service_offering))

        cls.local_cluster = cls.get_local_cluster()
        cls.host = cls.list_hosts_by_cluster_id(cls.local_cluster.id)

        assert len(cls.host) > 1, "Hosts list is less than 1"
        cls.host_on_local_1 = cls.host[0]
        cls.host_on_local_2 = cls.host[1]

        cls.remote_cluster = cls.get_remote_cluster()
        cls.host_remote = cls.list_hosts_by_cluster_id(cls.remote_cluster.id)
        assert len(cls.host_remote) > 1, "Hosts list is less than 1"

        cls.host_on_remote1 = cls.host_remote[0]
        cls.host_on_remote2 = cls.host_remote[1]

        cls.volume_1 = cls.create_custom_disk(
            cls.apiclient,
            {"diskname":"StorPoolDisk" },
            zoneid=cls.zone.id,
            size = 5,
            miniops = 2000,
            maxiops = 5000,
            diskofferingid=cls.disk_offerings.id,
        )
        cls.volume_2 = cls.create_custom_disk(
            cls.apiclient,
            {"diskname":"StorPoolDisk" },
            zoneid=cls.zone.id,
            size = 5,
            miniops = 2000,
            maxiops = 5000,
            diskofferingid=cls.disk_offerings.id,
        )
        cls.volume = cls.create_custom_disk(
            cls.apiclient,
            {"diskname":"StorPoolDisk" },
            zoneid=cls.zone.id,
            size = 5,
            miniops = 2000,
            maxiops = 5000,
            diskofferingid=cls.disk_offerings.id,
        )
        cls.virtual_machine = cls.create_vm_custom(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            minIops = 1000,
            maxIops = 5000,
            rootdisksize = 10
        )
        cls.virtual_machine2= cls.create_vm_custom(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            minIops = 1000,
            maxIops = 5000,
            rootdisksize = 10
        )

        cls.virtual_machine_live_migration_1 = cls.create_vm_custom(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            minIops = 1000,
            maxIops = 5000,
            hostid = cls.host_on_local_1.id,
            rootdisksize = 10
        )
        cls.virtual_machine_live_migration_2= cls.create_vm_custom(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            minIops = 1000,
            maxIops = 5000,
            hostid = cls.host_on_remote1.id,
            rootdisksize = 10
        )

        cls.template = template
        cls.random_data_0 = random_gen(size=100)
        cls.test_dir = "/tmp"
        cls.random_data = "random.data"
        cls._cleanup = []
        cls._cleanup.append(cls.virtual_machine)
        cls._cleanup.append(cls.virtual_machine2)
        cls._cleanup.append(cls.volume_1)
        cls._cleanup.append(cls.volume_2)
        cls._cleanup.append(cls.volume)
        return

    @classmethod
    def tearDownClass(cls):
        try:
            # Cleanup resources used
            cleanup_resources(cls.apiclient, cls._cleanup)
        except Exception as e:
            raise Exception("Warning: Exception during cleanup : %s" % e)
        return

    def setUp(self):
        self.apiclient = self.testClient.getApiClient()
        self.dbclient = self.testClient.getDbConnection()

        if self.unsupportedHypervisor:
            self.skipTest("Skipping test because unsupported hypervisor\
                    %s" % self.hypervisor)
        return

    def tearDown(self):
        return

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_01_resize_iops_attached_volume(self):
        ''' Test resize iops of attached StorPool's disk
        '''
        volume_attached = self.virtual_machine.attach_volume(
            self.apiclient,
            self.volume_1
            )

        volumes = list_volumes(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            )

        for v in volumes:
            self.check_storpool_volume_iops(v)

        self.volume_1 = Volume.resize(self.volume_1, self.apiclient, maxiops = 4000)
        self.check_storpool_volume_iops(self.volume_1)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_02_resize_iops_detached_volume(self):
        ''' Test resize iops of detached StorPool's disk
        '''
        self.virtual_machine.stop(self.apiclient, forced=True)
        self.virtual_machine.detach_volume(
            self.apiclient,
            self.volume_1
            )
        self.volume_1 = Volume.resize(self.volume_1, self.apiclient, maxiops = 10000)
        self.check_storpool_volume_iops(self.volume_1)
       
    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_03_resize_iops_root_volume(self):
        ''' Test resize iops of ROOT StorPool's disk
        '''
        
        vol = Volume.list(
                self.apiclient,
                virtualmachineid=
                self.virtual_machine.id,
                type='ROOT',
            )
        vol = self.resize_volume(apiclient = self.apiclient, volume = vol[0], shrinkOk = False, maxiops = 15000)
        self.check_storpool_volume_iops(vol)
    
    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_04_iops_root_volume_reverted(self):
        ''' Test resize iops of ROOT StorPool's disk after revert
        '''
        vol = Volume.list(
                self.apiclient,
                virtualmachineid=
                self.virtual_machine.id,
                type='ROOT',
            )
        self.check_storpool_volume_iops(vol[0])

        snapshot = Snapshot.create(self.apiclient, vol[0].id,)
        reverted_snapshot1 = Volume.revertToSnapshot(self.apiclient, volumeSnapshotId = snapshot.id)
        vol = Volume.list(
                self.apiclient,
                virtualmachineid=
                self.virtual_machine.id,
                type='ROOT',
            )
        self.check_storpool_volume_iops(vol[0])

### test live migration with max iops

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_05_migrate_live(self):
        """
        Migrate VMs/Volumes live
        """
        global vm
        destinationHost = self.getDestinationHost(self.virtual_machine_live_migration_1.hostid, self.host)
        # Migrate the VM
        vm = self.migrateVm(self.virtual_machine_live_migration_1, destinationHost)
        # self.check_files(vm,destinationHost)


        """
        Migrate the VM and ROOT volume
        """
        # Get all volumes to be migrated

        destinationHost,  vol_list = self.get_destination_pools_hosts(vm)
        for v in vol_list:
            self.check_storpool_volume_iops(v)

        vm = self.migrateVm(self.virtual_machine_live_migration_1, destinationHost)

        destinationHost,  vol_list = self.get_destination_pools_hosts(vm)
        for v in vol_list:
            self.check_storpool_volume_iops(v)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_06_migrate_vm_live_attach_disk(self):
        """
        Add a data disk and migrate vm, data disk and root disk
        """
        
        global vm
        global data_disk_1
        data_disk_1 = self.create_custom_disk(
            self.apiclient,
            {"diskname":"StorPoolDisk" },
            zoneid=self.zone.id,
            size = 5,
            miniops = 2000,
            maxiops = 5000,
            diskofferingid=self.disk_offerings.id,
        )

        self.debug("Created volume with ID: %s" % data_disk_1.id)

        self.virtual_machine_live_migration_1.attach_volume(
            self.apiclient,
            data_disk_1
        )

        destinationHost,  vol_list = self.get_destination_pools_hosts(vm)
        for v in vol_list:
            self.check_storpool_volume_iops(v)
        vm = self.migrateVm(self.virtual_machine_live_migration_1, destinationHost)


        self.virtual_machine_live_migration_1.attach_volume(
            self.apiclient,
            self.volume
        )

        destinationHost,  vol_list = self.get_destination_pools_hosts(vm)
        for v in vol_list:
            self.check_storpool_volume_iops(v)
        vm = self.migrateVm(self.virtual_machine_live_migration_1, destinationHost)

        destinationHost,  vol_list = self.get_destination_pools_hosts(vm)
        for v in vol_list:
            self.check_storpool_volume_iops(v)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_07_migrate_vm_live_with_snapshots(self):
        """
        Create snapshots on all the volumes, Migrate all the volumes and VM.
        """
        global vm
        # Get ROOT Volume
        vol_for_snap = list_volumes(
            self.apiclient,
            virtualmachineid=vm.id,
            listall=True)
        for vol in vol_for_snap:
            snapshot = Snapshot.create(
                self.apiclient,
                volume_id=vol.id
            )
            snapshot.validateState(
                self.apiclient,
                snapshotstate="backedup",
            )
        # Migrate all volumes and VMs

        destinationHost,  vol_list = self.get_destination_pools_hosts(vm)
        for v in vol_list:
            self.check_storpool_volume_iops(v)
        vm = self.migrateVm(self.virtual_machine_live_migration_1, destinationHost)

        destinationHost,  vol_list = self.get_destination_pools_hosts(vm)
        for v in vol_list:
            self.check_storpool_volume_iops(v)


    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_08_migrate_vm_live_resize_volume(self):
        """
        Resize the data volume , Migrate all the volumes and VM.
        """
        global vm
        global data_disk_1

        vol = self.resize_volume(apiclient = self.apiclient, volume = data_disk_1, shrinkOk = False, maxiops = 15000)
        # Migrate all volumes and VMs
        destinationHost,  vol_list = self.get_destination_pools_hosts(vm)
        for v in vol_list:
            self.check_storpool_volume_iops(v)
        vm = self.migrateVm(self.virtual_machine_live_migration_1, destinationHost)

        destinationHost,  vol_list = self.get_destination_pools_hosts(vm)
        for v in vol_list:
            self.check_storpool_volume_iops(v)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_09_migrate_vm_live_restore(self):
        """
        Restore the VM , Migrate all the volumes and VM.
        """
        global vm
        self.virtual_machine_live_migration_1.restore(self.apiclient)
        self.virtual_machine_live_migration_1.getState(
            self.apiclient,
            "Running"
        )
        # Migrate the VM and its volumes

        destinationHost,  vol_list = self.get_destination_pools_hosts(vm)
        for v in vol_list:
            self.check_storpool_volume_iops(v)
        vm = self.migrateVm(self.virtual_machine_live_migration_1, destinationHost)

        destinationHost,  vol_list = self.get_destination_pools_hosts(vm)
        for v in vol_list:
            self.check_storpool_volume_iops(v)

        cmd = destroyVirtualMachine.destroyVirtualMachineCmd()
        cmd.id = self.virtual_machine_live_migration_1.id
        cmd.expunge = True
        self.apiclient.destroyVirtualMachine(cmd)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_10_migrate_live_remote(self):
        """
        Migrate VMs/Volumes live
        """
        global vm2
        destinationHost = self.getDestinationHost(self.virtual_machine_live_migration_2.hostid, self.host_remote)
        # Migrate the VM
        vm2 = self.migrateVm(self.virtual_machine_live_migration_2, destinationHost)
        # self.check_files(vm,destinationHost)


        """
        Migrate the VM and ROOT volume
        """
        # Get all volumes to be migrated

        destinationHost,  vol_list = self.get_destination_pools_hosts(vm2)
        for v in vol_list:
            self.check_storpool_volume_iops(v)
        vm2 = self.migrateVm(self.virtual_machine_live_migration_2, destinationHost)

        destinationHost,  vol_list = self.get_destination_pools_hosts(vm2)
        for v in vol_list:
            self.check_storpool_volume_iops(v)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_11_migrate_vm_live_attach_disk_on_remote(self):
        """
        Add a data disk and migrate vm, data disk and root disk
        """
        
        global vm2
        global data_disk_2
        data_disk_2 = self.create_custom_disk(
            self.apiclient,
            {"diskname":"StorPoolDisk" },
            zoneid=self.zone.id,
            size = 5,
            miniops = 2000,
            maxiops = 5000,
            diskofferingid=self.disk_offerings.id,
        )

        self.debug("Created volume with ID: %s" % data_disk_2.id)

        self.virtual_machine_live_migration_2.attach_volume(
            self.apiclient,
            data_disk_2
        )

        destinationHost,  vol_list = self.get_destination_pools_hosts(vm2)
        for v in vol_list:
            self.check_storpool_volume_iops(v)
        vm2 = self.migrateVm(self.virtual_machine_live_migration_2, destinationHost)


        self.virtual_machine_live_migration_2.attach_volume(
            self.apiclient,
            self.volume_2
        )

        destinationHost,  vol_list = self.get_destination_pools_hosts(vm2)
        for v in vol_list:
            self.check_storpool_volume_iops(v)
        vm2 = self.migrateVm(self.virtual_machine_live_migration_2, destinationHost)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_12_migrate_vm_live_with_snapshots_on_remote(self):
        """
        Create snapshots on all the volumes, Migrate all the volumes and VM.
        """
        global vm2
        # Get ROOT Volume
        vol_for_snap = list_volumes(
            self.apiclient,
            virtualmachineid=vm2.id,
            listall=True)
        for vol in vol_for_snap:
            snapshot = Snapshot.create(
                self.apiclient,
                volume_id=vol.id
            )
            snapshot.validateState(
                self.apiclient,
                snapshotstate="backedup",
            )
        # Migrate all volumes and VMs

        destinationHost,  vol_list = self.get_destination_pools_hosts(vm2)
        for v in vol_list:
            self.check_storpool_volume_iops(v)
        vm2 = self.migrateVm(self.virtual_machine_live_migration_2, destinationHost)
        destinationHost,  vol_list = self.get_destination_pools_hosts(vm2)
        for v in vol_list:
            self.check_storpool_volume_iops(v)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_13_migrate_vm_live_resize_volume_on_remote(self):
        """
        Resize the data volume , Migrate all the volumes and VM.
        """
        global vm2
        global data_disk_2

        vol = self.resize_volume(apiclient = self.apiclient, volume = data_disk_1, shrinkOk = False, maxiops = 15000)

        # Migrate all volumes and VMs
        destinationHost,  vol_list = self.get_destination_pools_hosts(vm2)
        for v in vol_list:
            self.check_storpool_volume_iops(v)
        vm2 = self.migrateVm(self.virtual_machine_live_migration_2, destinationHost)
        destinationHost,  vol_list = self.get_destination_pools_hosts(vm2)
        for v in vol_list:
            self.check_storpool_volume_iops(v)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_14_migrate_vm_live_restore_on_remote(self):
        """
        Restore the VM , Migrate all the volumes and VM.
        """
        global vm2
        self.virtual_machine_live_migration_2.restore(self.apiclient)
        self.virtual_machine_live_migration_2.getState(
            self.apiclient,
            "Running"
        )
        # Migrate the VM and its volumes

        destinationHost,  vol_list = self.get_destination_pools_hosts(vm2)
        for v in vol_list:
            self.check_storpool_volume_iops(v)
        vm2 = self.migrateVm(self.virtual_machine_live_migration_2, destinationHost)

        destinationHost,  vol_list = self.get_destination_pools_hosts(vm2)
        for v in vol_list:
            self.check_storpool_volume_iops(v)

        cmd = destroyVirtualMachine.destroyVirtualMachineCmd()
        cmd.id = self.virtual_machine_live_migration_2.id
        cmd.expunge = True
        self.apiclient.destroyVirtualMachine(cmd)

    @classmethod
    def get_local_cluster(cls):
       storpool_clusterid = subprocess.check_output(['storpool_confshow', 'CLUSTER_ID'])
       clusterid = storpool_clusterid.split("=")
       cls.debug(storpool_clusterid)
       clusters = list_clusters(cls.apiclient)
       for c in clusters:
           configuration = list_configurations(
               cls.apiclient,
               clusterid = c.id
               )
           for conf in configuration:
               if conf.name == 'sp.cluster.id'  and (conf.value in clusterid[1]):
                   return c

    @classmethod
    def get_remote_cluster(cls):
       storpool_clusterid = subprocess.check_output(['storpool_confshow', 'CLUSTER_ID'])
       clusterid = storpool_clusterid.split("=")
       cls.debug(storpool_clusterid)
       clusters = list_clusters(cls.apiclient)
       for c in clusters:
           configuration = list_configurations(
               cls.apiclient,
               clusterid = c.id
               )
           for conf in configuration:
               if conf.name == 'sp.cluster.id'  and (conf.value not in clusterid[1]):
                   return c

    @classmethod
    def list_hosts_by_cluster_id(cls, clusterid):
        """List all Hosts matching criteria"""
        cmd = listHosts.listHostsCmd()
        cmd.clusterid = clusterid  
        return(cls.apiclient.listHosts(cmd))
    
    @classmethod
    def migrateVmWithVolumes(self, vm, destinationHost, volumes, pool):
        """
            This method is used to migrate a vm and its volumes using migrate virtual machine with volume API
            INPUTS:
                   1. vm -> virtual machine object
                   2. destinationHost -> the host to which VM will be migrated
                   3. volumes -> list of volumes which are to be migrated
                   4. pools -> list of destination pools
        """
        vol_pool_map = {vol.id: pool.id for vol in volumes}
    
        cmd = migrateVirtualMachineWithVolume.migrateVirtualMachineWithVolumeCmd()
        cmd.hostid = destinationHost.id
        cmd.migrateto = []
        cmd.virtualmachineid = self.virtual_machine.id
        for volume, pool1 in vol_pool_map.items():
            cmd.migrateto.append({
                'volume': volume,
                'pool': pool1
        })
        self.apiclient.migrateVirtualMachineWithVolume(cmd)

        vm.getState(
            self.apiclient,
            "Running"
        )
        # check for the VM's host and volume's storage post migration
        migrated_vm_response = list_virtual_machines(self.apiclient, id=vm.id)
        assert isinstance(migrated_vm_response, list), "Check list virtual machines response for valid list"

        assert migrated_vm_response[0].hostid == destinationHost.id, "VM did not migrate to a specified host"
    
        for vol in volumes:
            migrated_volume_response = list_volumes(
                self.apiclient,
                virtualmachineid=migrated_vm_response[0].id,
                name=vol.name,
                listall=True)
            assert isinstance(migrated_volume_response, list), "Check list virtual machines response for valid list"
            assert migrated_volume_response[0].storageid == pool.id, "Volume did not migrate to a specified pool"
    
            assert str(migrated_volume_response[0].state).lower().eq('ready'), "Check migrated volume is in Ready state"
    
            return migrated_vm_response[0]

    @classmethod
    def getDestinationHost(self, hostsToavoid, hosts):
        destinationHost = None
        for host in hosts:
            if host.id not in hostsToavoid:
                destinationHost = host
                break
        return destinationHost

    @classmethod
    def get_destination_pools_hosts(self, vm):
        vol_list = list_volumes(
            self.apiclient,
            virtualmachineid=vm.id,
            listall=True)
            # Get destination host
        destinationHost = self.getDestinationHost(vm.hostid, self.host)
        return destinationHost, vol_list

    @classmethod
    def migrateVm(self, vm, destinationHost):
        """
        This method is to migrate a VM using migrate virtual machine API
        """
    
        vm.migrate(
            self.apiclient,
            hostid=destinationHost.id,
        )
        vm.getState(
            self.apiclient,
            "Running"
        )
        # check for the VM's host and volume's storage post migration
        migrated_vm_response = list_virtual_machines(self.apiclient, id=vm.id)
        assert isinstance(migrated_vm_response, list), "Check list virtual machines response for valid list"

        assert migrated_vm_response[0].hostid ==  destinationHost.id, "VM did not migrate to a specified host"
        return migrated_vm_response[0]

    @classmethod
    def getDestinationPool(self,
                           poolsToavoid,
                           migrateto
                           ):
        """ Get destination pool which has scope same as migrateto
        and which is not in avoid set
        """
    
        destinationPool = None
    
        # Get Storage Pool Id to migrate to
        for storagePool in self.pools:
            if storagePool.scope == migrateto:
                if storagePool.name not in poolsToavoid:
                    destinationPool = storagePool
                    break
    
        return destinationPool

 
    @classmethod
    def check_storpool_volume_size(cls, volume):
        name = volume.path.split("/")[3]
        try:
            spvolume = cls.spapi.volumeList(volumeName = "~" + name)
            if spvolume[0].size != volume.size:
                raise Exception("Storpool volume size is not the same as CloudStack db size")
        except spapi.ApiError as err:
           raise Exception(err)

    @classmethod
    def check_storpool_volume_iops(cls, volume):
        name = volume.path.split("/")[3]
        try:
            spvolume = cls.spapi.volumeList(volumeName = "~" + name)
            cls.debug(spvolume[0].iops)
            cls.debug(volume.maxiops)
            if spvolume[0].iops != volume.maxiops:
                raise Exception("Storpool volume size is not the same as CloudStack db size")
        except spapi.ApiError as err:
           raise Exception(err)

    @classmethod
    def create_custom_disk(cls, apiclient, services, size = None, miniops = None, maxiops =None, diskofferingid=None, zoneid=None):
        """Create Volume from Custom disk offering"""
        cmd = createVolume.createVolumeCmd()
        cmd.name = services["diskname"]

        if diskofferingid:
            cmd.diskofferingid = diskofferingid

        if size:
            cmd.size = size

        if miniops:
            cmd.miniops = miniops

        if maxiops:
            cmd.maxiops = maxiops

        cmd.zoneid = zoneid


        return Volume(apiclient.createVolume(cmd).__dict__)

    @classmethod
    def create_vm_custom(cls, apiclient, services, templateid=None, zoneid=None, 
               serviceofferingid=None, method='GET', hypervisor=None,
               cpuNumber=None, cpuSpeed=None, memory=None, minIops=None,
               maxIops=None, hostid=None, rootdisksize=None,
               ):
        """Create the instance"""

        cmd = deployVirtualMachine.deployVirtualMachineCmd()

        if serviceofferingid:
            cmd.serviceofferingid = serviceofferingid
        elif "serviceoffering" in services:
            cmd.serviceofferingid = services["serviceoffering"]

        if zoneid:
            cmd.zoneid = zoneid
        elif "zoneid" in services:
            cmd.zoneid = services["zoneid"]

        if hypervisor:
            cmd.hypervisor = hypervisor

        if hostid:
            cmd.hostid = hostid

        if "displayname" in services:
            cmd.displayname = services["displayname"]

        if "name" in services:
            cmd.name = services["name"]

        if templateid:
            cmd.templateid = templateid
        elif "template" in services:
            cmd.templateid = services["template"]



        cmd.details = [{}]

        if cpuNumber:
            cmd.details[0]["cpuNumber"] = cpuNumber

        if cpuSpeed:
            cmd.details[0]["cpuSpeed"] = cpuSpeed

        if memory:
            cmd.details[0]["memory"] = memory

        if minIops:
            cmd.details[0]["minIops"] = minIops

        if maxIops:
            cmd.details[0]["maxIops"] = maxIops

        if rootdisksize >= 0:
            cmd.details[0]["rootdisksize"] = rootdisksize

        virtual_machine = apiclient.deployVirtualMachine(cmd, method=method)

        return VirtualMachine(virtual_machine.__dict__, services)

    @classmethod
    def resize_volume(cls, apiclient, volume, shrinkOk=None, disk_offering =None, size=None, maxiops=None, miniops=None):

        cmd = resizeVolume.resizeVolumeCmd()
        cmd.id = volume.id

        if disk_offering:
            cmd.diskofferingid = disk_offering.id
        if size:
            cmd.size = size
        
        if maxiops:
            cmd.maxiops = maxiops
        if miniops:
            cmd.miniops

        cmd.shrinkok = shrinkOk
        apiclient.resizeVolume(cmd)

        new_size = Volume.list(
            apiclient,
            id=volume.id
            )
        volume_size = new_size[0].size
        return new_size[0]
