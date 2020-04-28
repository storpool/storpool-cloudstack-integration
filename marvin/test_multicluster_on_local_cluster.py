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
                             Cluster,
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
                               list_hosts,
                               list_snapshots,
                               list_storage_pools,
                               list_volumes,
                               list_virtual_machines,
                               list_configurations,
                               list_service_offering,
                               list_clusters)
from marvin.cloudstackAPI import (listOsTypes,
                                  listTemplates,
                                  listHosts,
                                  createTemplate,
                                  createVolume,
                                  resizeVolume,
                                  getVolumeSnapshotDetails)
import time
import pprint
import random
import subprocess
from storpool import spapi
from marvin.configGenerator import configuration
import uuid
from __builtin__ import True

class TestStoragePool(cloudstackTestCase):

    @classmethod
    def setUpClass(cls):
        cls.spapi = spapi.Api.fromConfig(multiCluster=True)

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

        storpool_service_offerings_ssd = {
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

        storpool_service_offerings_ssd2 = {
            "name": "ssd2",
                "displaytext": "SP_CO_2 (Min IOPS = 10,000; Max IOPS = 15,000)",
                "cpunumber": 1,
                "cpuspeed": 500,
                "memory": 512,
                "storagetype": "shared",
                "customizediops": False,
                "hypervisorsnapshotreserve": 200,
                "tags": "ssd2"
            }

        storage_pool = list_storage_pools(
            cls.apiclient,
            name='ssd'
            )

        storage_pool2 = list_storage_pools(
            cls.apiclient,
            name='ssd2'
            )
        cls.primary_storage = storage_pool[0]
        cls.primary_storage2 = storage_pool2[0]

        service_offerings_ssd = list_service_offering(
            cls.apiclient,
            name='ssd'
            )

        service_offerings_ssd2 = list_service_offering(
            cls.apiclient,
            name='ssd2'
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

        if service_offerings_ssd is None:
            service_offerings_ssd = ServiceOffering.create(cls.apiclient, storpool_service_offerings_ssd)
        else:
            service_offerings_ssd = service_offerings_ssd[0]

        if service_offerings_ssd2 is None:
            service_offerings_ssd2 = ServiceOffering.create(cls.apiclient, storpool_service_offerings_ssd2)
        else:
            service_offerings_ssd2 = service_offerings_ssd2[0]

        #The version of CentOS has to be supported
        template = get_template(
             cls.apiclient,
            cls.zone.id,
            account = "system"
        )

        cls.local_cluster = cls.get_local_cluster()
        cls.host = cls.list_hosts_by_cluster_id(cls.local_cluster.id)

        cls.debug(pprint.pformat(template))
        cls.debug(pprint.pformat(cls.hypervisor))

        if template == FAILED:
            assert False, "get_template() failed to return template\
                    with description %s" % cls.services["ostype"]

        cls.services["domainid"] = cls.domain.id
        cls.services["small"]["zoneid"] = cls.zone.id
        cls.services["templates"]["ostypeid"] = template.ostypeid
        cls.services["zoneid"] = cls.zone.id


        cls.service_offering = service_offerings_ssd
        cls.service_offering_ssd2 = service_offerings_ssd2
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

        cls.volume = Volume.create(
            cls.apiclient,
            {"diskname":"StorPoolDisk-3" },
            zoneid=cls.zone.id,
            diskofferingid=disk_offerings[0].id,
        )

        cls.virtual_machine = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
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
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            hostid = cls.host[0].id,
            rootdisksize=10
        )

        cls.vm_migrate = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            hostid = cls.host[0].id,
            rootdisksize=10
        )

        cls.vm_cluster = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            hostid = cls.host[0].id,
            rootdisksize=10
        )

        cls.template = template
        cls.hostid = cls.virtual_machine.hostid
        cls.random_data_0 = random_gen(size=100)
        cls.test_dir = "/tmp"
        cls.random_data = "random.data"
        cls._cleanup = []
        cls._cleanup.append(cls.virtual_machine)
        cls._cleanup.append(cls.virtual_machine2)
        cls._cleanup.append(cls.vm_migrate)
        cls._cleanup.append(cls.vm_cluster)
        cls._cleanup.append(cls.volume_1)
        cls._cleanup.append(cls.volume_2)
        return

    @classmethod
    def tearDownClass(cls):
        try:
            clusters = Cluster.list(cls.apiclient, allocationstate = "Disabled")
            if clusters is not None:
                for c in clusters:
                    cluster = Cluster.update(
                    cls.apiclient,
                    id = c.id,
                    allocationstate = "Enabled"
                    )
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

    @classmethod
    def get_local_cluster(self):
       storpool_clusterid = subprocess.check_output(['storpool_confshow', 'CLUSTER_ID'])
       self.debug(storpool_clusterid)
       clusters = list_clusters(self.apiclient)
       for c in clusters:
           configuration = list_configurations(
               self.apiclient,
               clusterid = c.id
               )
           if configuration[0].name == 'sp.cluster.id'  and configuration[0].value == storpool_clusterid:
               return c

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_01_attach_detach_volume_to_running_vm(self):
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

        name = list_vm_volumes[0].path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
        except spapi.ApiError as err:
           raise Exception(err)

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
    def test_02_resize_root_volume_on_working_vm(self):
        ''' Test Resize Root volume on Running Virtual Machine
        '''
        self.assertEqual(VirtualMachine.RUNNING, self.virtual_machine2.state, "Running")
        volume = list_volumes(
            self.apiclient,
            virtualmachineid = self.virtual_machine2.id,
            type = "ROOT"
            )
        volume = volume[0]

        name = volume.path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
            if spvolume[0].size != volume.size:
                raise Exception("Storpool volume size is not the same as CloudStack db size")
        except spapi.ApiError as err:
           raise Exception(err)

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
            id=volume.id
            )

        self.assertTrue(
            (new_size[0].size == int((self.disk_offering_20.disksize) * (1024**3))),
            "New size is not int((self.disk_offering_20) * (1024**3)"
            )
        volume = new_size[0]

        name = volume.path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
            if spvolume[0].size != volume.size:
                raise Exception("Storpool volume size is not the same as CloudStack db size")
        except spapi.ApiError as err:
           raise Exception(err)

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
            id=volume.id
            )

        volume = new_size[0]

        name = volume.path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
            if spvolume[0].size != volume.size:
                raise Exception("Storpool volume size is not the same as CloudStack db size")
        except spapi.ApiError as err:
           raise Exception(err)

        self.assertTrue(
            (new_size[0].size == int((self.disk_offering_100.disksize) * (1024**3))),
            "New size is not int((self.disk_offering_20) * (1024**3)"
            )

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_03_resize_attached_volume_on_working_vm(self):
        ''' Test Resize Volume  Attached To Running Virtual Machine
        '''
        self.assertEqual(VirtualMachine.RUNNING, self.virtual_machine.state, "Running")
        volume = self.virtual_machine.attach_volume(
            self.apiclient,
            self.volume_1
            )

        listvol = Volume.list(
            self.apiclient,
            id=volume.id
            )
        name = listvol[0].path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
            if spvolume[0].size != listvol[0].size:
                raise Exception("Storpool volume size is not the same as CloudStack db size")
        except spapi.ApiError as err:
           raise Exception(err)

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
            id=volume.id
            )

        self.assertTrue(
            (new_size[0].size == int((self.disk_offering_20.disksize) * (1024**3))),
            "New size is not int((self.disk_offering_20) * (1024**3)"
            )
        volume = new_size[0]

        name = volume.path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
            if spvolume[0].size != volume.size:
                raise Exception("Storpool volume size is not the same as CloudStack db size")
        except spapi.ApiError as err:
           raise Exception(err)

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
            id=volume.id
            )

        self.assertTrue(
            (new_size[0].size == int((self.disk_offering_100.disksize) * (1024**3))),
            "New size is not int((self.disk_offering_20) * (1024**3)"
            )

        # return to small disk
        volume = new_size[0]

        name = volume.path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
            if spvolume[0].size != volume.size:
                raise Exception("Storpool volume size is not the same as CloudStack db size")
        except spapi.ApiError as err:
           raise Exception(err)

        shrinkOk = False
        if volume.size > int((self.disk_offerings.disksize)* (1024**3)):
            shrinkOk= True

        cmd.diskofferingid = self.disk_offerings.id
        cmd.shrinkok = shrinkOk

        self.apiclient.resizeVolume(cmd)
        new_size = Volume.list(
            self.apiclient,
            id=volume.id
            )

        volume = new_size[0]

        name = volume.path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
            if spvolume[0].size != volume.size:
                raise Exception("Storpool volume size is not the same as CloudStack db size")
        except spapi.ApiError as err:
           raise Exception(err)

        self.assertTrue(
            (new_size[0].size == int((self.disk_offerings.disksize)*(1024**3))),
            "Could not return to Small disk"
            )


    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_04_attach_detach_volume_to_stopped_vm(self):
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

        name = list_vm_volumes[0].path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
        except spapi.ApiError as err:
           raise Exception(err)

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
    def test_05_resize_attached_volume(self):
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

        name = self.volume_1.path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
            if spvolume[0].size != self.volume_1.size:
                raise Exception("Storpool volume size is not the same as CloudStack db size")
        except spapi.ApiError as err:
           raise Exception(err)

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

        name = self.volume_1.path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
            if spvolume[0].size != self.volume_1.size:
                raise Exception("Storpool volume size is not the same as CloudStack db size")
        except spapi.ApiError as err:
           raise Exception(err)

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

        name = new_size[0].path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
            if spvolume[0].size != new_size[0].size:
                raise Exception("Storpool volume size is not the same as CloudStack db size")
        except spapi.ApiError as err:
           raise Exception(err)
        self.assertTrue(
            (new_size[0].size == int((self.disk_offerings.disksize)*(1024**3))),
            "Could not return to Small disk"
            )

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_06_resize_detached_volume(self):
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
            (new_size[0].size == int((self.disk_offering_20.disksize) * (1024**3))),
            "New size is not int((self.disk_offering_20) * (1024**3)"
            )
        self.volume_2 = new_size[0]

        name = self.volume_2.path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
            if spvolume[0].size != self.volume_2.size:
                raise Exception("Storpool volume size is not the same as CloudStack db size")
        except spapi.ApiError as err:
           raise Exception(err)

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

        name = self.volume_2.path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
            if spvolume[0].size != self.volume_2.size:
                raise Exception("Storpool volume size is not the same as CloudStack db size")
        except spapi.ApiError as err:
           raise Exception(err)

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

        name = new_size[0].path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
            if spvolume[0].size != new_size[0].size:
                raise Exception("Storpool volume size is not the same as CloudStack db size")
        except spapi.ApiError as err:
           raise Exception(err)

        self.assertTrue(
            (new_size[0].size == int((self.disk_offerings.disksize)*(1024**3))),
            "Could not return to Small disk"
            )

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_07_snapshot_to_volume(self):
        ''' Create volume from snapshot
        '''
        snapshot = Snapshot.create(
            self.apiclient,
            volume_id = self.volume_2.id
            )

        try:
            cmd = getVolumeSnapshotDetails.getVolumeSnapshotDetailsCmd()
            cmd.snapshotid = snapshot.id
            snapshot_details = self.apiclient.getVolumeSnapshotDetails(cmd)
            flag = False
            for s in snapshot_details:
                if s["snapshotDetailsName"] == snapshot.id:
                    name = s["snapshotDetailsValue"].split("/")[3]
                    sp_snapshot = self.spapi.snapshotList(snapshotName = "~" + name)
                    self.debug('################ %s' % sp_snapshot)
                    flag = True
            if flag == False:
                raise Exception("Could not find snapshot in snapshot details")
        except spapi.ApiError as err:
           raise Exception(err)

        self.assertIsNotNone(snapshot, "Could not create snapshot")
        self.assertIsInstance(snapshot, Snapshot, "Snapshot is not an instance of Snapshot")

        volume = self.create_volume(
            self.apiclient,
            zoneid = self.zone.id,
            snapshotid = snapshot.id
            )

        listvol = Volume.list(
            self.apiclient,
            id=volume.id
            )
        name = listvol[0].path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
        except spapi.ApiError as err:
           raise Exception(err)

        self._cleanup.append(volume)
        self._cleanup.append(snapshot)
        self.assertIsNotNone(volume, "Could not create volume from snapshot")
        self.assertIsInstance(volume, Volume, "Volume is not instance of Volume")

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_08_snapshot_detached_volume(self):
        ''' Test Snapshot Detached Volume
        '''
        self.virtual_machine.stop(
            self.apiclient,
            forced = True
            )
        self.volume = self.virtual_machine.attach_volume(
            self.apiclient,
            self.volume
            )
        self.assertIsNotNone(self.volume, "Attach: Is none")
        self.volume = self.virtual_machine.detach_volume(
            self.apiclient,
            self.volume
            )

        self.assertIsNotNone(self.volume, "Detach: Is none")
 
        snapshot = Snapshot.create(
            self.apiclient,
            self.volume.id,
            )

        try:
            cmd = getVolumeSnapshotDetails.getVolumeSnapshotDetailsCmd()
            cmd.snapshotid = snapshot.id
            snapshot_details = self.apiclient.getVolumeSnapshotDetails(cmd)
            flag = False
            for s in snapshot_details:
                if s["snapshotDetailsName"] == snapshot.id:
                    name = s["snapshotDetailsValue"].split("/")[3]
                    sp_snapshot = self.spapi.snapshotList(snapshotName = "~" + name)
                    self.debug('################ %s' % sp_snapshot)
                    flag = True
            if flag == False:
                raise Exception("Could not find snapshot in snapshot details")
        except spapi.ApiError as err:
           raise Exception(err)

        self.assertIsNotNone(snapshot, "Snapshot is None")

        self.assertIsInstance(snapshot, Snapshot, "Snapshot is not Instance of Snappshot")

        snapshot = Snapshot.delete(
            snapshot,
            self.apiclient
            )

        self.assertIsNone(snapshot, "Snapshot was not deleted")

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_09_snapshot_root_disk(self):
        ''' Test ROOT Disk Snapshot 
        '''
        vm = VirtualMachine.create(self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid = self.zone.id,
            templateid = self.template.id,
            serviceofferingid = self.service_offering.id,
            hypervisor = self.hypervisor,
            hostid = self.host[0].id,
            rootdisksize = 10
            )
        list_volumes_of_vm = list_volumes(
            self.apiclient,
            virtualmachineid = vm.id
            )
        self.assertIs(len(list_volumes_of_vm), 1, "VM has more disk than 1")

        snapshot = Snapshot.create(
            self.apiclient,
            list_volumes_of_vm[0].id
            )

        try:
            cmd = getVolumeSnapshotDetails.getVolumeSnapshotDetailsCmd()
            cmd.snapshotid = snapshot.id
            snapshot_details = self.apiclient.getVolumeSnapshotDetails(cmd)
            flag = False
            for s in snapshot_details:
                if s["snapshotDetailsName"] == snapshot.id:
                    name = s["snapshotDetailsValue"].split("/")[3]
                    sp_snapshot = self.spapi.snapshotList(snapshotName = "~" + name)
                    self.debug('################ %s' % sp_snapshot)
                    flag = True
            if flag == False:
                raise Exception("Could not find snapshot in snapshot details")
        except spapi.ApiError as err:
           raise Exception(err)

        self.assertIsNotNone(snapshot, "Snapshot is None")

        self.assertEqual(list_volumes_of_vm[0].id, snapshot.volumeid, "Snapshot is not for the same volume")

        self._cleanup.append(snapshot)
        self._cleanup.append(vm)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_10_volume_to_template(self):
        ''' Create Template From ROOT Volume
        '''
        volume = Volume.list(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            type = "ROOT"
            )

        self.virtual_machine.stop(self.apiclient)

        template = self.create_template_from_snapshot(
            self.apiclient,
            self.services,
            volumeid = volume[0].id
            )

        virtual_machine = VirtualMachine.create(self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=template.id,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
            )
        ssh_client = virtual_machine.get_ssh_client()
        self.assertIsNotNone(template, "Template is None")
        self.assertIsInstance(template, Template, "Template is instance of template")
        self._cleanup.append(template)
        self._cleanup.append(virtual_machine)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_11_migrate_vm_to_another_storage(self):
        ''' Migrate VM to another Primary Storage
        '''
        list_volumes_of_vm = list_volumes(
            self.apiclient,
            virtualmachineid = self.vm_migrate.id
            )

        self.assertTrue(len(list_volumes_of_vm) == 1, "There are more volumes attached to VM")

        if list_volumes_of_vm[0].storageid is self.primary_storage.id:
            cmd = migrateVirtualMachine.migrateVirtualMachineCmd()
            cmd.virtualmachineid = self.vm_migrate.id
            if hostid:
                cmd.hostid = hostid
            vm =   apiclient.migrateVirtualMachine(cmd)
            volume = list_volumes(
                self.apiclient,
                virtualmachineid = vm.id
                )[0]
            self.assertNotEqual(volume.storageid, self.primary_storage.id, "Could not migrate VM")

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_12_migrate_volume_to_another_storage(self):
        ''' Migrate Volume To Another Primary Storage
        '''
        self.assertFalse(hasattr(self.volume, 'virtualmachineid') , "Volume is not detached")

        self.assertFalse(hasattr(self.volume, 'storageid') , "Volume is not detached")
        volume = Volume.migrate(
            self.apiclient,
            volumeid = self.volume.id,
            storageid = self.primary_storage2.id
            )

        self.assertIsNotNone(volume, "Volume is None")

        self.assertEqual(volume.storageid, self.primary_storage2.id, "Storage is the same")

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_13_create_vm_on_another_storpool_storage(self):
        """ Create Virtual Machine on another StorPool primary StoragePool"""
        virtual_machine = VirtualMachine.create(self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=self.template.id,
            serviceofferingid=self.service_offering_ssd2.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
            )
        self.assertIsNotNone(virtual_machine, "Could not create virtual machine on another Storpool primary storage")
        self._cleanup.append(virtual_machine)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_14_create_vm_on_second_cluster_with_template_from_first(self):
        """ Create Virtual Machine On Working Cluster With Template Created on Another """
        volume = Volume.list(
            self.apiclient,
            virtualmachineid = self.vm_cluster.id,
            type = "ROOT"
            )

        snapshot = Snapshot.create(
            self.apiclient, 
            volume[0].id
            )

        template = self.create_template_from_snapshot(
            self.apiclient,
            self.services,
            snapshotid = snapshot.id
            )

        cluster = Cluster.update(
            self.apiclient,
            id = self.local_cluster.id,
            allocationstate = "Disabled"
            )

        virtual_machine = VirtualMachine.create(self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=template.id,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
            )
        ssh_client = virtual_machine.get_ssh_client()

        cluster = Cluster.update(
            self.apiclient,
            id = self.local_cluster.id,
            allocationstate = "Enabled"
            )
        self._cleanup.append(virtual_machine)
        self._cleanup.append(template)
        self._cleanup.append(snapshot)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_15_snapshot_to_volume_of_root_disk(self):
        ''' Create volume from snapshot
        '''
        virtual_machine = VirtualMachine.create(self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=self.template.id,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
            )
        volume1 = list_volumes(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            type = "ROOT"
            )
        snapshot = Snapshot.create(
            self.apiclient,
            volume_id = volume1[0].id
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
        self._cleanup.append(virtual_machine)
        self.assertIsNotNone(volume, "Could not create volume from snapshot")
        self.assertIsInstance(volume, Volume, "Volume is not instance of Volume")

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_16_download_volume(self):
        vol = self.volume.extract(
            self.apiclient,
            volume_id = self.volume.id,
            zoneid = self.zone.id,
            mode = "HTTP_DOWNLOAD"
            )
        self.assertIsNotNone(vol, "Volume is None")
        self.assertIsNotNone(vol.url, "No URL provided")

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_17_create_vm_from_template_not_on_storpool(self):
        ''' Create virtual machine from template which for some reason is deleted from StorPool, but exists in template_spoool_ref DB tables '''

        volume = Volume.list(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            type = "ROOT"
            )

        self.virtual_machine.stop(self.apiclient)

        template = self.create_template_from_snapshot(
            self.apiclient,
            self.services,
            volumeid = volume[0].id
            )

        virtual_machine = VirtualMachine.create(self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=template.id,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
            )
        ssh_client = virtual_machine.get_ssh_client(reconnect= True)
        name = 'ssd-' + template.id
        flag = False
        storpoolGlId = None

        sp_snapshots = self.spapi.snapshotsList()
        for snap in sp_snapshots:
            tags = snap.tags
            for t in tags:
                if tags[t] == template.id:
                    storpoolGlId = snap.globalId
                    flag = True
                    break
            else:
                continue
            break

        if flag is False:
            try:
                sp_snapshot = self.spapi.snapshotList(snapshotName = name)
            except spapi.ApiError as err:
                raise Exception(err)


        self.spapi.snapshotDelete(snapshotName ="~" + storpoolGlId)

        virtual_machine2 = VirtualMachine.create(self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=template.id,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
            )

        ssh_client = virtual_machine2.get_ssh_client(reconnect= True)
        self.assertIsNotNone(template, "Template is None")
        self.assertIsInstance(template, Template, "Template is instance of template")
        self._cleanup.append(template)
        self._cleanup.append(virtual_machine)
        self._cleanup.append(virtual_machine2)
        
        

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
    def create_template_from_snapshot(self, apiclient, services, snapshotid=None, volumeid=None):
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
        if volumeid:
            cmd.volumeid = volumeid
        return Template(apiclient.createTemplate(cmd).__dict__)

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


    def start(cls, vmid, hostid):
        """Start the instance"""
        cmd = startVirtualMachine.startVirtualMachineCmd()
        cmd.id = vmid
        cmd.hostid = hostid
        return (cls.apiclient.startVirtualMachine(cmd))

#     @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
#     def test_10_start_vm_to_another_host(self):
#         ''' Start VM to another host
#         '''
#         hosts = list_hosts(
#             self.apiclient,
#             type = "Routing",
#             state = "Up")
#  
#         for h in hosts:
#             if h.id is not self.hostid:
#                 VirtualMachine.start(self.apiclient,
#                                      id = self.virtual_machine.id,
#                                      hostid = h.id
#                                      )
           