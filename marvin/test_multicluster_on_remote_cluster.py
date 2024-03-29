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
                                  startVirtualMachine)
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

class TestStoragePool(cloudstackTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestStoragePool, cls).setUpClass()
        try:
            cls.setUpCloudStack()
        except Exception:
            cls.cleanUpCloudStack()
            raise

    @classmethod
    def setUpCloudStack(cls):
        testClient = super(TestStoragePool, cls).getClsTestClient()
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
        cls._cleanup = []

        zones = list_zones(cls.apiclient)

        for z in zones:
            if z.internaldns1 == cls.getClsConfig().mgtSvr[0].mgtSvrIp:
                cls.zone = z

        td = TestData()
        cls.testdata = td.testdata
        cls.helper = StorPoolHelper()
        StorPoolHelper.logger = cls

        cls.account = cls.helper.create_account(
                            cls.apiclient,
                            cls.services["account"],
                            accounttype = 1,
                            domainid=cls.domain.id,
                            roleid = 1
                            )
        cls._cleanup.append(cls.account)

        securitygroup = SecurityGroup.list(cls.apiclient, account = cls.account.name, domainid= cls.account.domainid)[0]
        cls.helper.set_securityGroups(cls.apiclient, account = cls.account.name, domainid= cls.account.domainid, id = securitygroup.id)

        storpool_primary_storage = cls.testdata[TestData.primaryStorage]

        storpool_service_offerings = cls.testdata[TestData.serviceOffering]

        cls.template_name = storpool_primary_storage.get("name")

        storage_pool = list_storage_pools(
            cls.apiclient,
            name=cls.template_name
            )

        service_offerings = list_service_offering(
            cls.apiclient,
            name=cls.template_name
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

        cls.debug(pprint.pformat(template))
        cls.debug(pprint.pformat(cls.hypervisor))

        if template == FAILED:
            assert False, "get_template() failed to return template\
                    with description %s" % cls.services["ostype"]


        cls.service_offering = service_offerings
        cls.debug(pprint.pformat(cls.service_offering))

        cls.local_cluster = cls.helper.get_local_cluster(cls.apiclient, zoneid = cls.zone.id)
        cls.host = cls.helper.list_hosts_by_cluster_id(cls.apiclient, cls.local_cluster.id)

        cls.remote_cluster = cls.helper.get_remote_cluster(cls.apiclient, zoneid = cls.zone.id)
        cls.host_remote = cls.helper.list_hosts_by_cluster_id(cls.apiclient, cls.remote_cluster.id)


        cls.services["domainid"] = cls.domain.id
        cls.services["small"]["zoneid"] = cls.zone.id
        cls.services["templates"]["ostypeid"] = template.ostypeid
        cls.services["zoneid"] = cls.zone.id
        cls.services["diskofferingid"] = cls.disk_offerings.id

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
 
        cls.virtual_machine = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
            accountid=cls.account.name,
            domainid=cls.account.domainid,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            hostid = cls.host[0].id,
            rootdisksize=10
        )
        cls.virtual_machine2 = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
            accountid=cls.account.name,
            domainid=cls.account.domainid,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            hostid = cls.host[0].id,
            rootdisksize=10
        )
        cls.virtual_machine3 = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
            accountid=cls.account.name,
            domainid=cls.account.domainid,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            hostid = cls.host[0].id,
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
    def test_01_start_vm_on_remote_cluster(self):
        ''' Test Attach Volume To Running Virtual Machine
        '''
        self.virtual_machine.stop(self.apiclient, forced = True)
        self.virtual_machine2.stop(self.apiclient, forced = True)
        self.virtual_machine3.stop(self.apiclient, forced = True)
        
        self.helper.start(self.apiclient, self.virtual_machine.id, self.host_remote[0].id)
        self.helper.start(self.apiclient, self.virtual_machine2.id, self.host_remote[0].id)
        self.helper.start(self.apiclient, self.virtual_machine3.id, self.host_remote[0].id)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_02_attach_detach_volume_to_vm_on_remote(self):
        ''' Test Attach Volume To Running Virtual Machine on remote
        '''
        time.sleep(30)
        self.assertEqual(VirtualMachine.RUNNING, self.virtual_machine.state, "Running")
        volume = self.virtual_machine.attach_volume(
            self.apiclient,
            self.volume_1
            )
        print(volume)
        self.assertIsNotNone(volume, "Volume is not None")

        list_vm_volumes = Volume.list(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            id= volume.id
            )
        print(list_vm_volumes)
        self.assertEqual(volume.id, list_vm_volumes[0].id, "Is true")

        self.virtual_machine.stop(self.apiclient, forced = True)
        volume = self.virtual_machine.detach_volume(
            self.apiclient,
            self.volume_1
            )

        self.helper.start(self.apiclient, self.virtual_machine.id, self.host_remote[0].id)
        list_vm_volumes = Volume.list(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            id = volume.id
            )
        print(list_vm_volumes)
        self.assertIsNone(list_vm_volumes, "Is None")

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_03_resize_root_volume_of_vm_on_remote(self):
        ''' Test Resize Root volume on Running Virtual Machine on remote
        '''
        self.assertEqual(VirtualMachine.RUNNING, self.virtual_machine2.state, "Running")
        volume = list_volumes(
            self.apiclient,
            virtualmachineid = self.virtual_machine2.id,
            type = "ROOT",
            listall = True
            )
        volume = volume[0]
        self.assertEqual(volume.type, 'ROOT', "Volume is not of ROOT type")
        shrinkOk = False
        if volume.size > int((self.disk_offering_20.disksize) * (1024**3)):
            shrinkOk= True

        cmd = resizeVolume.resizeVolumeCmd()
        cmd.id = volume.id
        cmd.size = 20
        cmd.shrinkok = shrinkOk

        self.apiclient.resizeVolume(cmd)

        new_size = Volume.list(
            self.apiclient,
            id=volume.id,
            listall = True
            )

        self.assertTrue(
            (new_size[0].size == int((self.disk_offering_20.disksize) * (1024**3))),
            "New size is not int((self.disk_offering_20) * (1024**3)"
            )
        volume = new_size[0]
        shrinkOk = False
        if volume.size > int((self.disk_offering_100.disksize) * (1024**3)):
            shrinkOk= True

        cmd = resizeVolume.resizeVolumeCmd()
        cmd.id = volume.id
        cmd.size = 100
        cmd.shrinkok = shrinkOk

        self.apiclient.resizeVolume(cmd)
        new_size = Volume.list(
            self.apiclient,
            id=volume.id,
            listall = True
            )

        self.assertTrue(
            (new_size[0].size == int((self.disk_offering_100.disksize) * (1024**3))),
            "New size is not int((self.disk_offering_20) * (1024**3)"
            )

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_04_resize_attached_volume_of_vm_on_remote(self):
        ''' Test Resize Volume  Attached To Running Virtual Machine on remote
        '''
        self.assertEqual(VirtualMachine.RUNNING, self.virtual_machine.state, "Running")
        volume = self.virtual_machine.attach_volume(
            self.apiclient,
            self.volume_1
            )
        shrinkOk = False
        if volume.size > int((self.disk_offering_20.disksize) * (1024**3)):
            shrinkOk= True

        cmd = resizeVolume.resizeVolumeCmd()
        cmd.id = volume.id
        cmd.diskofferingid = self.disk_offering_20.id
        cmd.shrinkok = shrinkOk

        self.apiclient.resizeVolume(cmd)

        new_size = Volume.list(
            self.apiclient,
            id=volume.id,
            listall = True
            )

        self.assertTrue(
            (new_size[0].size == int((self.disk_offering_20.disksize) * (1024**3))),
            "New size is not int((self.disk_offering_20) * (1024**3)"
            )
        volume = new_size[0]
        shrinkOk = False
        if volume.size > int((self.disk_offering_100.disksize) * (1024**3)):
            shrinkOk= True

        cmd = resizeVolume.resizeVolumeCmd()
        cmd.id = volume.id
        cmd.diskofferingid = self.disk_offering_100.id
        cmd.shrinkok = shrinkOk

        self.apiclient.resizeVolume(cmd)
        new_size = Volume.list(
            self.apiclient,
            id=volume.id,
            listall = True
            )

        self.assertTrue(
            (new_size[0].size == int((self.disk_offering_100.disksize) * (1024**3))),
            "New size is not int((self.disk_offering_20) * (1024**3)"
            )

        # return to small disk
        volume = new_size[0]
        shrinkOk = False
        if volume.size > int((self.disk_offerings.disksize)* (1024**3)):
            shrinkOk= True

        cmd.diskofferingid = self.disk_offerings.id
        cmd.shrinkok = shrinkOk

        self.apiclient.resizeVolume(cmd)
        new_size = Volume.list(
            self.apiclient,
            id=volume.id,
            listall = True
            )
        self.assertTrue(
            (new_size[0].size == int((self.disk_offerings.disksize)*(1024**3))),
            "Could not return to Small disk"
            )

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_05_snapshot_root_disk_working_vm_on_remote(self):
        """ Snapshot root disk on running virtual machine on remote"""
        volume = list_volumes(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            type = "ROOT",
            listall = True
            )

        snapshot = Snapshot.create(
                        self.apiclient,
                        volume[0].id,
                        account=self.account.name,
                        domainid=self.account.domainid
                        )
        self.assertIsNotNone(snapshot, "Could not create snapshot from ROOT")
 
    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_06_snapshot_to_template_secondary_storage(self):
        ''' Create template from snapshot
        '''
        volume = Volume.list(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            type = "ROOT",
            listall = True
            )
        volume = volume[0]

        backup_config = list_configurations(
            self.apiclient, 
            name = "sp.bypass.secondary.storage" )
        if (backup_config[0].value == "true"):
            backup_config = Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage", 
            value = "false")
        snapshot = Snapshot.create(
           self.apiclient,
            volume_id = volume.id,
            account=self.account.name,
            domainid=self.account.domainid
            )
        self.assertIsNotNone(snapshot, "Could not create snapshot")
        self.assertIsInstance(snapshot, Snapshot, "Snapshot is not an instance of Snapshot")
        
        template = self.helper.create_template_from_snapshot(
            self.apiclient,
            self.services,
            snapshotid = snapshot.id
            )
        
        virtual_machine = VirtualMachine.create(self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=template.id,
            accountid=self.account.name,
            domainid=self.account.domainid,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
            )

        self.assertIsNotNone(template, "Template is None")
        self.assertIsInstance(template, Template, "Template is instance of template")
        ssh_client = virtual_machine.get_ssh_client(reconnect=True)

        self._cleanup.append(template)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_07_snapshot_to_template_bypass_secondary(self):
        ''' Create template from snapshot bypassing secondary storage
        '''
        ##cls.virtual_machine
        volume = list_volumes(
                        self.apiclient,
                        virtualmachineid = self.virtual_machine.id,
                        type = "ROOT",
                        listall = True
                        )

        backup_config = list_configurations(
            self.apiclient, 
            name = "sp.bypass.secondary.storage" )
        if (backup_config[0].value == "false"):
            backup_config = Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage", 
            value = "true")

        snapshot = Snapshot.create(
           self.apiclient,
            volume_id = volume[0].id,
            account=self.account.name,
            domainid=self.account.domainid
            )

        self.assertIsNotNone(snapshot, "Could not create snapshot")
        self.assertIsInstance(snapshot, Snapshot, "Snapshot is not an instance of Snapshot")
        
        template = self.helper.create_template_from_snapshot(
            self.apiclient,
            self.services,
            snapshotid = snapshot.id
            )

        virtual_machine = VirtualMachine.create(self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=template.id,
            accountid=self.account.name,
            domainid=self.account.domainid,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
            )

        ssh_client = virtual_machine.get_ssh_client(reconnect=True)

        self.assertIsNotNone(template, "Template is None")
        self.assertIsInstance(template, Template, "Template is instance of template")

        self._cleanup.append(template)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_08_volume_to_template(self):
        ''' Create template from snapshot
        '''
        volume = Volume.list(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            type = "ROOT",
            listall = True
            )

        self.virtual_machine.stop(self.apiclient, forced = True)

        template = self.helper.create_template_from_snapshot(
            self.apiclient,
            self.services,
            volumeid = volume[0].id
            )

        virtual_machine = VirtualMachine.create(self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=template.id,
            accountid=self.account.name,
            domainid=self.account.domainid,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
            )

        ssh_client = virtual_machine.get_ssh_client(reconnect=True)

        self.assertIsNotNone(template, "Template is None")
        self.assertIsInstance(template, Template, "Template is instance of template")

        self._cleanup.append(template)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_09_create_vm_snapshots(self):
        """Test to create VM snapshots
        """
        volume_attached = self.virtual_machine3.attach_volume(
            self.apiclient,
            self.volume
            )

        self.assertEqual(volume_attached.id, self.volume.id, "Is not the same volume ")
        try:
            # Login to VM and write data to file system
            ssh_client = self.virtual_machine3.get_ssh_client(reconnect=True)

            cmds = [
                "echo %s > %s/%s" %
                (self.random_data_0, self.test_dir, self.random_data),
                "sync",
                "sleep 1",
                "sync",
                "sleep 1",
                "cat %s/%s" %
                (self.test_dir, self.random_data)
            ]

            for c in cmds:
                self.debug(c)
                result = ssh_client.execute(c)
                self.debug(result)


        except Exception:
            self.fail("SSH failed for Virtual machine: %s" %
                      self.virtual_machine3.ipaddress)
        self.assertEqual(
            self.random_data_0,
            result[0],
            "Check the random data has be write into temp file!"
        )

        time.sleep(30)
        MemorySnapshot = False
        vm_snapshot = VmSnapshot.create(
            self.apiclient,
            self.virtual_machine3.id,
            MemorySnapshot,
            "TestSnapshot",
            "Display Text"
        )
        self.assertEqual(
            vm_snapshot.state,
            "Ready",
            "Check the snapshot of vm is ready!"
        )

        return

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_10_revert_vm_snapshots(self):
        """Test to revert VM snapshots
        """

        try:
            ssh_client = self.virtual_machine3.get_ssh_client(reconnect=True)

            cmds = [
                "rm -rf %s/%s" % (self.test_dir, self.random_data),
                "ls %s/%s" % (self.test_dir, self.random_data)
            ]

            for c in cmds:
                self.debug(c)
                result = ssh_client.execute(c)
                self.debug(result)

        except Exception:
            self.fail("SSH failed for Virtual machine: %s" %
                      self.virtual_machine3.ipaddress)

        if str(result[0]).index("No such file or directory") == -1:
            self.fail("Check the random data has be delete from temp file!")

        time.sleep(30)

        list_snapshot_response = VmSnapshot.list(
            self.apiclient,
            virtualmachineid=self.virtual_machine3.id,
            listall=True)

        self.assertEqual(
            isinstance(list_snapshot_response, list),
            True,
            "Check list response returns a valid list"
        )
        self.assertNotEqual(
            list_snapshot_response,
            None,
            "Check if snapshot exists in ListSnapshot"
        )

        self.assertEqual(
            list_snapshot_response[0].state,
            "Ready",
            "Check the snapshot of vm is ready!"
        )

        self.virtual_machine3.stop(self.apiclient, forced=True)

        VmSnapshot.revertToSnapshot(
            self.apiclient,
            list_snapshot_response[0].id
            )

        self.helper.start(self.apiclient, self.virtual_machine3.id, self.host_remote[0].id)

        try:
            ssh_client = self.virtual_machine3.get_ssh_client(reconnect=True)

            cmds = [
                "cat %s/%s" % (self.test_dir, self.random_data)
            ]

            for c in cmds:
                self.debug(c)
                result = ssh_client.execute(c)
                self.debug(result)

        except Exception:
            self.fail("SSH failed for Virtual machine: %s" %
                      self.virtual_machine3.ipaddress)

        self.assertEqual(
            self.random_data_0,
            result[0],
            "Check the random data is equal with the ramdom file!"
        )

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_11_delete_vm_snapshots(self):
        """Test to delete vm snapshots
        """

        list_snapshot_response = VmSnapshot.list(
            self.apiclient,
            virtualmachineid=self.virtual_machine3.id,
            listall=True)

        self.assertEqual(
            isinstance(list_snapshot_response, list),
            True,
            "Check list response returns a valid list"
        )
        self.assertNotEqual(
            list_snapshot_response,
            None,
            "Check if snapshot exists in ListSnapshot"
        )
        VmSnapshot.deleteVMSnapshot(
            self.apiclient,
            list_snapshot_response[0].id)

        time.sleep(30)

        list_snapshot_response = VmSnapshot.list(
            self.apiclient,
            #vmid=self.virtual_machine.id,
            virtualmachineid=self.virtual_machine3.id,
            listall=False)
        self.debug('list_snapshot_response -------------------- %s' % list_snapshot_response)

        self.assertIsNone(list_snapshot_response, "snapshot is already deleted")

           