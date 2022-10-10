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
""" Tests for Virtual Machine Life Cycle
    This is the first test for StorPool's tests
"""
#Import Local Modules
import random
import re
import time

from marvin.cloudstackAPI import (recoverVirtualMachine,
                                  destroyVirtualMachine,
                                  attachIso,
                                  detachIso,
                                  provisionCertificate,
                                  updateConfiguration)
from marvin.cloudstackTestCase import cloudstackTestCase
from marvin.codes import FAILED, PASS
from marvin.lib.base import (Account,
                             ServiceOffering,
                             VirtualMachine,
                             Host,
                             Iso,
                             Router,
                             Configurations,
                             Template
                             )
from marvin.lib.common import (get_domain,
                                get_zone,
                                get_template,
                               list_hosts,
                               list_service_offering,
                               list_accounts,
                               list_storage_pools
                               )
from marvin.lib.utils import *
from nose.plugins.attrib import attr


#Import System modules
_multiprocess_shared_ = True

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
    storageTag = ["cloud-test-dev-2", "cloud-test-dev-1", "shared-tags"]
    tags = "tags"
    template = "template"
    virtualMachine = "virtualmachine"
    virtualMachine2 = "virtualmachine2"
    volume_1 = "volume_1"
    volume_2 = "volume_2"
    zoneId = "zoneId"
    def __init__(self):
        self.testdata = {
            TestData.primaryStorage: {
                "name": "cloud-test-dev-1",
                TestData.scope: "ZONE",
                "url": "cloud-test-dev-1",
                TestData.provider: "StorPool",
                "path": "/dev/storpool",
                TestData.capacityBytes: 2251799813685248,
                TestData.hypervisor: "KVM"
            },
            TestData.primaryStorage2: {
                "name": "cloud-test-dev-2",
                TestData.scope: "ZONE",
                "url": "cloud-test-dev-2",
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
                "name": "tags",
                "displaytext": "SP_CO_2 (Min IOPS = 10,000; Max IOPS = 15,000)",
                "cpunumber": 1,
                "cpuspeed": 500,
                "memory": 512,
                "storagetype": "shared",
                "customizediops": False,
                "hypervisorsnapshotreserve": 200,
                "tags": TestData.storageTag
            },
            TestData.serviceOfferingOnly:{
                "name": "only",
                "displaytext": "SP_CO_2 (Min IOPS = 10,000; Max IOPS = 15,000)",
                "cpunumber": 1,
                "cpuspeed": 500,
                "memory": 512,
                "storagetype": "shared",
                "customizediops": False,
                "hypervisorsnapshotreserve": 200,
                "tags": "only"
            },
            TestData.template:{
                "name": "centOS6.4",
                "displaytext" : "StorPool template for Tests - centOS6.4",
                "url":"http://download.cloudstack.org/releases/4.3/centos6_4_64bit.vhd.bz2",
                "format":"VHD",
                "isextractable": False,
                 "ostypeid":"89109566-aedd-11e9-8c58-02000a0201ba",
                "passwordenabled": False,
                "isdynamicallyscalable": False,
                "hypervisor":"KVM",
                "ispublic": False,
                "directdownload": False
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


class TestDeployVM(cloudstackTestCase):

    @classmethod
    def setUpClass(cls):
        testClient = super(TestDeployVM, cls).getClsTestClient()
        cls.apiclient = testClient.getApiClient()
        cls.services = testClient.getParsedTestDataConfig()

        # Get Zone, Domain and templates
        cls.domain = get_domain(cls.apiclient)
        cls.zone = get_zone(cls.apiclient, testClient.getZoneForTests())
        cls.services['mode'] = cls.zone.networktype
        cls.hypervisor = get_hypervisor_type(cls.apiclient)
        
        # Setup test data
        td = TestData()
        cls.testdata = td.testdata

        # OS template 
        template = cls.testdata[TestData.template]

        #StorPool primary storages
        primarystorage = cls.testdata[TestData.primaryStorage]
        primarystorage2 = cls.testdata[TestData.primaryStorage2]

        storage_pool = list_storage_pools(
            cls.apiclient,
            name = primarystorage.get("name")
            )
        if storage_pool is None:
             cls.primary_storage = StoragePool.create(
                        cls.apiclient,
                        primarystorage,
                        scope=primarystorage[TestData.scope],
                        zoneid=cls.zone.id,
                        provider=primarystorage[TestData.provider],
                        tags=primarystorage[TestData.tags],
                        capacityiops=primarystorage[TestData.capacityIops],
                        capacitybytes=primarystorage[TestData.capacityBytes],
                        hypervisor=primarystorage[TestData.hypervisor]
                    )
        else:
            cls.primary_storage = storage_pool[0]

        storage_pool = list_storage_pools(
            cls.apiclient,
            name = primarystorage2.get("name")
            )
        if storage_pool is None:
            cls.primary_storage2 = StoragePool.create(
                    cls.apiclient,
                    primarystorage2,
                    scope=primarystorage2[TestData.scope],
                    zoneid=cls.zone.id,
                    provider=primarystorage2[TestData.provider],
                    tags=primarystorage2[TestData.tags],
                    capacityiops=primarystorage2[TestData.capacityIops],
                    capacitybytes=primarystorage2[TestData.capacityBytes],
                    hypervisor=primarystorage2[TestData.hypervisor]
             )
        else:
            cls.primary_storage2 = storage_pool[0]

        cls.debug(primarystorage)
        cls.debug(primarystorage2)
        os_template = get_template(
            cls.apiclient,
            cls.zone.id,
            account = "system"
        )
        if os_template == FAILED:
            cls.template = Template.register(
                cls.apiclient,
                template,
                cls.zone.id,
                randomize_name = False
                )
        else:
            cls.template = os_template
        cls.debug(template)

        # Set Zones and disk offerings
        cls.services["small"]["zoneid"] = cls.zone.id
        cls.services["small"]["template"] = cls.template.id

        cls.services["iso1"]["zoneid"] = cls.zone.id

        cls.account = list_accounts(
            cls.apiclient,
            name="admin"
            )[0]
        cls.debug(cls.account.id)

        service_offering_only = list_service_offering(
            cls.apiclient,
            name="cloud-test-dev-1"
            )
        cls.service_offering = service_offering_only[0]

        cls.virtual_machine = VirtualMachine.create(
            cls.apiclient,
            cls.services["small"],
            accountid=cls.account.name,
            domainid=cls.account.domainid,
            serviceofferingid=cls.service_offering.id,
            mode=cls.services['mode']
        )

        cls.cleanup = [
            cls.virtual_machine
        ]

    @classmethod
    def tearDownClass(cls):
        try:
            cleanup_resources(cls.apiclient, cls.cleanup)
        except Exception as e:
            raise Exception("Warning: Exception during cleanup : %s" % e)

    def setUp(self):
        self.apiclient = self.testClient.getApiClient()
        self.dbclient = self.testClient.getDbConnection()
        self.cleanup = []


    @attr(tags = ["devcloud", "advanced", "advancedns", "smoke", "basic", "sg"], required_hardware="false")
    def test_deploy_vm(self):
        """Test Deploy Virtual Machine
        """
        # Validate the following:
        # 1. Virtual Machine is accessible via SSH
        # 2. listVirtualMachines returns accurate information
        #TODO: test 1.
        list_vm_response = VirtualMachine.list(
                                                 self.apiclient,
                                                 id=self.virtual_machine.id
                                                 )

        self.debug(
                "Verify listVirtualMachines response for virtual machine: %s" \
                % self.virtual_machine.id
            )
        self.assertEqual(
                            isinstance(list_vm_response, list),
                            True,
                            "Check list response returns a valid list"
                        )
        self.assertNotEqual(
                            len(list_vm_response),
                            0,
                            "Check VM available in List Virtual Machines"
                        )
        vm_response = list_vm_response[0]
        self.assertEqual(

                            vm_response.id,
                            self.virtual_machine.id,
                            "Check virtual machine id in listVirtualMachines"
                        )
        self.assertEqual(
                    vm_response.name,
                    self.virtual_machine.name,
                    "Check virtual machine name in listVirtualMachines"
                    )
        self.assertEqual(
            vm_response.state,
            'Running',
             msg="VM is not in Running state"
        )
        return


    @attr(tags = ["advanced"], required_hardware="false")
    def test_advZoneVirtualRouter(self):
        #TODO: SIMENH: duplicate test, remove it
        """
        Test advanced zone virtual router
        1. Is Running
        2. is in the account the VM was deployed in
        3. Has a linklocalip, publicip and a guestip
        @return:
        """
        routers = Router.list(self.apiclient, account="system")
        self.assertTrue(len(routers) > 0, msg = "No virtual router found")
        router = routers[0]

        self.assertEqual(router.state, 'Running', msg="Router is not in running state")
       # self.assertEqual(router.account, self.account.name, msg="Router does not belong to the account")

        #Has linklocal, public and guest ips
        self.assertIsNotNone(router.linklocalip, msg="Router has no linklocal ip")
        self.assertIsNotNone(router.guestipaddress, msg="Router has no guest ip")

    @attr(tags = ['advanced','basic','sg'], required_hardware="false")
    def test_deploy_vm_multiple(self):
        """Test Multiple Deploy Virtual Machine

        # Validate the following:
        # 1. deploy 2 virtual machines
        # 2. listVirtualMachines using 'ids' parameter returns accurate information
        """
        virtual_machine1 = VirtualMachine.create(
           self.apiclient,
            {"name":"StorPool-%d" % random.randint(0, 100)},
            zoneid=self.zone.id,
            templateid=self.template.id,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
        )
        virtual_machine2 = VirtualMachine.create(
            self.apiclient,
            {"name":"StorPool-%d" % random.randint(0, 100)},
            zoneid=self.zone.id,
            templateid=self.template.id,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
        )

        list_vms = VirtualMachine.list(self.apiclient, ids=[virtual_machine1.id, virtual_machine2.id], listAll=True)
        self.debug(
            "Verify listVirtualMachines response for virtual machines: %s, %s" % (virtual_machine1.id, virtual_machine2.id)
        )
        self.assertEqual(
            isinstance(list_vms, list),
            True,
            "List VM response was not a valid list"
        )
        self.assertEqual(
            len(list_vms),
            2,
            "List VM response was empty, expected 2 VMs"
        )
        self.cleanup.append(virtual_machine1)
        self.cleanup.append(virtual_machine2)

    def tearDown(self):
        try:
            # Clean up, terminate the created instance, volumes and snapshots
            cleanup_resources(self.apiclient, self.cleanup)
        except Exception as e:
            raise Exception("Warning: Exception during cleanup : %s" % e)


class TestVMLifeCycle(cloudstackTestCase):

    @classmethod
    def setUpClass(cls):
        testClient = super(TestVMLifeCycle, cls).getClsTestClient()
        cls.apiclient = testClient.getApiClient()
        cls.services = testClient.getParsedTestDataConfig()
        cls.hypervisor = get_hypervisor_type(cls.apiclient)
        # Get Zone, Domain and templates
        domain = get_domain(cls.apiclient)
        cls.zone = get_zone(cls.apiclient, cls.testClient.getZoneForTests())
        cls.services['mode'] = cls.zone.networktype
        cls.domain = domain

        template = get_template(
            apiclient=cls.apiclient,
            zone_id=cls.zone.id,
            account = "system"
        )
        if template == FAILED:
            assert False, "get_template() failed to return template with description %s" % cls.services["ostype"]

        cls.template = template
        # Set Zones and disk offerings
        cls.services["small"]["zoneid"] = cls.zone.id
        cls.services["small"]["template"] = template.id

        cls.services["iso1"]["zoneid"] = cls.zone.id

        # Create VMs, NAT Rules etc
        cls.account = list_accounts(
            cls.apiclient,
            name="admin"
            )[0]


        cls.small_offering = ServiceOffering.create(
                                    cls.apiclient,
                                    cls.services["service_offerings"]["small"],
                                    tags="cloud-test-dev-1"
                                    )

        cls.medium_offering = ServiceOffering.create(
                                    cls.apiclient,
                                    cls.services["service_offerings"]["medium"],
                                    tags="cloud-test-dev-1"
                                    )
        #create small and large virtual machines
        cls.small_virtual_machine = VirtualMachine.create(
                                        cls.apiclient,
                                        cls.services["small"],
                                        accountid=cls.account.name,
                                        domainid=cls.account.domainid,
                                        serviceofferingid=cls.small_offering.id,
                                        )
        cls.medium_virtual_machine = VirtualMachine.create(
                                       cls.apiclient,
                                       cls.services["small"],
                                       accountid=cls.account.name,
                                       domainid=cls.account.domainid,
                                       serviceofferingid=cls.medium_offering.id,
                                    )
        cls.virtual_machine = VirtualMachine.create(
                                        cls.apiclient,
                                        cls.services["small"],
                                        accountid=cls.account.name,
                                        domainid=cls.account.domainid,
                                        serviceofferingid=cls.small_offering.id,
                                        )
        cls._cleanup = [
                        cls.small_offering,
                        cls.medium_offering,
                        cls.medium_virtual_machine,
                        cls.virtual_machine
                        ]

    @classmethod
    def tearDownClass(cls):
        cls.apiclient = super(TestVMLifeCycle, cls).getClsTestClient().getApiClient()
        try:
            cleanup_resources(cls.apiclient, cls._cleanup)
        except Exception as e:
            raise Exception("Warning: Exception during cleanup : %s" % e)
        return

    def setUp(self):
        self.apiclient = self.testClient.getApiClient()
        self.dbclient = self.testClient.getDbConnection()
        self.cleanup = []

    def tearDown(self):
        try:
            #Clean up, terminate the created ISOs
            cleanup_resources(self.apiclient, self.cleanup)
        except Exception as e:
            raise Exception("Warning: Exception during cleanup : %s" % e)
        return


    @attr(tags = ["devcloud", "advanced", "advancedns", "smoke", "basic", "sg"], required_hardware="false")
    def test_01_stop_vm(self):
        """Test Stop Virtual Machine
        """

        # Validate the following
        # 1. Should Not be able to login to the VM.
        # 2. listVM command should return
        #    this VM.State of this VM should be ""Stopped"".
        try:
            self.small_virtual_machine.stop(self.apiclient)
        except Exception as e:
            self.fail("Failed to stop VM: %s" % e)
        return


    @attr(tags = ["devcloud", "advanced", "advancedns", "smoke", "basic", "sg"], required_hardware="false")
    def test_01_stop_vm_forced(self):
        """Test Force Stop Virtual Machine
        """
        try:
            self.small_virtual_machine.stop(self.apiclient, forced=True)
        except Exception as e:
            self.fail("Failed to stop VM: %s" % e)

        list_vm_response = VirtualMachine.list(
                                            self.apiclient,
                                            id=self.small_virtual_machine.id
                                            )
        self.assertEqual(
                            isinstance(list_vm_response, list),
                            True,
                            "Check list response returns a valid list"
                        )

        self.assertNotEqual(
                            len(list_vm_response),
                            0,
                            "Check VM avaliable in List Virtual Machines"
                        )

        self.assertEqual(
                            list_vm_response[0].state,
                            "Stopped",
                            "Check virtual machine is in stopped state"
                        )
        return


    @attr(tags = ["devcloud", "advanced", "advancedns", "smoke", "basic", "sg"], required_hardware="false")
    def test_02_start_vm(self):
        """Test Start Virtual Machine
        """
        # Validate the following
        # 1. listVM command should return this VM.State
        #    of this VM should be Running".

        self.debug("Starting VM - ID: %s" % self.virtual_machine.id)
        self.small_virtual_machine.start(self.apiclient)

        list_vm_response = VirtualMachine.list(
                                            self.apiclient,
                                            id=self.small_virtual_machine.id
                                            )
        self.assertEqual(
                            isinstance(list_vm_response, list),
                            True,
                            "Check list response returns a valid list"
                        )

        self.assertNotEqual(
                            len(list_vm_response),
                            0,
                            "Check VM avaliable in List Virtual Machines"
                        )

        self.debug(
                "Verify listVirtualMachines response for virtual machine: %s" \
                % self.small_virtual_machine.id
                )
        self.assertEqual(
                            list_vm_response[0].state,
                            "Running",
                            "Check virtual machine is in running state"
                        )
        return

    @attr(tags = ["devcloud", "advanced", "advancedns", "smoke", "basic", "sg"], required_hardware="false")
    def test_03_reboot_vm(self):
        """Test Reboot Virtual Machine
        """

        # Validate the following
        # 1. Should be able to login to the VM.
        # 2. listVM command should return the deployed VM.
        #    State of this VM should be "Running"

        self.debug("Rebooting VM - ID: %s" % self.virtual_machine.id)
        self.small_virtual_machine.reboot(self.apiclient)

        list_vm_response = VirtualMachine.list(
                                            self.apiclient,
                                            id=self.small_virtual_machine.id
                                            )
        self.assertEqual(
                            isinstance(list_vm_response, list),
                            True,
                            "Check list response returns a valid list"
                        )

        self.assertNotEqual(
                            len(list_vm_response),
                            0,
                            "Check VM avaliable in List Virtual Machines"
                        )

        self.assertEqual(
                            list_vm_response[0].state,
                            "Running",
                            "Check virtual machine is in running state"
                        )
        return


    @attr(tags = ["devcloud", "advanced", "advancedns", "smoke", "basic", "sg"], required_hardware="false")
    def test_06_destroy_vm(self):
        """Test destroy Virtual Machine
        """

        # Validate the following
        # 1. Should not be able to login to the VM.
        # 2. listVM command should return this VM.State
        #    of this VM should be "Destroyed".

        self.debug("Destroy VM - ID: %s" % self.small_virtual_machine.id)
        self.small_virtual_machine.delete(self.apiclient, expunge=False)

        list_vm_response = VirtualMachine.list(
                                            self.apiclient,
                                            id=self.small_virtual_machine.id
                                            )
        self.assertEqual(
                            isinstance(list_vm_response, list),
                            True,
                            "Check list response returns a valid list"
                        )

        self.assertNotEqual(
                            len(list_vm_response),
                            0,
                            "Check VM avaliable in List Virtual Machines"
                        )

        self.assertEqual(
                            list_vm_response[0].state,
                            "Destroyed",
                            "Check virtual machine is in destroyed state"
                        )
        return

    @attr(tags = ["devcloud", "advanced", "advancedns", "smoke", "basic", "sg"], required_hardware="false")
    def test_07_restore_vm(self):
        #TODO: SIMENH: add another test the data on the restored VM.
        """Test recover Virtual Machine
        """

        # Validate the following
        # 1. listVM command should return this VM.
        #    State of this VM should be "Stopped".
        # 2. We should be able to Start this VM successfully.

        self.debug("Recovering VM - ID: %s" % self.small_virtual_machine.id)

        cmd = recoverVirtualMachine.recoverVirtualMachineCmd()
        cmd.id = self.small_virtual_machine.id
        self.apiclient.recoverVirtualMachine(cmd)

        list_vm_response = VirtualMachine.list(
                                            self.apiclient,
                                            id=self.small_virtual_machine.id
                                            )
        self.assertEqual(
                            isinstance(list_vm_response, list),
                            True,
                            "Check list response returns a valid list"
                        )

        self.assertNotEqual(
                            len(list_vm_response),
                            0,
                            "Check VM avaliable in List Virtual Machines"
                        )

        self.assertEqual(
                            list_vm_response[0].state,
                            "Stopped",
                            "Check virtual machine is in Stopped state"
                        )

        return


    @attr(configuration = "expunge.interval")
    @attr(configuration = "expunge.delay")
    @attr(tags = ["devcloud", "advanced", "advancedns", "smoke", "basic", "sg"], required_hardware="false")
    def test_09_expunge_vm(self):
        """Test destroy(expunge) Virtual Machine
        """
        # Validate the following
        # 1. listVM command should NOT  return this VM any more.

        self.debug("Expunge VM-ID: %s" % self.small_virtual_machine.id)

        cmd = destroyVirtualMachine.destroyVirtualMachineCmd()
        cmd.id = self.small_virtual_machine.id
        self.apiclient.destroyVirtualMachine(cmd)

        config = Configurations.list(
                                     self.apiclient,
                                     name='expunge.delay'
                                     )

        expunge_delay = int(config[0].value)
        time.sleep(expunge_delay * 2)

        #VM should be destroyed unless expunge thread hasn't run
        #Wait for two cycles of the expunge thread
        config = Configurations.list(
                                     self.apiclient,
                                     name='expunge.interval'
                                     )
        expunge_cycle = int(config[0].value)
        wait_time = expunge_cycle * 4
        while wait_time >= 0:
            list_vm_response = VirtualMachine.list(
                                                self.apiclient,
                                                id=self.small_virtual_machine.id
                                                )
            if not list_vm_response:
                break
            self.debug("Waiting for VM to expunge")
            time.sleep(expunge_cycle)
            wait_time = wait_time - expunge_cycle

        self.debug("listVirtualMachines response: %s" % list_vm_response)

        self.assertEqual(list_vm_response,None,"Check Expunged virtual machine is in listVirtualMachines response")
        return

    @attr(tags = ["advanced", "advancedns", "smoke", "basic", "sg"], required_hardware="true")
    def test_10_attachAndDetach_iso(self):
        """Test for attach and detach ISO to virtual machine"""

        # Validate the following
        # 1. Create ISO
        # 2. Attach ISO to VM
        # 3. Log in to the VM.
        # 4. The device should be available for use
        # 5. Detach ISO
        # 6. Check the device is properly detached by logging into VM

        if self.hypervisor.lower() in ["lxc"]:
            self.skipTest("ISOs are not supported on LXC")

        iso = Iso.create(
                         self.apiclient,
                         self.services["iso1"],
                         account=self.account.name,
                         domainid=self.account.domainid
                         )

        self.debug("Successfully created ISO with ID: %s" % iso.id)
        try:
            iso.download(self.apiclient)
        except Exception as e:
            self.fail("Exception while downloading ISO %s: %s"\
                      % (iso.id, e))

        self.debug("Attach ISO with ID: %s to VM ID: %s" % (
                                                    iso.id,
                                                    self.virtual_machine.id
                                                    ))
        #Attach ISO to virtual machine
        cmd = attachIso.attachIsoCmd()
        cmd.id = iso.id
        cmd.virtualmachineid = self.virtual_machine.id
        self.apiclient.attachIso(cmd)

        try:
            ssh_client = self.virtual_machine.get_ssh_client(reconnect=True)
        except Exception as e:
            self.fail("SSH failed for virtual machine: %s - %s" %
                                (self.virtual_machine.ipaddress, e))

        mount_dir = "/mnt/tmp"
        cmds = "mkdir -p %s" % mount_dir
        self.assert_(ssh_client.execute(cmds) == [], "mkdir failed within guest")

        for diskdevice in self.services["diskdevice"]:
            res = ssh_client.execute("mount -rt iso9660 {} {}".format(diskdevice, mount_dir))
            if res == []:
                self.services["mount"] = diskdevice
                break
        else:
            self.fail("No mount points matched. Mount was unsuccessful")

        c = "mount |grep %s|head -1" % self.services["mount"]
        res = ssh_client.execute(c)
        size = ssh_client.execute("du %s | tail -1" % self.services["mount"])
        self.debug("Found a mount point at %s with size %s" % (res, size))

        # Get ISO size
        iso_response = Iso.list(
                                 self.apiclient,
                                 id=iso.id
                                 )
        self.assertEqual(
                            isinstance(iso_response, list),
                            True,
                            "Check list response returns a valid list"
                        )

        try:
            #Unmount ISO
            command = "umount %s" % mount_dir
            ssh_client.execute(command)
        except Exception as e:
            self.fail("SSH failed for virtual machine: %s - %s" %
                                (self.virtual_machine.ipaddress, e))

        #Detach from VM
        cmd = detachIso.detachIsoCmd()
        cmd.virtualmachineid = self.virtual_machine.id
        self.apiclient.detachIso(cmd)

        try:
            res = ssh_client.execute(c)
        except Exception as e:
            self.fail("SSH failed for virtual machine: %s - %s" %
                                (self.virtual_machine.ipaddress, e))

        # Check if ISO is properly detached from VM (using fdisk)
        result = self.services["mount"] in str(res)

        self.assertEqual(
                         result,
                         False,
                         "Check if ISO is detached from virtual machine"
                         )
        return
