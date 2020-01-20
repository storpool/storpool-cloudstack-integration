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
from marvin.codes import FAILED, KVM, PASS, XEN_SERVER, RUNNING
from nose.plugins.attrib import attr
from marvin.cloudstackTestCase import cloudstackTestCase
from marvin.lib.utils import random_gen, cleanup_resources, validateList, is_snapshot_on_nfs, isAlmostEqual
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
                               list_configurations, list_service_offering)
from marvin.cloudstackAPI import (listOsTypes,
                                  listTemplates,
                                  createTemplate,
                                  createVolume,
                                  resizeVolume)
import time
import pprint
import random

class TestStoragePool(cloudstackTestCase):

    @classmethod
    def setUpClass(cls):
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
        cls.zone = get_zone(cls.apiclient, testClient.getZoneForTests())

        storpool_primary_storage = {
            "name" : "cloud-test-dev-1",
            "zoneid": cls.zone.id,
            "url": "cloud-test-dev-1",
            "scope": "zone",
            "capacitybytes": 4500000,
            "capacityiops": 155466464221111121,
            "hypervisor": "kvm",
            "provider": "StorPool",
            "tags": "cloud-test-dev-1"
            }

        storpool_service_offerings = {
            "name": "cloud-test-dev-1",
                "displaytext": "SP_CO_2 (Min IOPS = 10,000; Max IOPS = 15,000)",
                "cpunumber": 1,
                "cpuspeed": 500,
                "memory": 512,
                "storagetype": "shared",
                "customizediops": False,
                "hypervisorsnapshotreserve": 200,
                "tags": "cloud-test-dev-1"
            }

        storage_pool = list_storage_pools(
            cls.apiclient,
            name='cloud-test-dev-1'
            )

        service_offerings = list_service_offering(
            cls.apiclient,
            name='cloud-test-dev-1'
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

        cls.services["domainid"] = cls.domain.id
        cls.services["small"]["zoneid"] = cls.zone.id
        cls.services["templates"]["ostypeid"] = template.ostypeid
        cls.services["zoneid"] = cls.zone.id


        cls.service_offering = service_offerings
        cls.debug(pprint.pformat(cls.service_offering))

        cls.volume_1 = Volume.create(
            cls.apiclient,
            {"diskname":"StorPoolDisk-1" },
            zoneid=cls.zone.id,
            diskofferingid=disk_offerings[0].id,
        )

        cls.volume_2 = Volume.create(
            cls.apiclient,
            {"diskname":"StorPoolDisk-2" },
            zoneid=cls.zone.id,
            diskofferingid=disk_offerings[0].id,
        )

        cls.virtual_machine = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%d" % random.randint(0, 100)},
            zoneid=cls.zone.id,
            templateid=template.id,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            rootdisksize=10
        )
        cls.random_data_0 = random_gen(size=100)
        cls.test_dir = "/tmp"
        cls.random_data = "random.data"
        cls._cleanup = []
        cls._cleanup.append(cls.virtual_machine)
        cls._cleanup.append(cls.volume_1)
        cls._cleanup.append(cls.volume_2)
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
    def test_01_attach_detach_volume_to_vm(self):
        ''' Test Attach Volume To Running Virtual Machine
        '''
        time.sleep(60)
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

        volume = self.virtual_machine.detach_volume(
            self.apiclient,
            self.volume_1
            )
        list_vm_volumes = Volume.list(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            id = volume.id
            )
        print(list_vm_volumes)
        self.assertIsNone(list_vm_volumes, "Is None")


    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_02_attach_detach_volume_to_stopped_vm(self):
        ''' Test Attach Volume To Stopped Virtual Machine
        '''
        virtual_machine = self.virtual_machine.stop(
            self.apiclient,
            forced=True
            )

        time.sleep(60)
        volume_2 = self.virtual_machine.attach_volume(
            self.apiclient,
            self.volume_2
            )
        list_vm_volumes = Volume.list(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            id= volume_2.id
            )
        print(list_vm_volumes)
        self.assertEqual(volume_2.id,list_vm_volumes[0].id, "Is true")

        time.sleep(90)
        volume_2 = self.virtual_machine.detach_volume(
            self.apiclient,
            self.volume_2
            )
        list_vm_volumes = Volume.list(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            id = volume_2.id
            )
        print(list_vm_volumes)
        self.assertIsNone(list_vm_volumes, "Is None")

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_03_resize_attached_volume(self):
        ''' Test Resize Volume  Attached To Virtual Machine
        '''
        #=======================================================================
        # list_volume_response = Volume.list(
        #     self.apiclient,
        #     id = self.volume_1.id
        #     )
        # volume =list_volume_response[0]
        # self.assertIsNotNone(lvolume, "Volume response is  None")
        #=======================================================================
        shrinkOk = False
        if self.volume_1.size > int((self.disk_offering_20.disksize) * (1024**3)):
            shrinkOk= True

        cmd = resizeVolume.resizeVolumeCmd()
        cmd.id = self.volume_1.id
        cmd.diskofferingid = self.disk_offering_20.id
        cmd.shrinkok = shrinkOk

        self.apiclient.resizeVolume(cmd)

        new_size = Volume.list(
            self.apiclient,
            id=self.volume_1.id
            )

        self.assertTrue(
            (new_size[0].size == int((self.disk_offering_20.disksize) * (1024**3))),
            "New size is not int((self.disk_offering_20) * (1024**3)"
            )
        self.volume_1 = new_size[0]
        shrinkOk = False
        if self.volume_1.size > int((self.disk_offering_100.disksize) * (1024**3)):
            shrinkOk= True

        cmd = resizeVolume.resizeVolumeCmd()
        cmd.id = self.volume_1.id
        cmd.diskofferingid = self.disk_offering_100.id
        cmd.shrinkok = shrinkOk

        self.apiclient.resizeVolume(cmd)
        new_size = Volume.list(
            self.apiclient,
            id=self.volume_1.id
            )

        self.assertTrue(
            (new_size[0].size == int((self.disk_offering_100.disksize) * (1024**3))),
            "New size is not int((self.disk_offering_20) * (1024**3)"
            )

        # return to small disk
        self.volume_1 = new_size[0]
        shrinkOk = False
        if self.volume_1.size > int((self.disk_offerings.disksize)* (1024**3)):
            shrinkOk= True

        cmd.diskofferingid = self.disk_offerings.id
        cmd.shrinkok = shrinkOk

        self.apiclient.resizeVolume(cmd)
        new_size = Volume.list(
            self.apiclient,
            id=self.volume_1.id
            )
        self.assertTrue(
            (new_size[0].size == int((self.disk_offerings.disksize)*(1024**3))),
            "Could not return to Small disk"
            )

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_04_resize_detached_volume(self):
        ''' Test Resize Volume Detached To Virtual Machine
        '''
        list_vm_volumes = Volume.list(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            id= self.volume_2.id
            )
        #check that the volume is not attached to VM
        self.assertIsNone(list_vm_volumes, "List volumes is not None")

        shrinkOk = False
        if self.volume_2.size > int((self.disk_offering_20.disksize) * (1024**3)):
            shrinkOk= True

        cmd = resizeVolume.resizeVolumeCmd()
        cmd.id = self.volume_2.id
        cmd.diskofferingid = self.disk_offering_20.id
        cmd.shrinkok = shrinkOk

        self.apiclient.resizeVolume(cmd)

        new_size = Volume.list(
            self.apiclient,
            id=self.volume_2.id
            )

        self.assertTrue(
            (new_size[0].size == int((self.disk_offering_20.disksize) * (1024**3))) , 
            "New size is not int((self.disk_offering_20) * (1024**3)"
            )
        self.volume_2 = new_size[0]
        shrinkOk = False
        if self.volume_2.size > int((self.disk_offering_100.disksize) * (1024**3)):
            shrinkOk= True

        cmd = resizeVolume.resizeVolumeCmd()
        cmd.id = self.volume_2.id
        cmd.diskofferingid = self.disk_offering_100.id
        cmd.shrinkok = shrinkOk

        self.apiclient.resizeVolume(cmd)
        new_size = Volume.list(
            self.apiclient,
            id=self.volume_2.id
            )

        self.assertTrue(
            (new_size[0].size == int((self.disk_offering_100.disksize) * (1024**3))), 
            "New size is not int((self.disk_offering_20) * (1024**3)"
            )

        # return to small disk
        self.volume_2 = new_size[0]
        shrinkOk = False
        if self.volume_2.size > int((self.disk_offerings.disksize)* (1024**3)):
            shrinkOk= True

        cmd.diskofferingid = self.disk_offerings.id
        cmd.shrinkok = shrinkOk

        self.apiclient.resizeVolume(cmd)
        new_size = Volume.list(
            self.apiclient,
            id=self.volume_2.id
            )
        self.assertTrue(
            (new_size[0].size == int((self.disk_offerings.disksize)*(1024**3))),
            "Could not return to Small disk"
            )

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_05_snapshot_to_volume(self):
        ''' Create volume from snapshot
        '''
        snapshot = Snapshot.create(
            self.apiclient,
            volume_id = self.volume_2.id
            )

        self.assertIsNotNone(snapshot, "Could not create snapshot")
        self.assertIsInstance(snapshot, Snapshot, "Snapshot is not an instance of Snapshot")

        volume = self.create_volume(
            self.apiclient,
            zoneid = self.zone.id,
            snapshotid = snapshot.id
            )

        self._cleanup.append(volume)
        self._cleanup.append(snapshot)
        self.assertIsNotNone(volume, "Could not create volume from snapshot")
        self.assertIsInstance(volume, Volume, "Volume is not instance of Volume")


    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_06_snapshot_to_template(self):
        ''' Create template from snapshot
        '''
        snapshot = Snapshot.create(
           self.apiclient,
            volume_id = self.volume_2.id
            )

        self.assertIsNotNone(snapshot, "Could not create snapshot")
        self.assertIsInstance(snapshot, Snapshot, "Snapshot is not an instance of Snapshot")
        
        template = self.create_template_from_snapshot(
            self.apiclient,
            self.services,
            snapshotid = snapshot.id
            )
        

        self.assertIsNotNone(template, "Template is None")
        self.assertIsInstance(template, Template, "Template is instance of template")
        self._cleanup.append(snapshot)
        self._cleanup.append(template)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_07_snapshot_to_template_bypass_secondary(self):
        ''' Create template from snapshot bypassing secondary storage
        '''
        ##cls.virtual_machine
        volume = list_volumes(
                        self.apiclient,
                        virtualmachineid = self.virtual_machine.id
                        )
        snapshot = Snapshot.create(
           self.apiclient,
            volume_id = volume[0].id
            )

        backup_config = list_configurations(
            self.apiclient, 
            name = "sp.bypass.secondary.storage" )
        if (backup_config[0].value == "false"):
            backup_config = Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage", 
            value = "true")
        self.assertIsNotNone(snapshot, "Could not create snapshot")
        self.assertIsInstance(snapshot, Snapshot, "Snapshot is not an instance of Snapshot")
        
        template = self.create_template_from_snapshot(
            self.apiclient,
            self.services,
            snapshotid = snapshot.id
            )
        virtual_machine = VirtualMachine.create(self.apiclient,
            {"name":"StorPool-%d" % random.randint(0, 100)},
            zoneid=self.zone.id,
            templateid=template.id,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
            )
        ssh_client = virtual_machine.get_ssh_client()
        self.assertIsNotNone(template, "Template is None")
        self.assertIsInstance(template, Template, "Template is instance of template")
        self._cleanup.append(snapshot)
        self._cleanup.append(template)
    @classmethod
    def create_volume(self, apiclient, zoneid=None, snapshotid=None):
        """Create Volume"""
        cmd = createVolume.createVolumeCmd()
        cmd.name = "Test"

        if zoneid:
            cmd.zoneid = zoneid

        if snapshotid:
            cmd.snapshotid = snapshotid
        return Volume(apiclient.createVolume(cmd).__dict__)
    
    @classmethod
    def create_template_from_snapshot(self, apiclient, services, snapshotid=None):
        """Create template from Volume"""
        # Create template from Virtual machine and Volume ID
        cmd = createTemplate.createTemplateCmd()
        cmd.displaytext = "StorPool_Template"
        cmd.name = "-".join(["StorPool-", random_gen()])
        if "ostypeid" in services:
            cmd.ostypeid = services["ostypeid"]
        elif "ostype" in services:
            # Find OSTypeId from Os type
            sub_cmd = listOsTypes.listOsTypesCmd()
            sub_cmd.description = services["ostype"]
            ostypes = apiclient.listOsTypes(sub_cmd)

            if not isinstance(ostypes, list):
                raise Exception(
                    "Unable to find Ostype id with desc: %s" %
                    services["ostype"])
            cmd.ostypeid = ostypes[0].id
        else:
            raise Exception(
                "Unable to find Ostype is required for creating template")

        cmd.isfeatured = True
        cmd.ispublic = True
        cmd.isextractable =  False

        if snapshotid:
            cmd.snapshotid = snapshotid

        return Template(apiclient.createTemplate(cmd).__dict__)