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

import unittest
import random
import os
import json
import time
import math
import collections
import distutils.util
import pprint
from ansible.module_utils import storage


# All tests inherit from cloudstackTestCase
from marvin.cloudstackTestCase import cloudstackTestCase

from nose.plugins.attrib import attr

# Import Integration Libraries

# base - contains all resources as entities and defines create, delete, list operations on them
from marvin.lib.base import (Account,
                             DiskOffering,
                             ServiceOffering,
                             Snapshot,
                             StoragePool,
                             User,
                             VirtualMachine,
                             Volume,
                             VmSnapshot)

# common - commonly used methods for all tests are listed here
from marvin.lib.common import (get_domain,
                               get_template,
                               get_zone,
                               list_clusters,
                               list_hosts,
                               list_virtual_machines,
                               list_volumes,
                               list_disk_offering,
                               list_accounts,
                               list_storage_pools,
                               list_service_offering)

# utils - utility classes for common cleanup, external library wrappers, etc.
from marvin.lib.utils import cleanup_resources, get_hypervisor_type

from marvin.cloudstackAPI import resizeVolume




class TestData():
    account = "account"
    capacityBytes = "capacitybytes"
    capacityIops = "capacityiops"
    clusterId = "clusterId"
    managedComputeOffering = "managedComputeoffering"
    nonManagedComputeOffering = "nonManagedComputeoffering"
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
    scope = "scope"
    StorPool = "storpool"
    storageTag = ["cloud-test-dev-2", "cloud-test-dev-1", "shared-tags"]
    tags = "tags"
    templateName = "templatename"
    testAccount = "testaccount"
    url = "url"
    user = "user"
    username = "username"
    virtualMachine = "virtualmachine"
    virtualMachine2 = "virtualmachine2"
    volume_1 = "volume_1"
    volume_2 = "volume_2"
    xenServer = "xenserver"
    zoneId = "zoneId"
    serviceOfferingOnly = "serviceOfferingOnly"
    def __init__(self):
        self.testdata = {
            TestData.primaryStorage: {
                "name": "cloud-test-dev-2",
                TestData.scope: "ZONE",
                "url": "cloud-test-dev-2",
                TestData.provider: "StorPool",
                "path": "/dev/storpool",
                #TestData.capacityIops: 4500000,
                TestData.capacityBytes: 2251799813685248,
                TestData.hypervisor: "KVM"
            },
            TestData.primaryStorage2: {
                "name": "cloud-test-dev-1",
                TestData.scope: "ZONE",
                "url": "cloud-test-dev-1",
                TestData.provider: "StorPool",
                "path": "/dev/storpool",
                #TestData.capacityIops: 4500000,
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
            TestData.managedComputeOffering: {
                "name": "SP_CO_1",
                "displaytext": "SP_CO_1 (Min IOPS = 10,000; Max IOPS = 15,000)",
                "cpunumber": 1,
                "cpuspeed": 100,
                "memory": 128,
                "storagetype": "shared",
                "customizediops": False,
                "miniops": "10000",
                "maxiops": "15000",
                "hypervisorsnapshotreserve": 200,
                "tags": TestData.storageTag
            },
            TestData.serviceOffering:{
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
            TestData.serviceOfferingOnly:{
                "name": "cloud-test-dev-2",
                "displaytext": "SP_CO_2 (Min IOPS = 10,000; Max IOPS = 15,000)",
                "cpunumber": 1,
                "cpuspeed": 500,
                "memory": 512,
                "storagetype": "shared",
                "customizediops": False,
                "hypervisorsnapshotreserve": 200,
                "tags": "cloud-test-dev-2"
            },
            TestData.nonManagedComputeOffering: {
                "name": "SP_CO_2",
                "displaytext": "SP_CO_2 (Min IOPS = 10,000; Max IOPS = 15,000)",
                "cpunumber": 1,
                "cpuspeed": 100,
                "memory": 128,
                "storagetype": "shared",
                "customizediops": False,
                "miniops": "10000",
                "maxiops": "15000",
                "hypervisorsnapshotreserve": 200,
                "tags": TestData.storageTag
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
            "testdiskofferings": {
                "customiopsdo": {
                    "name": "SP_Custom_Iops_DO",
                    "displaytext": "Customized Iops DO",
                    "disksize": 5,
                    "customizediops": True,
                    "miniops": 500,
                    "maxiops": 1000,
                    "hypervisorsnapshotreserve": 200,
                    TestData.tags: TestData.storageTag,
                    "storagetype": "shared"
                },
                "customsizedo": {
                    "name": "SP_Custom_Size_DO",
                    "displaytext": "Customized Size DO",
                    "disksize": 5,
                    "customizediops": False,
                    "miniops": 500,
                    "maxiops": 1000,
                    "hypervisorsnapshotreserve": 200,
                    TestData.tags: TestData.storageTag,
                    "storagetype": "shared"
                },
                "customsizeandiopsdo": {
                    "name": "SP_Custom_Iops_Size_DO",
                    "displaytext": "Customized Size and Iops DO",
                    "disksize": 10,
                    "customizediops": True,
                    "miniops": 400,
                    "maxiops": 800,
                    "hypervisorsnapshotreserve": 200,
                    TestData.tags: TestData.storageTag,
                    "storagetype": "shared"
                },
                "newiopsdo": {
                    "name": "SP_New_Iops_DO",
                    "displaytext": "New Iops (min=350, max = 700)",
                    "disksize": 5,
                    "miniops": 350,
                    "maxiops": 700,
                    "hypervisorsnapshotreserve": 200,
                    TestData.tags: TestData.storageTag,
                    "storagetype": "shared"
                },
                "newsizedo": {
                    "name": "SP_New_Size_DO",
                    "displaytext": "New Size: 10",
                    "disksize": 10,
                    "customizediops": False,
                    "miniops": 400,
                    "maxiops": 800,
                    "hypervisorsnapshotreserve": 200,
                    TestData.tags: TestData.storageTag,
                    "storagetype": "shared"
                },
                "newsizeandiopsdo": {
                    "name": "SP_New_Size_Iops_DO",
                    "displaytext": "New Size and Iops",
                    "disksize": 10,
                    "customizediops": False,
                    "miniops": 200,
                    "maxiops": 800,
                    "hypervisorsnapshotreserve": 200,
                    TestData.tags: TestData.storageTag,
                    "storagetype": "shared"
                }
            },
            TestData.volume_1: {
                TestData.diskName: "test-volume-1",
            },
            TestData.volume_2: {
                TestData.diskName: "test-volume-2",
            },
            TestData.templateName: "tiny linux kvm",  # TODO
            TestData.zoneId: 1,
            TestData.clusterId: 1,
            TestData.domainId: 1,
        }

class TestVolumes(cloudstackTestCase):

    @classmethod
    def setUpClass(cls):

        # Set up API client
        testclient = super(TestVolumes, cls).getClsTestClient()
        cls.apiClient = testclient.getApiClient()
        cls.dbConnection = testclient.getDbConnection()
        cls.services = testclient.getParsedTestDataConfig()

        # Setup test data
        td = TestData()
        cls.testdata = td.testdata

        # Get Resources from Cloud Infrastructure
        cls.domain = get_domain(cls.apiClient)
        cls.zone = get_zone(cls.apiClient, testclient.getZoneForTests())
        cls.cluster = list_clusters(cls.apiClient)[0]
        cls.hypervisor = get_hypervisor_type(cls.apiClient)
        
        cls.template = get_template(
             cls.apiClient,
             cls.zone.id,
             account = "system"
        )
        primarystorage = cls.testdata[TestData.primaryStorage]
        primarystorage2 = cls.testdata[TestData.primaryStorage2]

        serviceOffering = cls.testdata[TestData.serviceOffering]
        serviceOfferingOnly = cls.testdata[TestData.serviceOfferingOnly]
        storage_pool = list_storage_pools(
            cls.apiClient,
            name = primarystorage.get("name")
            )
        cls.primary_storage = storage_pool[0]

        storage_pool = list_storage_pools(
            cls.apiClient,
            name = primarystorage2.get("name")
            )
        cls.primary_storage2 = storage_pool[0]

        disk_offering = list_disk_offering(
            cls.apiClient,
            name="Small"
            )

        assert disk_offering is not None


        service_offering = list_service_offering(
            cls.apiClient,
            name="cloud-test-dev-1"
            )
        if service_offering is not None:
            cls.service_offering = service_offering[0]
        else:
            cls.service_offering = ServiceOffering.create(
                cls.apiClient,
                serviceOffering)

        service_offering_only = list_service_offering(
            cls.apiClient,
            name="cloud-test-dev-2"
            )
        if service_offering_only is not None:
            cls.service_offering_only = service_offering_only[0]
        else:
            cls.service_offering_only = ServiceOffering.create(
                cls.apiClient,
                serviceOfferingOnly)
        assert cls.service_offering_only is not None

        cls.disk_offering = disk_offering[0]

        account = list_accounts(
            cls.apiClient,
            name="admin"
            )
        cls.account = account[0]
        # Create 1 data volume_1
        cls.volume = Volume.create(
            cls.apiClient,
            cls.testdata[TestData.volume_1],
            account=cls.account.name,
            domainid=cls.domain.id,
            zoneid=cls.zone.id,
            diskofferingid=cls.disk_offering.id
        )

        cls.virtual_machine = VirtualMachine.create(
            cls.apiClient,
            {"name":"StorPool-%d" % random.randint(0, 100)},
            zoneid=cls.zone.id,
            templateid=cls.template.id,
            serviceofferingid=cls.service_offering_only.id,
            hypervisor=cls.hypervisor,
            rootdisksize=10
        )

        # Resources that are to be destroyed
        cls._cleanup = [
            cls.virtual_machine,
            cls.volume
        ]

    @classmethod
    def tearDownClass(cls):
        try:
            cleanup_resources(cls.apiClient, cls._cleanup)
        except Exception as e:
            cls.debug("-----------------------")

    def setUp(self):
        self.attached = False
        self.cleanup = []

    def tearDown(self):
        cleanup_resources(self.apiClient, self.cleanup)

    def _get_cs_storage_pool_db_id(self, storage_pool):
        return self._get_db_id("storage_pool", storage_pool)

    def _get_db_id(self, table, db_obj):
        sql_query = "Select id From " + table + " Where uuid = '" + str(db_obj.id) + "'"
        sql_result = self.dbConnection.execute(sql_query)
        return sql_result[0][0]

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_01_snapshot_detached_volume(self):
        ''' Test Snapshot Detached Volume
        '''
        self.virtual_machine.stop(
            self.apiClient,
            forced = True
            )
        self.volume = self.virtual_machine.attach_volume(
            self.apiClient,
            self.volume
            )
        self.assertIsNotNone(self.volume, "Attach: Is none")
        self.volume = self.virtual_machine.detach_volume(
            self.apiClient,
            self.volume
            )

        self.assertIsNotNone(self.volume, "Detach: Is none")

        snapshot = Snapshot.create(
            self.apiClient,
            self.volume.id,
            )

        self.assertIsNotNone(snapshot, "Snapshot is None")

        self.assertIsInstance(snapshot, Snapshot, "Snapshot is not Instance of Snappshot")

        snapshot = Snapshot.delete(
            snapshot,
            self.apiClient
            )

        self.assertIsNone(snapshot, "Snapshot was not deleted")

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_02_snapshot_attached_volume(self):
        ''' Test Snapshot With Attached Volume
        '''
        list_volumes_of_vm = list_volumes(
            self.apiClient,
            virtualmachineid = self.virtual_machine.id
            )
        self.assertIs(len(list_volumes_of_vm), 1, "VM has more disk than 1")

        snapshot = Snapshot.create(
            self.apiClient,
            list_volumes_of_vm[0].id
            )

        self.assertIsNotNone(snapshot, "Snapshot is None")

        self.assertEqual(list_volumes_of_vm[0].id, snapshot.volumeid, "Snapshot is not for the same volume")

        snapshot = Snapshot.delete(
            snapshot,
            self.apiClient
            )

        self.assertIsNone(snapshot, "Snapshot is not None")
    
    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_03_migrate_vm_to_another_storage(self):
        ''' Migrate VM to another Primary Storage
        '''
        list_volumes_of_vm = list_volumes(
            self.apiClient,
            virtualmachineid = self.virtual_machine.id
            )

        self.assertTrue(len(list_volumes_of_vm) == 1, "Thera are more volumes attached to VM")

        if list_volumes_of_vm[0].storageid is self.primary_storage2.id:
            vm = VirtualMachine.migrate(
                self.apiClient,
                storageid = self.primary_storage.id
                )
            volume = list_volumes(
                self.apiClient,
                virtualmachineid = vm.id
                )[0]
            self.assertEqual(volume.storageid, self.primary_storage2.id, "Could not migrate VM")


    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")

    def test_04_migrate_volume_to_another_storage(self):
        ''' Migrate Volume To Another Primary Storage
        '''
        self.assertFalse(hasattr(self.volume, 'virtualmachineid') , "Volume is not detached")
        
        self.assertFalse(hasattr(self.volume, 'storageid') , "Volume is not detached")
        volume = Volume.migrate(
            self.apiClient,
            volumeid = self.volume.id,
            storageid = self.primary_storage.id
            )

        self.assertIsNotNone(volume, "Volume is None")

        self.assertEqual(volume.storageid, self.primary_storage.id, "Storage is the same")
   