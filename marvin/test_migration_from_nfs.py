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
import uuid

from marvin.cloudstackAPI import (listOsTypes,
                                  listTemplates,
                                  listHosts,
                                  createTemplate,
                                  createVolume,
                                  resizeVolume,
                                  startVirtualMachine,
                                  migrateVirtualMachine,
                                  migrateVolume
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

from storpool import spapi


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
        nfs_service_offerings = {
            "name": "nfs",
                "displaytext": "NFS service offerings",
                "cpunumber": 1,
                "cpuspeed": 500,
                "memory": 512,
                "storagetype": "shared",
                "customizediops": False,
                "hypervisorsnapshotreserve": 200,
                "tags": "nfs"
            }
        storage_pool = list_storage_pools(
            cls.apiclient,
            name='ssd'
            )
        nfs_storage_pool = list_storage_pools(
            cls.apiclient,
            name='primary'
            )
        service_offerings = list_service_offering(
            cls.apiclient,
            name='ssd'
            )
        nfs_service_offering = list_service_offering(
            cls.apiclient,
            name='nfs'
            )

        disk_offerings = list_disk_offering(
            cls.apiclient,
            name="Small"
            )

        cls.disk_offerings = disk_offerings[0]
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
        if nfs_service_offering is None:
            nfs_service_offering = ServiceOffering.create(cls.apiclient, nfs_service_offerings)
        else:
            nfs_service_offering = nfs_service_offering[0]
        #The version of CentOS has to be supported
        template = get_template(
             cls.apiclient,
            cls.zone.id,
            account = "system"
        )

        cls.nfs_storage_pool = nfs_storage_pool[0]
        cls.nfs_storage_pool = StoragePool.cancelMaintenance(cls.apiclient, cls.nfs_storage_pool.id)
        cls.vm = VirtualMachine.create(cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
            serviceofferingid=nfs_service_offering.id,
            hypervisor=cls.hypervisor,
            rootdisksize=10
            )
        cls.vm2 = VirtualMachine.create(cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
            serviceofferingid=nfs_service_offering.id,
            hypervisor= cls.hypervisor,
            rootdisksize=10
            )
        cls.storage_pool = StoragePool.update(cls.apiclient,
                                              id=cls.storage_pool.id,
                                              tags = ["ssd, nfs"])
        
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
        cls.nfs_service_offering = nfs_service_offering
        cls.debug(pprint.pformat(cls.service_offering))


        cls.template = template
        cls.random_data_0 = random_gen(size=100)
        cls.test_dir = "/tmp"
        cls.random_data = "random.data"
        cls._cleanup = []
        cls._cleanup.append(cls.vm)
        cls._cleanup.append(cls.vm2)

        return

    @classmethod
    def tearDownClass(cls):
        try:
            cls.nfs_storage_pool = StoragePool.enableMaintenance(cls.apiclient, cls.nfs_storage_pool.id)
            cls.storage_pool = StoragePool.update(cls.apiclient,
                                              id=cls.storage_pool.id,
                                              tags = ["ssd"])
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
    def test_1_migrate_vm_from_nfs_to_storpool(self):
        ''' Test migrate virtual machine from NFS primary storage to StorPool'''

        self.vm.stop(self.apiclient, forced=True)
        cmd = migrateVirtualMachine.migrateVirtualMachineCmd()
        cmd.virtualmachineid = self.vm.id
        cmd.storageid = self.storage_pool.id
        migrated_vm = self.apiclient.migrateVirtualMachine(cmd)
        volumes = list_volumes(
            self.apiclient,
            virtualmachineid = migrated_vm.id
            )
        for v in volumes:
            name = v.path.split("/")[3]
            try:
                sp_volume = self.spapi.volumeList(volumeName="~" + name)
            except spapi.ApiError as err:
                raise Exception(err)

            self.assertEqual(v.storageid, self.storage_pool.id, "Did not migrate virtual machine from NFS to StorPool")

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_2_migrate_volume_from_nfs_to_storpool(self):
        ''' Test migrate volume from NFS primary storage to StorPool'''

        self.vm2.stop(self.apiclient, forced=True)
        volumes = list_volumes(
            self.apiclient,
            virtualmachineid = self.vm2.id
            )
        for v in volumes:
            cmd = migrateVolume.migrateVolumeCmd()
            cmd.storageid = self.storage_pool.id
            cmd.volumeid = v.id
            volume =  self.apiclient.migrateVolume(cmd)
            self.assertEqual(volume.storageid, self.storage_pool.id, "Did not migrate volume from NFS to StorPool")

        volumes = list_volumes(
            self.apiclient,
            virtualmachineid = self.vm2.id
            )
        for v in volumes:
            name = v.path.split("/")[3]
            try:
                sp_volume = self.spapi.volumeList(volumeName="~" + name)
            except spapi.ApiError as err:
                raise Exception(err)
