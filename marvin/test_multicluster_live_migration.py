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
                             Volume,
                             SecurityGroup,
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
                               list_zones)
from marvin.lib.utils import random_gen, cleanup_resources, validateList, is_snapshot_on_nfs, isAlmostEqual
from nose.plugins.attrib import attr
import uuid

import storpool
from sp_util import (TestData, StorPoolHelper)


class TestLiveMigration(cloudstackTestCase):
    vm = ""
    vm2 = ""
    data_disk_1 = ""
    data_disk_2 = ""

    @classmethod
    def setUpClass(cls):
        super(TestLiveMigration, cls).setUpClass()
        try:
            cls.setUpCloudStack()
        except Exception:
            cls.cleanUpCloudStack()
            raise

    @classmethod
    def setUpCloudStack(cls):
        super(TestLiveMigration, cls).setUpClass()

        cls._cleanup = []
        testClient = super(TestLiveMigration, cls).getClsTestClient()
        cls.apiclient = testClient.getApiClient()
        cls.unsupportedHypervisor = False
        cls.hypervisor = testClient.getHypervisorInfo()
        if cls.hypervisor.lower() in ("hyperv", "lxc"):
            cls.unsupportedHypervisor = True
            return

        cls.services = testClient.getParsedTestDataConfig()
        # Get Zone, Domain and templates
        cls.domain = get_domain(cls.apiclient)
        cls.zone = None


        zones = list_zones(cls.apiclient)

        for z in zones:
            if z.internaldns1 == cls.getClsConfig().mgtSvr[0].mgtSvrIp:
                cls.zone = z

        td = TestData()
        cls.testdata = td.testdata
        cls.helper = StorPoolHelper()

        cls.template_name = cls.testdata[TestData.primaryStorage].get("name")

        storage_pool = list_storage_pools(
            cls.apiclient,
            name = cls.template_name
            )

        service_offerings = list_service_offering(
            cls.apiclient,
            name = cls.template_name
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

        cls.disk_offerings = disk_offerings[0]
        cls.disk_offering_20 = disk_offering_20[0]
        cls.disk_offering_100 = disk_offering_100[0]
        cls.debug(pprint.pformat(storage_pool))
        if storage_pool is None:
            storage_pool = cls.helper.create_sp_template_and_storage_pool(cls.apiclient, cls.template_name, cls.testdata[TestData.primaryStorage], cls.zone.id)
        else:
            storage_pool = storage_pool[0]
        cls.storage_pool = storage_pool
        cls.debug(pprint.pformat(storage_pool))
        if service_offerings is None:
            service_offerings = ServiceOffering.create(cls.apiclient, cls.testdata[TestData.serviceOffering])
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

        cls.local_cluster = cls.helper.get_local_cluster(cls.apiclient, zoneid = cls.zone.id)
        cls.host = cls.helper.list_hosts_by_cluster_id(cls.apiclient, cls.local_cluster.id)

        assert len(cls.host) > 1, "Hosts list is less than 1"
        cls.host_on_local_1 = cls.host[0]
        cls.host_on_local_2 = cls.host[1]

        cls.remote_cluster = cls.helper.get_remote_cluster(cls.apiclient, zoneid = cls.zone.id)
        cls.host_remote = cls.helper.list_hosts_by_cluster_id(cls.apiclient, cls.remote_cluster.id)
        assert len(cls.host_remote) > 1, "Hosts list is less than 1"

        cls.host_on_remote1 = cls.host_remote[0]
        cls.host_on_remote2 = cls.host_remote[1]

        cls.services["domainid"] = cls.domain.id
        cls.services["zoneid"] = cls.zone.id
        cls.services["template"] = template.id
        cls.services["diskofferingid"] = disk_offerings[0].id

        cls.account = Account.create(
                            cls.apiclient,
                            cls.services["account"],
                            domainid=cls.domain.id
                            )
        cls._cleanup.append(cls.account)

        securitygroup = SecurityGroup.list(cls.apiclient, account = cls.account.name, domainid= cls.account.domainid)[0]
        cls.helper.set_securityGroups(cls.apiclient, account = cls.account.name, domainid= cls.account.domainid, id = securitygroup.id)

        cls.volume_1 = Volume.create(
            cls.apiclient,
            cls.services,
            account=cls.account.name,
            domainid=cls.account.domainid
        )

        cls.volume = Volume.create(
            cls.apiclient,
            cls.services,
            account=cls.account.name,
            domainid=cls.account.domainid
        )

        cls.volume_on_remote = Volume.create(
            cls.apiclient,
            cls.services,
            account=cls.account.name,
            domainid=cls.account.domainid
        )

        cls.virtual_machine = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
            accountid=cls.account.name,
            domainid=cls.account.domainid,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            hostid = cls.host_on_local_1.id,
            rootdisksize=10
        )


        cls.virtual_machine_on_remote = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
            accountid=cls.account.name,
            domainid=cls.account.domainid,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            hostid = cls.host_on_remote1.id,
            rootdisksize=10
        )

        cls.virtual_machine_migr_btw_cl = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
            accountid=cls.account.name,
            domainid=cls.account.domainid,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            hostid = cls.host_on_local_1.id,
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
        destinationHost = self.helper.getDestinationHost(self.virtual_machine.hostid, self.host)
        # Migrate the VM
        vm = self.helper.migrateVm(self.apiclient, self.virtual_machine, destinationHost)
        # self.check_files(vm,destinationHost)

        destinationHost,  vol_list = self.helper.get_destination_pools_hosts(self.apiclient, vm, self.host)
        vm = self.helper.migrateVm(self.apiclient, self.virtual_machine, destinationHost)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_02_migrate_vm_live_attach_disk(self):
        """
        Add a data disk and migrate vm, data disk and root disk
        """
        
        global vm
        global data_disk_1
        data_disk_1 = Volume.create(
            self.apiclient,
            self.services,
            account=self.account.name,
            domainid=self.account.domainid
        )

        self.debug("Created volume with ID: %s" % data_disk_1.id)

        self.virtual_machine.attach_volume(
            self.apiclient,
            data_disk_1
        )

        destinationHost, vol_list = self.helper.get_destination_pools_hosts(self.apiclient, vm, self.host)
        vm = self.helper.migrateVm(self.apiclient, self.virtual_machine, destinationHost)


        self.virtual_machine.attach_volume(
            self.apiclient,
            self.volume
        )

        destinationHost, vol_list = self.helper.get_destination_pools_hosts(self.apiclient, vm, self.host)
        vm = self.helper.migrateVm(self.apiclient, self.virtual_machine, destinationHost)

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
                volume_id=vol.id,
                account=self.account.name,
                domainid=self.account.domainid,
            )
            snapshot.validateState(
                self.apiclient,
                snapshotstate="backedup",
            )
        # Migrate all volumes and VMs

        destinationHost, vol_list = self.helper.get_destination_pools_hosts(self.apiclient, vm, self.host)
        vm = self.helper.migrateVm(self.apiclient, self.virtual_machine, destinationHost)


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
        destinationHost,  vol_list = self.helper.get_destination_pools_hosts(self.apiclient, vm, self.host)
        vm = self.helper.migrateVm(self.apiclient, self.virtual_machine, destinationHost)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_05_migrate_vm_live_restore(self):
        """
        Restore the VM , Migrate all the volumes and VM.
        """
        global vm
        self.virtual_machine.restore(self.apiclient)
        self.virtual_machine.getState(
            self.apiclient,
            "Running"
        )

        destinationHost, vol_list = self.helper.get_destination_pools_hosts(self.apiclient, vm, self.host)
        vm = self.helper.migrateVm(self.apiclient, self.virtual_machine, destinationHost)

        self.helper.destroy_vm(self.apiclient, self.virtual_machine.id)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_06_migrate_live_remote(self):
        """
        Migrate VMs/Volumes live
        """
        global vm2
        destinationHost = self.helper.getDestinationHost(self.virtual_machine_on_remote.hostid, self.host_remote)
        # Migrate the VM
        vm2 = self.helper.migrateVm(self.apiclient, self.virtual_machine_on_remote, destinationHost)
        # self.check_files(vm,destinationHost)

        destinationHost,  vol_list = self.helper.get_destination_pools_hosts(self.apiclient, vm2, self.host_remote)
        vm2 = self.helper.migrateVm(self.apiclient, self.virtual_machine_on_remote, destinationHost)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_07_migrate_vm_live_attach_disk_on_remote(self):
        """
        Add a data disk and migrate vm, data disk and root disk
        """
        
        global vm2
        global data_disk_2
        data_disk_2 = Volume.create(
            self.apiclient,
            self.services,
            account=self.account.name,
            domainid=self.account.domainid
        )

        self.debug("Created volume with ID: %s" % data_disk_2.id)

        self.virtual_machine_on_remote.attach_volume(
            self.apiclient,
            data_disk_2
        )

        destinationHost, vol_list = self.helper.get_destination_pools_hosts(self.apiclient, vm2, self.host_remote)
        vm2 = self.helper.migrateVm(self.apiclient, self.virtual_machine_on_remote, destinationHost)


        self.virtual_machine_on_remote.attach_volume(
            self.apiclient,
            self.volume_on_remote
        )

        destinationHost, vol_list = self.helper.get_destination_pools_hosts( self.apiclient, vm2, self.host_remote)
        vm2 = self.helper.migrateVm(self.apiclient, self.virtual_machine_on_remote, destinationHost)

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
                volume_id=vol.id,
                account=self.account.name,
                domainid=self.account.domainid,
            )
            snapshot.validateState(
                self.apiclient,
                snapshotstate="backedup",
            )
        # Migrate all volumes and VMs

        destinationHost, vol_list = self.helper.get_destination_pools_hosts(self.apiclient, vm2, self.host_remote)
        vm2 = self.helper.migrateVm(self.apiclient, self.virtual_machine_on_remote, destinationHost)


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
        destinationHost,  vol_list = self.helper.get_destination_pools_hosts(self.apiclient, vm2, self.host_remote)
        vm2 = self.helper.migrateVm(self.apiclient, self.virtual_machine_on_remote, destinationHost)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_10_migrate_vm_live_restore_on_remote(self):
        """
        Restore the VM , Migrate all the volumes and VM.
        """
        global vm2
        self.virtual_machine_on_remote.restore(self.apiclient)
        self.virtual_machine_on_remote.getState(
            self.apiclient,
            "Running"
        )
        # Migrate the VM and its volumes

        destinationHost, vol_list = self.helper.get_destination_pools_hosts(self.apiclient, vm2, self.host_remote)
        vm2 = self.helper.migrateVm(self.apiclient, self.virtual_machine_on_remote, destinationHost)

        self.helper.destroy_vm(self.apiclient, self.virtual_machine_on_remote.id)


    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_11_migrate_vm_live_between_clusters(self):
        cloudstackversion = Configurations.listCapabilities(self.apiclient).cloudstackversion
        cloudstackversion = cloudstackversion.split(".")
        if int(cloudstackversion[1]) < 12:
            return
        
        destinationHost = self.helper.getDestinationHost(self.virtual_machine_migr_btw_cl.hostid, self.host_remote)
        # Migrate the VM
        vm = self.helper.migrateVm(self.apiclient, self.virtual_machine_migr_btw_cl, destinationHost)
        # self.check_files(vm,destinationHost)

        self.helper.destroy_vm(self.apiclient, self.virtual_machine_migr_btw_cl.id)


