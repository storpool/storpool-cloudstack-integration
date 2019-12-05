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
import pprint
import random
import time

from marvin.cloudstackAPI import (listTemplates)
from marvin.cloudstackTestCase import cloudstackTestCase
from marvin.codes import FAILED, KVM, PASS, XEN_SERVER, RUNNING
from marvin.lib.base import (Account,
                             ServiceOffering,
                             StoragePool,
                             VirtualMachine,
                             VmSnapshot, Volume)
from marvin.lib.common import (get_zone,
                               get_domain,
                               get_template,
                               list_disk_offering,
                               list_snapshots,
                               list_storage_pools,
                               list_virtual_machines,
                               list_configurations, list_service_offering)
from marvin.lib.utils import random_gen, cleanup_resources, validateList, is_snapshot_on_nfs, isAlmostEqual
from nose.plugins.attrib import attr
from sepolicy.templates.etc_rw import if_admin_rules

import storpool


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
            "name" : "cloudLocal",
            "zoneid": cls.zone.id,
            "url": "cloudLocal",
            "scope": "zone",
            "capacitybytes": 4500000,
            "capacityiops": 155466464221111121,
            "hypervisor": "kvm",
            "provider": "StorPool",
            "tags": "cloudLocal"
            }

        storpool_service_offerings = {
            "name": "tags",
                "displaytext": "SP_CO_2 (Min IOPS = 10,000; Max IOPS = 15,000)",
                "cpunumber": 1,
                "cpuspeed": 500,
                "memory": 512,
                "storagetype": "shared",
                "customizediops": False,
                "hypervisorsnapshotreserve": 200,
                "tags": "test_tags"
            }
        storage_pool = list_storage_pools(
            cls.apiclient,
            name='cloudLocal'
            )

        service_offerings = list_service_offering(
            cls.apiclient,
            name='tags'
            )

        disk_offerings = list_disk_offering(
            cls.apiclient,
            name="Small"
            )

        cls.debug(pprint.pformat(storage_pool))
        if storage_pool is None:
            storage_pool = StoragePool.create(cls.apiclient, storpool_primary_storage)
        else:
            storage_pool = storage_pool[0]
        cls.debug(pprint.pformat(storage_pool))
        if service_offerings is None:
            service_offerings = ServiceOffering.create(cls.apiclient, storpool_service_offerings)
        else:
            service_offerings = service_offerings[0]
        #The version of CentOS has to be supported
        template = get_template(
            apiclient=cls.apiclient,
            zone_id=cls.zone.id,
            template_filter='self',
            template_name="centos6",
            domain_id=cls.domain.id,
            hypervisor=cls.hypervisor
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
    def test_01_attach_volume_to_vm(self):
        #time.sleep(60)
        # It does not work!!  Unable to detach volume 63d7d256-a5bc-4117-9db8-5ad95941371d. Error:  Error: '63d7d256-a5b
        # c-4117-9db8-5ad95941371d' is open at client 22
        # Executing: sh -c lsof | fgrep /dev/sp-
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
        self.virtual_machine.stop(
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
