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
            diskofferingid=cls.disk_offerings.id,
        )
        cls.volume_2 = Volume.create(
            cls.apiclient,
            {"diskname":"StorPoolDisk-1" },
            zoneid=cls.zone.id,
            diskofferingid=cls.disk_offerings.id,
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

        cls.template = template
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
    def test_01_set_vcpolicy_tag_to_vm_with_attached_disks(self):
        ''' Test set vc_policy tag to VM with one attached disk
        '''
        volume_attached = self.virtual_machine.attach_volume(
            self.apiclient,
            self.volume_1
            )
        tag = Tag.create(
            self.apiclient,
            resourceIds=self.virtual_machine.id,
            resourceType='UserVm',
            tags={'vc_policy': 'testing_vc_policy'}
        )
        vm = list_virtual_machines(self.apiclient,id = self.virtual_machine.id)
        vm_tags = vm[0].tags
        volumes = list_volumes(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            )
        flag = False
        for v in volumes:
            spvolume = self.spapi.volumeList(volumeName=v.id)
            tags = spvolume[0].tags
            for t in tags:
                for vm_tag in vm_tags:
                    if t == vm_tag.key:
                        flag = True
                        self.assertEqual(tags[t], vm_tag.value, "Tags are not equal")
                        self.debug("######################### Storpool tag %s, vm tag %s  ; storpool tag value %s vm tag value %s ######################### " % (t, vm_tag.key, tags[t], vm_tag.value))
                    if t == 'cvm':
                        self.assertEqual(tags[t], vm[0].id, "CVM tag is not the same as vm UUID")
            #self.assertEqual(tag.tags., second, msg)
        self.assertTrue(flag, "There aren't volumes with vm tags")

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_02_set_vcpolicy_tag_to_attached_disk(self):
        """ Test set vc_policy tag to new disk attached to VM"""
        volume_attached = self.virtual_machine.attach_volume(
                self.apiclient,
                self.volume_2
                )
        vm = list_virtual_machines(self.apiclient,id = self.virtual_machine.id)
        vm_tags = vm[0].tags
        for vm_tag in vm_tags:
            sp_volume = self.spapi.volumeList(volumeName=volume_attached.id)
            for sp_tag in sp_volume[0].tags:
                if sp_tag == vm_tag.key:
                    self.debug("######################### StorPool tag %s , VM tag %s ######################### " % (sp_tag, vm_tag.key))
                    self.assertEqual(sp_tag, vm_tag.key, "StorPool tag is not the same as the Virtual Machine tag")
                    self.assertEqual(sp_volume[0].tags[sp_tag], vm_tag.value, "StorPool tag value is not the same as the Virtual Machine tag value")
                if sp_tag == 'cvm':
                    self.debug("#########################  StorPool tag value %s , VM uuid %s ######################### " % (sp_volume[0].tags[sp_tag], vm[0].id))
                    self.assertEqual(sp_volume[0].tags[sp_tag], vm[0].id, "cvm tag is not the expected value")

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_03_remove_vcpolicy_tag_when_disk_detached(self):
        """ Test remove vc_policy tag to disk detached from VM"""
        time.sleep(60)
        volume_detached = self.virtual_machine.detach_volume(
                self.apiclient,
                self.volume_2
                )
        vm = list_virtual_machines(self.apiclient,id = self.virtual_machine.id)
        vm_tags = vm[0].tags
        for vm_tag in vm_tags:
            vc = 'vc_policy'
            if vm_tag.key.lower() == vc.lower():
                sp_volume = self.spapi.volumeList(volumeName=self.volume_2.id)
                for sp_tag in sp_volume[0].tags:
                    self.assertFalse(sp_tag == vm_tag.key, "Sp tag is the same as vm tag")
                    if sp_tag == 'cvm':
                        self.assertEqual(sp_volume[0].tags[sp_tag], vm[0].id, "cvm tag is not the expected value")

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_04_delete_vcpolicy_tag(self):
        """ Test delete vc_policy tag of VM"""
        Tag.delete(self.apiclient,
            resourceIds=self.virtual_machine.id,
            resourceType='UserVm',
            tags={'vc_policy': 'testing_vc_policy'})

        volumes = list_volumes(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            )
        for v in volumes:
            spvolume = self.spapi.volumeList(volumeName=v.id)
            tags = spvolume[0].tags
            for t in tags:
                self.debug("######################### Storpool tag key:%s, value:%s ######################### " % (t, tags[t]))
                self.assertFalse(t.lower() == 'vc_policy'.lower(), "There is VC Policy tag")
        
        