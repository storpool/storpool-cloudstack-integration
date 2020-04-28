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

from marvin.cloudstackAPI import (listOsTypes,
                                  listTemplates,
                                  listHosts,
                                  createTemplate,
                                  createVolume,
                                  resizeVolume,
                                  startVirtualMachine,
                                  migrateVirtualMachineWithVolume,
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
                             VirtualMachine,
                             VmSnapshot,
                             Volume)
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
                               list_clusters)
from marvin.lib.utils import random_gen, cleanup_resources, validateList, is_snapshot_on_nfs, isAlmostEqual
from nose.plugins.attrib import attr
import uuid

from storpool import spapi
from storpool import sptypes

from logs_and_commands import (TeeStream, TestData, HelperUtil, cfg, TeeTextTestRunner)



class TestRenameObjectsWithUuids(cloudstackTestCase):
    vm = ""
    vm2 = ""
    data_disk_1 = ""
    data_disk_2 = ""
    @classmethod
    def setUpClass(cls):
        super(TestRenameObjectsWithUuids, cls).setUpClass()
        try:
            cls.setUpCloudStack()
        except Exception:
            cls.cleanUpCloudStack()
            raise

    @classmethod
    def setUpCloudStack(cls):
        super(TestRenameObjectsWithUuids, cls).setUpClass()

        cls.spapi = spapi.Api.fromConfig(multiCluster=True)
        cls.helper = HelperUtil(cls)

        cls._cleanup = []
        testClient = super(TestRenameObjectsWithUuids, cls).getClsTestClient()
        cls.apiclient = testClient.getApiClient()
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
            "capacitybytes": 4500000,
            "capacityiops": 155466464221111121,
            "hypervisor": "kvm",
            "provider": "StorPool",
            "tags": "ssd"
            }

        storpool_service_offerings = {
            "name": "ssd",
                "displaytext": "SP_CO_2 (Min IOPS = 10,000; Max IOPS = 15,000)",
                "cpunumber": 1,
                "cpuspeed": 500,
                "memory": 512,
                "storagetype": "shared",
                "customizediops": False,
                "hypervisorsnapshotreserve": 200,
                "tags": "ssd"
            }

        storage_pool = list_storage_pools(
            cls.apiclient,
            name='ssd'
            )

        service_offerings = list_service_offering(
            cls.apiclient,
            name='ssd'
            )

        disk_offerings = list_disk_offering(
            cls.apiclient,
            name="Small"
            )

        disk_offering_20 = list_disk_offering(
            cls.apiclient,
            name="Medium"
            )

        disk_offering_100 = list_disk_offering(
            cls.apiclient,
            name="Large"
            )

        cls.disk_offering = disk_offerings[0]
        cls.disk_offering_20 = disk_offering_20[0]
        cls.disk_offering_100 = disk_offering_100[0]
        cls.debug(pprint.pformat(storage_pool))
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
        #The version of CentOS has to be supported
        template = get_template(
             cls.apiclient,
            cls.zone.id,
            account = "system"
        )

        cls.pools = StoragePool.list(cls.apiclient, zoneid=cls.zone.id)
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

        cls.volume_1 = Volume.create(
            cls.apiclient,
            {"diskname":"StorPoolDisk-1" },
            zoneid=cls.zone.id,
            diskofferingid=cls.disk_offering.id,
        )
        cls._cleanup.append(cls.volume_1)

        cls.volume = Volume.create(
            cls.apiclient,
            {"diskname":"StorPoolDisk-3" },
            zoneid=cls.zone.id,
            diskofferingid=cls.disk_offering.id,
        )
        cls._cleanup.append(cls.volume)

        cls.virtual_machine = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            hostid = cls.host_on_local_1.id,
            rootdisksize=10
        )

        cls.volume_on_remote = Volume.create(
            cls.apiclient,
            {"diskname":"StorPoolDisk-3" },
            zoneid=cls.zone.id,
            diskofferingid=cls.disk_offering.id,
        )
        cls._cleanup.append(cls.volume_on_remote)

        cls.virtual_machine_on_remote = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            hostid = cls.host_on_remote1.id,
            rootdisksize=10
        )

        cls.template = template
        cls.random_data_0 = random_gen(size=100)
        cls.test_dir = "/tmp"
        cls.random_data = "random.data"
        return

    @classmethod
    def tearDownClass(cls):
        cls.cleanUpCloudStack()

    @classmethod
    def cleanUpCloudStack(cls):
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
    def test_01_migrate_live(self):
        """
        Migrate VMs/Volumes live
        """
        global vm
        volumes = list_volumes(self.apiclient, virtualmachineid = self.virtual_machine.id)
        for v in volumes:
            vol = sptypes.VolumeUpdateDesc(rename = v.id)
            name = v.path.split("/")[3]

            rename = self.spapi.volumeUpdate(volumeName = "~" + name, json = vol)

        destinationHost = self.getDestinationHost(self.virtual_machine.hostid, self.host)
        # Migrate the VM
        vm = self.migrateVm(self.virtual_machine, destinationHost)
        # self.check_files(vm,destinationHost)


        """
        Migrate the VM and ROOT volume
        """
        # Get all volumes to be migrated

        destinationHost,  vol_list = self.get_destination_pools_hosts(vm)
        vm = self.migrateVm(self.virtual_machine, destinationHost)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_02_migrate_vm_live_attach_disk(self):
        """
        Add a data disk and migrate vm, data disk and root disk
        """
        
        global vm
        global data_disk_1
        data_disk_1 = Volume.create(
            self.apiclient,
            {"diskname":"StorPoolDisk-4" },
            zoneid=self.zone.id,
            diskofferingid=self.disk_offering.id,
        )

        self.debug("Created volume with ID: %s" % data_disk_1.id)


        self.virtual_machine.attach_volume(
            self.apiclient,
            data_disk_1
        )

        volumes = list_volumes(self.apiclient, id = data_disk_1.id)
        vol = sptypes.VolumeUpdateDesc(rename = volumes[0].id)
        name = volumes[0].path.split("/")[3]

        rename = self.spapi.volumeUpdate(volumeName = "~" + name, json = vol)

        destinationHost, vol_list = self.get_destination_pools_hosts(vm)
        vm = self.migrateVm(self.virtual_machine, destinationHost)


        self.virtual_machine.attach_volume(
            self.apiclient,
            self.volume
        )

        destinationHost, vol_list = self.get_destination_pools_hosts(vm)
        vm = self.migrateVm(self.virtual_machine, destinationHost)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_03_migrate_vm_live_with_snapshots(self):
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
            globalId = self.storpool_snapshot_globalid(snapshot)
            sn = sptypes.SnapshotUpdateDesc(rename = snapshot.id)
            self.debug("Globalid is %s, and snapshot is %s" % (globalId, snapshot))
    
            rename = self.spapi.snapshotUpdate(snapshotName = globalId, json = sn)
            
            snapshot.validateState(
                self.apiclient,
                snapshotstate="backedup",
            )
            self._cleanup.append(snapshot)
        # Migrate all volumes and VMs

        destinationHost, vol_list = self.get_destination_pools_hosts(vm)
        vm = self.migrateVm(self.virtual_machine, destinationHost)


    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_04_migrate_vm_live_resize_volume(self):
        """
        Resize the data volume , Migrate all the volumes and VM.
        """
        global vm
        global data_disk_1

        data_disk_1.resize(
            self.apiclient,
            diskofferingid=self.disk_offering_20.id
        )
        # Migrate all volumes and VMs
        destinationHost,  vol_list = self.get_destination_pools_hosts(vm)
        vm = self.migrateVm(self.virtual_machine, destinationHost)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_05_migrate_vm_live_restore(self):
        """
        Restore the VM , Migrate all the volumes and VM.
        """
        global vm
        global data_disk_1
        self.virtual_machine.restore(self.apiclient)
        self.virtual_machine.getState(
            self.apiclient,
            "Running"
        )
        # Migrate the VM and its volumes

        destinationHost, vol_list = self.get_destination_pools_hosts(vm)
        vm = self.migrateVm(self.virtual_machine, destinationHost)

        cmd = destroyVirtualMachine.destroyVirtualMachineCmd()
        cmd.id = self.virtual_machine.id
        cmd.expunge = True
        self.apiclient.destroyVirtualMachine(cmd)
        data_disk_1.delete(self.apiclient)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_06_migrate_live_remote(self):
        """
        Migrate VMs/Volumes live
        """
        global vm2

        volumes = list_volumes(self.apiclient, virtualmachineid = self.virtual_machine_on_remote.id)
        for v in volumes:
            vol = sptypes.VolumeUpdateDesc(rename = v.id)
            name = v.path.split("/")[3]

            rename = self.spapi.volumeUpdate(volumeName = "~" + name, json = vol)
        destinationHost = self.getDestinationHost(self.virtual_machine_on_remote.hostid, self.host_remote)
        # Migrate the VM
        vm2 = self.migrateVm(self.virtual_machine_on_remote, destinationHost)
        # self.check_files(vm,destinationHost)


        """
        Migrate the VM and ROOT volume
        """
        # Get all volumes to be migrated

        destinationHost,  vol_list = self.get_destination_pools_hosts(vm2)
        vm2 = self.migrateVm(self.virtual_machine_on_remote, destinationHost)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_07_migrate_vm_live_attach_disk_on_remote(self):
        """
        Add a data disk and migrate vm, data disk and root disk
        """
        
        global vm2
        global data_disk_2
        data_disk_2 = Volume.create(
            self.apiclient,
            {"diskname":"StorPoolDisk-5" },
            zoneid=self.zone.id,
            diskofferingid=self.disk_offering.id,
        )

        self.debug("Created volume with ID: %s" % data_disk_2.id)

        self.virtual_machine_on_remote.attach_volume(
            self.apiclient,
            data_disk_2
        )

        volumes = list_volumes(self.apiclient, id = data_disk_2.id)
        vol = sptypes.VolumeUpdateDesc(rename = volumes[0].id)
        name = volumes[0].path.split("/")[3]

        rename = self.spapi.volumeUpdate(volumeName = "~" + name, json = vol)

        destinationHost, vol_list = self.get_destination_pools_hosts(vm2)
        vm2 = self.migrateVm(self.virtual_machine_on_remote, destinationHost)


        self.virtual_machine_on_remote.attach_volume(
            self.apiclient,
            self.volume_on_remote
        )

        destinationHost, vol_list = self.get_destination_pools_hosts(vm2)
        vm2 = self.migrateVm(self.virtual_machine_on_remote, destinationHost)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_08_migrate_vm_live_with_snapshots_on_remote(self):
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
            globalId = self.storpool_snapshot_globalid(snapshot)
            sn = sptypes.SnapshotUpdateDesc(rename = snapshot.id)
    
            rename = self.spapi.snapshotUpdate(snapshotName = globalId, json = sn)
            snapshot.validateState(
                self.apiclient,
                snapshotstate="backedup",
            )
            self._cleanup.append(snapshot)
        # Migrate all volumes and VMs

        destinationHost, vol_list = self.get_destination_pools_hosts(vm2)
        vm2 = self.migrateVm(self.virtual_machine_on_remote, destinationHost)


    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_09_migrate_vm_live_resize_volume_on_remote(self):
        """
        Resize the data volume , Migrate all the volumes and VM.
        """
        global vm2
        global data_disk_2

        data_disk_2.resize(
            self.apiclient,
            diskofferingid=self.disk_offering_20.id
        )
        # Migrate all volumes and VMs
        destinationHost,  vol_list = self.get_destination_pools_hosts(vm2)
        vm2 = self.migrateVm(self.virtual_machine_on_remote, destinationHost)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_10_migrate_vm_live_restore_on_remote(self):
        """
        Restore the VM , Migrate all the volumes and VM.
        """
        global vm2
        global data_disk_2

        self.virtual_machine_on_remote.restore(self.apiclient)
        self.virtual_machine_on_remote.getState(
            self.apiclient,
            "Running"
        )
        # Migrate the VM and its volumes

        destinationHost, vol_list = self.get_destination_pools_hosts(vm2)
        vm2 = self.migrateVm(self.virtual_machine_on_remote, destinationHost)

        cmd = destroyVirtualMachine.destroyVirtualMachineCmd()
        cmd.id = self.virtual_machine_on_remote.id
        cmd.expunge = True
        self.apiclient.destroyVirtualMachine(cmd)
        data_disk_2.delete(self.apiclient)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_11_resize_renamed_volume(self):
        '''Resize volume which was created with globalid than renamed with uuid'''

        volume_on_sp_1 = Volume.create(
            self.apiclient,
            {"diskname":"StorPoolDisk-3" },
            zoneid=self.zone.id,
            diskofferingid=self.disk_offering.id,
        )
        virtual_machine = VirtualMachine.create(
            self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=self.template.id,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            hostid = self.host_on_local_1.id,
            rootdisksize=10
        )

        virtual_machine.attach_volume(self.apiclient, volume_on_sp_1)

        self.assertEqual(VirtualMachine.RUNNING, virtual_machine.state, "Running")


        listvol = Volume.list(
            self.apiclient,
            virtualmachineid = virtual_machine.id,
            id= volume_on_sp_1.id
            )
        
        volume = listvol[0]
        
        vol = sptypes.VolumeUpdateDesc(rename = volume.id)
        name = volume.path.split("/")[3]

        rename = self.spapi.volumeUpdate(volumeName = "~" + name, json = vol)
        #resize volume with it's global id
        self.helper.resizing_volume(volume, globalid=True)
        
        volume_with_global_id = self.spapi.volumeList(volumeName = "~" + name)

        #resize volume that was renamed with uuid
        self.helper.resizing_volume(volume, globalid=False)
        
        volume_with_uuid = self.spapi.volumeList(volumeName = volume.id)

        self.debug("volume_with_global_id %s" % volume_with_global_id)
        self.debug("volume_with_uuid %s" % volume_with_uuid)
        self.assertEqual(volume_with_global_id[0].name, volume_with_uuid[0].name, "Are not the same")

        cmd = destroyVirtualMachine.destroyVirtualMachineCmd()
        cmd.id = virtual_machine.id
        cmd.expunge = True
        self.apiclient.destroyVirtualMachine(cmd)
        volume_on_sp_1.delete(self.apiclient)



    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_12_resize_renamed_root_volume(self):
        '''Resize ROOT volume which was created with globalid than renamed with uuid'''

        virtual_machine = VirtualMachine.create(
            self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=self.template.id,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            hostid = self.host_on_local_1.id,
            rootdisksize=10
        )
        self.assertEqual(VirtualMachine.RUNNING, virtual_machine.state, "Running")

        listvol = Volume.list(
            self.apiclient,
            virtualmachineid = virtual_machine.id,
            type = "ROOT"
            )

        volume = listvol[0]
        vol = sptypes.VolumeUpdateDesc(rename = volume.id)
        name = volume.path.split("/")[3]

        rename = self.spapi.volumeUpdate(volumeName = "~" + name, json = vol)
        #resize volume with it's global id
        self.helper.resizing_volume(volume, globalid=True)
        volume_with_global_id = self.spapi.volumeList(volumeName = "~" + name)

        #resize volume that was renamed with uuid
        self.helper.resizing_volume(volume, globalid=False)
        
        volume_with_uuid = self.spapi.volumeList(volumeName = volume.id)
        self.debug("volume_with_global_id %s" % volume_with_global_id)
        self.debug("volume_with_uuid %s" % volume_with_uuid)

        self.assertEqual(volume_with_global_id[0].name, volume_with_uuid[0].name, "Are not the same")

        cmd = destroyVirtualMachine.destroyVirtualMachineCmd()
        cmd.id = virtual_machine.id
        cmd.expunge = True
        self.apiclient.destroyVirtualMachine(cmd)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_13_revert_renamed_snapshot(self):
        '''Revert which was created with globalid than renamed with uuid'''
        virtual_machine = VirtualMachine.create(
            self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=self.template.id,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            hostid = self.host_on_local_1.id,
            rootdisksize=10
        )
        self.assertEqual(VirtualMachine.RUNNING, virtual_machine.state, "Running")

        listvol = Volume.list(
            self.apiclient,
            virtualmachineid = virtual_machine.id,
            type = "ROOT"
            )

        snapshot = Snapshot.create(self.apiclient, volume_id = listvol[0].id)

        volume = listvol[0]
        vol = sptypes.VolumeUpdateDesc(rename = volume.id)
        name = volume.path.split("/")[3]

        rename = self.spapi.volumeUpdate(volumeName = "~" + name, json = vol)
        
        virtual_machine.stop(self.apiclient, forced = True)

        globalId = self.storpool_snapshot_globalid(snapshot)
        sn = sptypes.SnapshotUpdateDesc(rename = snapshot.id)

        rename = self.spapi.snapshotUpdate(snapshotName = globalId, json = sn)
        snapshot.validateState(
            self.apiclient,
            snapshotstate="backedup",
        )

        Volume.revertToSnapshot(self.apiclient, snapshot.id)

        virtual_machine.start(self.apiclient)

        cmd = destroyVirtualMachine.destroyVirtualMachineCmd()
        cmd.id = virtual_machine.id
        cmd.expunge = True
        self.apiclient.destroyVirtualMachine(cmd)
        snapshot.delete(self.apiclient)     

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
    def storpool_snapshot_globalid(cls, snapshot):
        flag = False
        sp_snapshots = cls.spapi.snapshotsList()
        globalId = None
        for snap in sp_snapshots:
            tags = snap.tags
            for t in tags:
                cls.debug("################## Snapshot id %s snapshot tag %s" % (snapshot.id, tags[t]))
                if tags[t] == snapshot.id:
                    cls.debug("############################## SNAPSHOT NAME %s" % snap)
                    return snap.name
            else:
                continue
            break
                       
        if flag is False:
            raise Exception(err)
        return globalId
