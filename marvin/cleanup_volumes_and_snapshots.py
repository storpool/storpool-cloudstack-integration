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
from _ast import If
import random
import time

from marvin.cloudstackAPI import (listTemplates, deleteSnapshot, deleteVolume, destroyVirtualMachine)
from marvin.cloudstackTestCase import cloudstackTestCase
from marvin.codes import FAILED, KVM, PASS, XEN_SERVER, RUNNING
from marvin.lib.base import (Account,
                             ServiceOffering,
                             VirtualMachine,
                             VmSnapshot,
                             Snapshot,
                             User,
                             Volume,Template
                             )
from marvin.lib.common import (get_zone,
                               get_domain,
                               get_template,
                               list_clusters,
                               list_snapshots,
                               list_virtual_machines,
                               list_configurations,
                               list_disk_offering,
                               list_accounts,
                               list_storage_pools,
                               list_service_offering,
                               list_volumes,
                               list_templates)
from marvin.lib.utils import random_gen, cleanup_resources, validateList, is_snapshot_on_nfs, isAlmostEqual, get_hypervisor_type
from nose.plugins.attrib import attr
from sepolicy.templates.etc_rw import if_admin_rules


class TestData():
    account = "account"
    capacityBytes = "capacitybytes"
    capacityIops = "capacityiops"
    clusterId = "clusterId"
    diskName = "diskname"
    diskOffering = "diskoffering"
    domainId = "domainId"
    hypervisor = "hypervisor"
    login = "login"
    mvip = "mvip"
    password = "password"
    port = "port"
    primaryStorage = "primarystorage"
    primaryStorage2 = "primaryStorage"
    provider = "provider"
    serviceOffering = "serviceOffering"
    serviceOfferingOnly = "serviceOfferingOnly"
    scope = "scope"
    StorPool = "storpool"
    storageTag = ["ssd", "cloud-test-dev-1", "shared-tags"]
    tags = "tags"
    virtualMachine = "virtualmachine"
    virtualMachine2 = "virtualmachine2"
    volume_1 = "volume_1"
    volume_2 = "volume_2"
    zoneId = "zoneId"


    def __init__(self):
        self.testdata = {
            TestData.primaryStorage: {
                "name": "ssd",
                TestData.scope: "ZONE",
                "url": "ssd",
                TestData.provider: "StorPool",
                "path": "/dev/storpool",
                TestData.capacityBytes: 2251799813685248,
                TestData.hypervisor: "KVM"
            },
            TestData.primaryStorage2: {
                "name": "cloud-test-dev-1",
                TestData.scope: "ZONE",
                "url": "cloud-test-dev-1",
                TestData.provider: "StorPool",
                "path": "/dev/storpool",
                TestData.capacityBytes: 2251799813685248,
                TestData.hypervisor: "KVM"
            },
            TestData.virtualMachine: {
                "name": "TestVM",
                "displayname": "TestVM",
                "privateport": 22,
                "publicport": 22,
                "protocol": "tcp"
            },
            TestData.virtualMachine2: {
                "name": "TestVM2",
                "displayname": "TestVM2",
                "privateport": 22,
                "publicport": 22,
                "protocol": "tcp"
            },
            TestData.serviceOffering:{
                "name": "ssd",
                "displaytext": "SP_CO_2 (Min IOPS = 10,000; Max IOPS = 15,000)",
                "cpunumber": 1,
                "cpuspeed": 500,
                "memory": 512,
                "storagetype": "shared",
                "customizediops": False,
                "hypervisorsnapshotreserve": 200,
                "tags": "ssd"
            },
            TestData.serviceOfferingOnly:{
                "name": "cloud-test-dev-1",
                "displaytext": "SP_CO_2 (Min IOPS = 10,000; Max IOPS = 15,000)",
                "cpunumber": 1,
                "cpuspeed": 500,
                "memory": 512,
                "storagetype": "shared",
                "customizediops": False,
                "hypervisorsnapshotreserve": 200,
                "tags": "cloud-test-dev-1"
            },
            TestData.diskOffering: {
                "name": "SP_DO_1",
                "displaytext": "SP_DO_1 (5GB Min IOPS = 300; Max IOPS = 500)",
                "disksize": 5,
                "customizediops": False,
                "miniops": 300,
                "maxiops": 500,
                "hypervisorsnapshotreserve": 200,
                TestData.tags: TestData.storageTag,
                "storagetype": "shared"
            },
            TestData.volume_1: {
                TestData.diskName: "test-volume-1",
            },
            TestData.volume_2: {
                TestData.diskName: "test-volume-2",
            },
            TestData.zoneId: 1,
            TestData.clusterId: 1,
            TestData.domainId: 1,
        }


class TestVmSnapshot(cloudstackTestCase):

    @classmethod
    def setUpClass(cls):
        testClient = super(TestVmSnapshot, cls).getClsTestClient()
        cls.apiclient = testClient.getApiClient()
        cls._cleanup = []
        cls.unsupportedHypervisor = False

        # Setup test data
        td = TestData()
        cls.testdata = td.testdata


        cls.services = testClient.getParsedTestDataConfig()
        # Get Zone, Domain and templates
        cls.domain = get_domain(cls.apiclient)
        cls.zone = get_zone(cls.apiclient, testClient.getZoneForTests())
        cls.cluster = list_clusters(cls.apiclient)[0]
        cls.hypervisor = get_hypervisor_type(cls.apiclient)

        cls.test_dir = "/tmp"
        cls.random_data = "random.data"
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
    def test_01_delete_all_virtual_machines(self):
        """Test to delete VMs
        """
        virtual_machines = list_virtual_machines(self.apiclient)
        for v in virtual_machines:
                cmd = destroyVirtualMachine.destroyVirtualMachineCmd()
                cmd.id = v.id
                cmd.expunge = True
                self.apiclient.destroyVirtualMachine(cmd)
     

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_02_delete_all_snapshots(self):
        """Test to delete snapshots
        """
        snapshots = list_snapshots(self.apiclient)
        for s in snapshots:
            if s.state != "BackingUp":
                cmd = deleteSnapshot.deleteSnapshotCmd()
                cmd.id = s.id
                self.apiclient.deleteSnapshot(cmd)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_03_delete_all_datadisks(self):
        """Test to delete volumes
        """
        volumes = list_volumes(self.apiclient)
        for s in volumes:
            if s.state != "ROOT" and s.virtualmachineid is None:
                cmd = deleteVolume.deleteVolumeCmd()
                cmd.id = s.id
                self.apiclient.deleteVolume(cmd)
