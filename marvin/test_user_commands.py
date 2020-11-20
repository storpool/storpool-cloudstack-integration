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
import json
import tempfile
import os
import uuid

from marvin.cloudstackAPI import (listOsTypes,
                                  listTemplates,
                                  listHosts,
                                  createTemplate,
                                  createVolume,
                                  resizeVolume,
                                  revertSnapshot,
                                  startVirtualMachine,
                                  createAccount)
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
                             Volume,
                             Role,
                             SSHKeyPair)
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
                               list_users,
                               list_accounts,
                               list_zones)
from marvin.lib.utils import random_gen, cleanup_resources, validateList, is_snapshot_on_nfs, isAlmostEqual
from nose.plugins.attrib import attr

from storpool import spapi
from time import sleep

class TestStoragePool(cloudstackTestCase):

    @classmethod
    def setUpClass(cls):
        cls.spapi = spapi.Api.fromConfig(multiCluster=True)

        testClient = super(TestStoragePool, cls).getClsTestClient()
        cls.apiclient = testClient.getApiClient()
        cls.userapiclient = testClient.getUserApiClient(UserName= "StorPoolUser", DomainName="ROOT")
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

        cls.service_offering = service_offerings

        user = list_users(cls.apiclient, account='StorPoolUser', domainid = cls.domain.id )
        account = list_accounts(cls.apiclient, id = user[0].accountid)
        if account is None:
            role = Role.list(cls.apiclient, name='User')
            cmd = createAccount.createAccountCmd()
            cmd.email = 'StorPoolUser@storpool.storpool'
            cmd.firstname = 'StorPoolUser'
            cmd.lastname = 'StorPoolUser'

            cmd.password = 'StorPoolUser'
            cmd.username = 'StorPoolUser'
            cmd.roleid = role[0].id
            account = cls.apiclient.createAccount(cmd)
        else:
            account = account[0]

        cls.account = account

#         cls.tmp_files = []
#         cls.keypair = SSHKeyPair.create(
#                                     cls.apiclient,
#                                     name=random_gen() + ".pem",
#                                     account=cls.account.name,
#                                     domainid=cls.account.domainid)
# 
#         keyPairFilePath = tempfile.gettempdir() + os.sep + cls.keypair.name
#         # Clenaup at end of execution
#         cls.tmp_files.append(keyPairFilePath)
# 
#         cls.debug("File path: %s" % keyPairFilePath)
# 
#         f = open(keyPairFilePath, "w+")
#         f.write(cls.keypair.privatekey)
#         f.close()
# 
#         os.system("chmod 400 " + keyPairFilePath)
# 
#         cls.keyPairFilePath = keyPairFilePath

        cls.volume_1 = Volume.create(
            cls.userapiclient,
            {"diskname":"StorPoolDisk-1" },
            zoneid=cls.zone.id,
            diskofferingid=cls.disk_offerings.id,
        )
        cls.volume_2 = Volume.create(
            cls.userapiclient,
            {"diskname":"StorPoolDisk-2" },
            zoneid=cls.zone.id,
            diskofferingid=cls.disk_offerings.id,
        )
        cls.volume = Volume.create(
            cls.userapiclient,
            {"diskname":"StorPoolDisk-3" },
            zoneid=cls.zone.id,
            diskofferingid=cls.disk_offerings.id,
        )
        cls.virtual_machine = VirtualMachine.create(
            cls.userapiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            rootdisksize=10,
        )
        cls.virtual_machine2= VirtualMachine.create(
            cls.userapiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            rootdisksize=10,
        )
        cls.template = template
        cls.random_data_0 = random_gen(size=100)
        cls.test_dir = "/tmp"
        cls.random_data = "random.data"
        cls._cleanup = []
        cls._cleanup.append(cls.virtual_machine)
        cls._cleanup.append(cls.virtual_machine2)
        cls._cleanup.append(cls.volume_1)
        cls._cleanup.append(cls.volume_2)
        cls._cleanup.append(cls.volume)
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
            self.userapiclient,
            self.volume_1
            )
        try:
            tag = Tag.create(
                self.userapiclient,
                resourceIds=self.virtual_machine.id,
                resourceType='UserVm',
                tags={'vc_policy': 'testing_vc_policy'}
            )
        except Exception as e:
            self.debug("##################### test_01_set_vcpolicy_tag_to_vm_with_attached_disks %s" % e)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_02_create_vm_snapshot_by_user(self):
        """Test to create VM snapshots
        """
        volume_attached = self.virtual_machine.attach_volume(
            self.userapiclient,
            self.volume
            )

        volumes = list_volumes(
            self.userapiclient,
            virtualmachineid = self.virtual_machine.id,
            listall =True
            )

        self.assertEqual(volume_attached.id, self.volume.id, "Is not the same volume ")
        try:
            # Login to VM and write data to file system
            ssh_client = self.virtual_machine.get_ssh_client(reconnect=True)

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
            self.userapiclient,
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
    def test_03_revert_vm_snapshots_vc_policy_tag(self):
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
            self.userapiclient,
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

        self.virtual_machine.stop(self.userapiclient, forced=True)

        VmSnapshot.revertToSnapshot(
            self.userapiclient,
            list_snapshot_response[0].id
            )

        self.virtual_machine.start(self.userapiclient)

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
    def test_04_delete_vm_snapshots(self):
        """Test to delete vm snapshots
        """

        list_snapshot_response = VmSnapshot.list(
            self.userapiclient,
            virtualmachineid=self.virtual_machine.id,
            listall=True)

        self.assertNotEqual(
            list_snapshot_response,
            None,
            "Check if snapshot exists in ListSnapshot"
        )
        VmSnapshot.deleteVMSnapshot(
            self.userapiclient,
            list_snapshot_response[0].id)

        time.sleep(30)

        list_snapshot_response = VmSnapshot.list(
            self.userapiclient,
            #vmid=self.virtual_machine.id,
            virtualmachineid=self.virtual_machine.id,
            listall=False)
        self.debug('list_snapshot_response -------------------- %s' % list_snapshot_response)

        self.assertIsNone(list_snapshot_response, "snapshot is already deleted")
      

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_05_set_vcpolicy_tag_with_admin_and_try_delete_with_user(self):
        ''' Test set vc_policy tag to VM with one attached disk
        '''
        tag = Tag.create(
                self.apiclient,
                resourceIds=self.virtual_machine.id,
                resourceType='UserVm',
                tags={'vc_policy': 'testing_vc_policy'}
            )

        self.debug('######################### test_05_set_vcpolicy_tag_with_admin_and_try_delete_with_user tags ######################### ')
        
        vm = list_virtual_machines(self.userapiclient,id = self.virtual_machine.id)
        vm_tags = vm[0].tags
        volumes = list_volumes(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            listall= True
            )
        self.debug('######################### test_01_set_vcpolicy_tag_to_vm_with_attached_disks tags ######################### ')

        self.vc_policy_tags(volumes, vm_tags, vm)

        try:
            Tag.delete(self.userapiclient,
                resourceIds=self.virtual_machine.id,
                resourceType='UserVm',
                tags={'vc_policy': 'testing_vc_policy'}
                )
        except Exception as e:
            self.debug("##################### test_05_set_vcpolicy_tag_with_admin_and_try_delete_with_user %s " % e)


    def vc_policy_tags(self, volumes, vm_tags, vm):
        flag = False
        for v in volumes:
            self.debug("Volume attached")
            self.debug(v)
            name = v.path.split("/")[3]
            spvolume = self.spapi.volumeList(volumeName= "~" + name)
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