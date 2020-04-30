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
                                  resizeVolume)
import time
import pprint
import random
import subprocess
from storpool import spapi
from marvin.configGenerator import configuration

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
            {"name":"StorPool-%d" % random.randint(0, 100)},
            zoneid=cls.zone.id,
            templateid=template.id,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            hostid = cls.host[0].id,
            rootdisksize=10
        )

        cls.virtual_machine2 = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-Resize-%d" % random.randint(0, 100)},
            zoneid=cls.zone.id,
            templateid=template.id,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            hostid = cls.host[0].id,
            rootdisksize=10
        )

        cls.vm_migrate = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-Migrate-%d" % random.randint(0, 100)},
            zoneid=cls.zone.id,
            templateid=template.id,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            hostid = cls.host[0].id,
            rootdisksize=10
        )

        cls.vm_cluster = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-Cluster-%d" % random.randint(0, 100)},
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



    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_01_snapshot_to_template(self):
        ''' Create template from snapshot without bypass secondary storage
        '''
        volume = Volume.list(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            type = "ROOT"
            )

        backup_config = list_configurations(
            self.apiclient,
            name = "sp.bypass.secondary.storage")
        if (backup_config[0].value == "true"):
            backup_config = Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "false")
        snapshot = Snapshot.create(
           self.apiclient,
            volume_id = volume[0].id
            )
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
        self._cleanup.append(virtual_machine)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_02_snapshot_to_template_bypass_secondary(self):
        ''' Test Create Template from snapshot bypassing secondary storage
        '''
        ##cls.virtual_machine
        volume = list_volumes(
                        self.apiclient,
                        virtualmachineid = self.virtual_machine.id,
                        type = "ROOT"
                        )
        try:
            sp_volume = self.spapi.volumeList(volumeName = volume[0].id)
            self.debug('################ %s' % sp_volume)
        except spapi.ApiError as err:
            self.assertEquals(err.name, "objectDoesNotExist", "Error")

        backup_config = list_configurations(
            self.apiclient,
            name = "sp.bypass.secondary.storage")
        if (backup_config[0].value == "false"):
            backup_config = Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "true")

        snapshot = Snapshot.create(
           self.apiclient,
            volume_id = volume[0].id
            )
        try:
            sp_snapshot = self.spapi.snapshotList(snapshotName = snapshot.id)
            self.debug('################ %s' % sp_snapshot)
        except spapi.ApiError as err:
            self.assertEquals(err.name, "objectDoesNotExist", "Error")

        self.assertIsNotNone(snapshot, "Could not create snapshot")
        self.assertIsInstance(snapshot, Snapshot, "Snapshot is not an instance of Snapshot")

        template = self.create_template_from_snapshot(
            self.apiclient,
            self.services,
            snapshotid = snapshot.id
            )

        try:
            sp_template = self.spapi.snapshotList(snapshotName = template.id)
            self.debug('################ %s' % sp_template)

        except spapi.ApiError as err:
            self.assertEquals(err.name, "objectDoesNotExist", "Error")
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
        self._cleanup.append(virtual_machine)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_03_snapshot_volume_with_secondary(self):
        '''
            Test Create snapshot and backup to secondary
        '''
        backup_config = list_configurations(
            self.apiclient,
            name = "sp.bypass.secondary.storage")
        if (backup_config[0].value == "true"):
            backup_config = Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "false")
        volume = list_volumes(
                        self.apiclient,
                        virtualmachineid = self.virtual_machine.id,
                        type = "ROOT"
                        )
        snapshot = Snapshot.create(
           self.apiclient,
            volume_id = volume[0].id
            )
        self.assertIsNotNone(snapshot, "Could not create snapshot")

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_04_snapshot_volume_bypass_secondary(self):
        '''
            Test snapshot bypassing secondary
        '''
        backup_config = list_configurations(
            self.apiclient,
            name = "sp.bypass.secondary.storage")
        if (backup_config[0].value == "false"):
            backup_config = Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "true")
        volume = list_volumes(
                        self.apiclient,
                        virtualmachineid = self.virtual_machine.id,
                        type = "ROOT"
                        )
        snapshot = Snapshot.create(
           self.apiclient,
            volume_id = volume[0].id
            )
        self.assertIsNotNone(snapshot, "Could not create snapshot")

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_05_delete_template_bypassed_secondary(self):
        ''' Test delete template from snapshot bypassed secondary storage
        '''
        volume = list_volumes(
                        self.apiclient,
                        virtualmachineid = self.virtual_machine.id,
                        type = "ROOT"
                        )
        try:
            sp_volume = self.spapi.volumeList(volumeName = volume[0].id)
            self.debug('################ %s' % sp_volume)
        except spapi.ApiError as err:
            self.assertEquals(err.name, "objectDoesNotExist", "Error")

        backup_config = list_configurations(
            self.apiclient,
            name = "sp.bypass.secondary.storage")
        if (backup_config[0].value == "false"):
            backup_config = Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "true")

        snapshot = Snapshot.create(
           self.apiclient,
            volume_id = volume[0].id
            )
        try:
            sp_snapshot = self.spapi.snapshotList(snapshotName = snapshot.id)
            self.debug('################ %s' % sp_snapshot)
        except spapi.ApiError as err:
            self.assertEquals(err.name, "objectDoesNotExist", "Error")

        self.assertIsNotNone(snapshot, "Could not create snapshot")
        self.assertIsInstance(snapshot, Snapshot, "Snapshot is not an instance of Snapshot")

        template = self.create_template_from_snapshot(
            self.apiclient,
            self.services,
            snapshotid = snapshot.id
            )

        try:
            sp_template = self.spapi.snapshotList(snapshotName = template.id)
            self.debug('################ %s' % sp_template)

        except spapi.ApiError as err:
            self.assertEquals(err.name, "objectDoesNotExist", "Error")


        self.assertIsNotNone(template, "Template is None")
        self.assertIsInstance(template, Template, "Template is instance of template")
        temp = Template.delete(template, self.apiclient, self.zone.id)
        self.assertIsNone(temp, "Template was not deleted")
        try:
            sp_template = self.spapi.snapshotList(snapshotName = template.id)
            self.debug('################ %s' % sp_template)

        except spapi.ApiError as err:
            self.debug('################ snapshot template does not exists %s' % err.name)
            self.assertEquals(err.name, "objectDoesNotExist", "Error")
        self._cleanup.append(snapshot)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_06_template_from_snapshot(self):
        ''' Test create template bypassing secondary from snapshot which is backed up on secondary storage
        '''
        ##cls.virtual_machine
        volume = list_volumes(
                        self.apiclient,
                        virtualmachineid = self.virtual_machine.id,
                        type = "ROOT"
                        )
        try:
            sp_volume = self.spapi.volumeList(volumeName = volume[0].id)
            self.debug('################ %s' % sp_volume)
        except spapi.ApiError as err:
            self.assertEquals(err.name, "objectDoesNotExist", "Error")

        backup_config = list_configurations(
            self.apiclient,
            name = "sp.bypass.secondary.storage")
        if (backup_config[0].value == "true"):
            backup_config = Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "false")

        snapshot = Snapshot.create(
           self.apiclient,
            volume_id = volume[0].id
            )
        try:
            sp_snapshot = self.spapi.snapshotList(snapshotName = snapshot.id)
            self.debug('################ %s' % sp_snapshot)
        except spapi.ApiError as err:
            self.assertEquals(err.name, "objectDoesNotExist", "Error")

        self.assertIsNotNone(snapshot, "Could not create snapshot")
        self.assertIsInstance(snapshot, Snapshot, "Snapshot is not an instance of Snapshot")

        backup_config = list_configurations(
            self.apiclient,
            name = "sp.bypass.secondary.storage")
        if (backup_config[0].value == "false"):
            backup_config = Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "true")

        template = self.create_template_from_snapshot(
            self.apiclient,
            self.services,
            snapshotid = snapshot.id
            )

        try:
            sp_template = self.spapi.snapshotList(snapshotName = template.id)
            self.debug('################ %s' % sp_template)

        except spapi.ApiError as err:
            self.assertEquals(err.name, "objectDoesNotExist", "Error")


        self.assertIsNotNone(template, "Template is None")
        self.assertIsInstance(template, Template, "Template is instance of template")
        temp = Template.delete(template, self.apiclient, self.zone.id)
        self.assertIsNone(temp, "Template was not deleted")
        try:
            sp_template = self.spapi.snapshotList(snapshotName = template.id)
            self.debug('################ %s' % sp_template)

        except spapi.ApiError as err:
            self.debug('################ snapshot template does not exists %s' % err.name)
            self.assertEquals(err.name, "objectDoesNotExist", "Error")
        self._cleanup.append(snapshot)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_07_vm_from_bypassed_template(self):
        '''Create virtual machine with sp.bypass.secondary.storage=false
        from template created on StorPool and Secondary Storage'''

        volume = list_volumes(
                        self.apiclient,
                        virtualmachineid = self.virtual_machine.id,
                        type = "ROOT"
                        )
        try:
            sp_volume = self.spapi.volumeList(volumeName = volume[0].id)
            self.debug('################ %s' % sp_volume)
        except spapi.ApiError as err:
            self.assertEquals(err.name, "objectDoesNotExist", "Error")

        backup_config = list_configurations(
            self.apiclient,
            name = "sp.bypass.secondary.storage")
        if (backup_config[0].value == "false"):
            backup_config = Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "true")

        snapshot = Snapshot.create(
           self.apiclient,
            volume_id = volume[0].id
            )
        try:
            sp_snapshot = self.spapi.snapshotList(snapshotName = snapshot.id)
            self.debug('################ %s' % sp_snapshot)
        except spapi.ApiError as err:
            raise Exception(err.name, "objectDoesNotExist", "Error")

        self.assertIsNotNone(snapshot, "Could not create snapshot")
        self.assertIsInstance(snapshot, Snapshot, "Snapshot is not an instance of Snapshot")

        template = self.create_template_from_snapshot(
            self.apiclient,
            self.services,
            snapshotid = snapshot.id
            )

        try:
            sp_template = self.spapi.snapshotList(snapshotName = template.id)
            self.debug('################ %s' % sp_template)

        except spapi.ApiError as err:
            raise Exception(err.name, "objectDoesNotExist", "Error")

        self.assertIsNotNone(template, "Template is None")
        self.assertIsInstance(template, Template, "Template is instance of template")   

        backup_config = list_configurations(
            self.apiclient,
            name = "sp.bypass.secondary.storage")
        if (backup_config[0].value == "true"):
            backup_config = Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "false")  

        vm = VirtualMachine.create(
            self.apiclient,
            {"name":"StorPool-Templ-%d" % random.randint(0, 100)},
            zoneid=self.zone.id,
            templateid = template.id,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            hostid = self.host[0].id,
            rootdisksize=10,
            )

        ssh_client = vm.get_ssh_client(reconnect=True)

    @classmethod
    def list_hosts_by_cluster_id(cls, clusterid):
        """List all Hosts matching criteria"""
        cmd = listHosts.listHostsCmd()
        cmd.clusterid = clusterid
        return(cls.apiclient.listHosts(cmd))

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
