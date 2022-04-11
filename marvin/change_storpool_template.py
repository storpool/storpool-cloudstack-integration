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
                             Volume,
                             SecurityGroup,
                             ResourceDetails,
                             DiskOffering,
                             )
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
                               list_clusters,
                               list_zones)
from marvin.cloudstackAPI import (listOsTypes,
                                  listTemplates,
                                  listHosts,
                                  createTemplate,
                                  createVolume,
                                  resizeVolume,
                                  getVolumeSnapshotDetails,
                                  migrateVirtualMachine)
import time
import pprint
import random
import subprocess
from storpool import spapi
from marvin.configGenerator import configuration
import uuid
from sp_util import (TestData, StorPoolHelper)
import time

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
        cls._cleanup = []
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
        cls.zone = None

        zones = list_zones(cls.apiclient)

        for z in zones:
            if z.internaldns1 == cls.getClsConfig().mgtSvr[0].mgtSvrIp:
                cls.zone = z

        cls.debug("##################### zone %s" % cls.zone)
        td = TestData()
        cls.testdata = td.testdata
        cls.helper = StorPoolHelper()

        storpool_primary_storage = {
                "name": "ssd",
                TestData.scope: "ZONE",
                "url": "ssd",
                TestData.provider: "StorPool",
                "path": "/dev/storpool",
                TestData.capacityBytes: 2251799813685248,
                TestData.hypervisor: "KVM"
            }

        storpool_without_qos = {
                "name": "ssd",
                "displaytext": "ssd",
                "cpunumber": 1,
                "cpuspeed": 500,
                "memory": 512,
                "storagetype": "shared",
                "customizediops": False,
                "hypervisorsnapshotreserve": 200,
                "tags": "ssd"
            }

        storpool_qos_template = {
                "name": "qos",
                "displaytext": "qos",
                "cpunumber": 1,
                "cpuspeed": 500,
                "memory": 512,
                "storagetype": "shared",
                "customizediops": False,
                "hypervisorsnapshotreserve": 200,
                "tags": "ssd"
            }

        disk_offering_ssd = {
                "name": "ssd",
                "displaytext": "SP_DO_1 (5GB Min IOPS = 300; Max IOPS = 500)",
                "disksize": 10,
                "customizediops": False,
                "hypervisorsnapshotreserve": 200,
                TestData.tags: "ssd",
                "storagetype": "shared"
            }

        disk_offering_qos = {
                "name": "qos",
                "displaytext": "SP_DO_1 (5GB Min IOPS = 300; Max IOPS = 500)",
                "disksize": 10,
                "customizediops": False,
                "hypervisorsnapshotreserve": 200,
                TestData.tags: "ssd",
                "storagetype": "shared"
            }

        cls.template_name = storpool_primary_storage.get("name")

        cls.template_name_2 = "qos"

        storage_pool = list_storage_pools(
            cls.apiclient,
            name = "ssd"
            )
        cls.primary_storage = storage_pool[0]

        if storage_pool is None:
            storage_pool = StoragePool.create(cls.apiclient, storpool_primary_storage)
        else:
            storage_pool = storage_pool[0]
        cls.storage_pool = storage_pool
        cls.debug(pprint.pformat(storage_pool))

        service_offerings_ssd = list_service_offering(
            cls.apiclient,
            name = cls.template_name
            )

        service_offerings_qos = list_service_offering(
            cls.apiclient,
            name = cls.template_name_2
            )

        if service_offerings_ssd is None:
            service_offerings_ssd = ServiceOffering.create(cls.apiclient, storpool_without_qos)
        else:
            service_offerings_ssd = service_offerings_ssd[0]

        if service_offerings_qos is None:
            service_offerings_qos = ServiceOffering.create(cls.apiclient, storpool_qos_template)
            ResourceDetails.create(cls.apiclient, resourceid=service_offerings_qos.id, resourcetype="ServiceOffering", details={"SP_TEMPLATE" : "qos"}, fordisplay=True)

        else:
            service_offerings_qos = service_offerings_qos[0]

        cls.service_offering_ssd = service_offerings_ssd
        cls.service_offering_qos = service_offerings_qos

        cls.disk_offering_ssd = list_disk_offering(cls.apiclient, name = cls.template_name)
        cls.disk_offering_qos = list_disk_offering(cls.apiclient, name = cls.template_name_2)

        if cls.disk_offering_ssd is None:
            cls.disk_offering_ssd = DiskOffering.create(cls.apiclient, disk_offering_ssd)
        else:
            cls.disk_offering_ssd = cls.disk_offering_ssd[0]

        if cls.disk_offering_qos is None:
            cls.disk_offering_qos = DiskOffering.create(cls.apiclient, disk_offering_qos)
            ResourceDetails.create(cls.apiclient, resourceid=cls.disk_offering_qos.id, resourcetype="DiskOffering", details={"SP_TEMPLATE" : "qos"}, fordisplay=True)
        else:
            cls.disk_offering_qos = cls.disk_offering_qos[0]

        #The version of CentOS has to be supported
        template = get_template(
             cls.apiclient,
            cls.zone.id,
            account = "system"
        )

        if template == FAILED:
            assert False, "get_template() failed to return template\
                    with description %s" % cls.services["ostype"]

        cls.services["domainid"] = cls.domain.id
        cls.services["small"]["zoneid"] = cls.zone.id
        cls.services["templates"]["ostypeid"] = template.ostypeid
        cls.services["zoneid"] = cls.zone.id
        cls.services["diskofferingid"] = cls.disk_offering_ssd.id


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

        cls.volume_1 = Volume.create(
            cls.apiclient,
           cls.services,
           account=cls.account.name,
           domainid=cls.account.domainid
        )

        cls.volume_2 = Volume.create(
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
            serviceofferingid=cls.service_offering_ssd.id,
            hypervisor=cls.hypervisor,
            rootdisksize=10
        )
        cls.virtual_machine.attach_volume(
            cls.apiclient,
            cls.volume_1
            )

        cls.virtual_machine.attach_volume(
            cls.apiclient,
            cls.volume_2
            )

        cls.template = template
        cls.hostid = cls.virtual_machine.hostid

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

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_01_resize_volume_to_qos_offering(self):

        Volume.resize(self.volume_1, self.apiclient, diskofferingid=self.disk_offering_qos.id)

        volume = Volume.list(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            id=self.volume_1.id,
            listall= True
            )[0]

        name = volume.path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
            self.debug("#################### volumes %s" % spvolume)
            if spvolume[0].templateName != "qos":
                raise Exception("StorPool volume was not migrated to the QoS template")
            else:
                self.debug("Volume was migrate to the new qos template")
        except spapi.ApiError as err:
           raise Exception(err)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_02_scale_vm_to_qos_offering(self):
        self.virtual_machine.stop(self.apiclient, forced=True)

        volume = Volume.list(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            type = "ROOT",
            listall= True
            )[0]

        self.debug("Volume disk offerings %s" % volume.serviceofferingid)
        self.debug("Service offerings %s" % self.service_offering_ssd.id)

        self.assertEqual(volume.serviceofferingid, self.service_offering_ssd.id, "Offerings are not the same")

        self.virtual_machine.scale(self.apiclient, serviceOfferingId = self.service_offering_qos.id,)
        self.virtual_machine.start(self.apiclient)

        volume = Volume.list(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            type = "ROOT",
            listall= True
            )[0]

        self.assertEqual(volume.serviceofferingid, self.service_offering_qos.id, "Offerings are not the same")

        time.sleep(60)
        name = volume.path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
            self.debug("#################### volumes %s" % spvolume)
            if spvolume[0].templateName != "qos":
                raise Exception("StorPool volume was not migrated to the QoS template")
            else:
                self.debug("Volume was migrate to the new qos template")
        except spapi.ApiError as err:
           raise Exception(err)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_03_create_vm_snapshots(self):
        """Test to create VM snapshots
        """
        time.sleep(60)
        try:
            # Login to VM and write data to file system
            ssh_client = self.virtual_machine.get_ssh_client(reconnect=True, retries=30)

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
                      self.virtual_machine.ipaddress)
        self.assertEqual(
            self.random_data_0,
            result[0],
            "Check the random data has be write into temp file!"
        )

        time.sleep(30)
        MemorySnapshot = False
        vm_snapshot = VmSnapshot.create(
            self.apiclient,
            self.virtual_machine.id,
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
    def test_04_revert_vm_snapshots(self):
        """Test to revert VM snapshots
        """

        try:
            ssh_client = self.virtual_machine.get_ssh_client(reconnect=True)

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
                      self.virtual_machine.ipaddress)

        if str(result[0]).index("No such file or directory") == -1:
            self.fail("Check the random data has be delete from temp file!")

        time.sleep(30)

        list_snapshot_response = VmSnapshot.list(
            self.apiclient,
            virtualmachineid=self.virtual_machine.id,
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

        self.virtual_machine.stop(self.apiclient, forced=True)

        VmSnapshot.revertToSnapshot(
            self.apiclient,
            list_snapshot_response[0].id
            )

        self.virtual_machine.start(self.apiclient)

        try:
            ssh_client = self.virtual_machine.get_ssh_client(reconnect=True)

            cmds = [
                "cat %s/%s" % (self.test_dir, self.random_data)
            ]

            for c in cmds:
                self.debug(c)
                result = ssh_client.execute(c)
                self.debug(result)

        except Exception:
            self.fail("SSH failed for Virtual machine: %s" %
                      self.virtual_machine.ipaddress)

        self.assertEqual(
            self.random_data_0,
            result[0],
            "Check the random data is equal with the ramdom file!"
        )

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_05_delete_vm_snapshots(self):
        """Test to delete vm snapshots
        """

        list_snapshot_response = VmSnapshot.list(
            self.apiclient,
            virtualmachineid=self.virtual_machine.id,
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
            virtualmachineid=self.virtual_machine.id,
            listall=False)
        self.debug('list_snapshot_response -------------------- %s' % list_snapshot_response)

        self.assertIsNone(list_snapshot_response, "snapshot is already deleted")
