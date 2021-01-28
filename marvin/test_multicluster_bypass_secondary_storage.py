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
                                  getVolumeSnapshotDetails,
                                  resizeVolume)
import time
import pprint
import random
import subprocess
from storpool import spapi
from storpool import sptypes
from marvin.configGenerator import configuration
import uuid
from sp_util import (TestData, StorPoolHelper)


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
        cls.spapi = spapi.Api.fromConfig(multiCluster=True)

        testClient = super(TestStoragePool, cls).getClsTestClient()
        cls.apiclient = testClient.getApiClient()

        td = TestData()
        cls.testdata = td.testdata
        cls.helper = StorPoolHelper()
        cls._cleanup = []

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

        cls.template_name = cls.testdata[TestData.primaryStorage].get("name")

        storage_pool = list_storage_pools(
            cls.apiclient,
            name= cls.template_name
            )
        if storage_pool is None:
            storage_pool = cls.helper.create_sp_template_and_storage_pool(cls.apiclient, cls.template_name, cls.testdata[TestData.primaryStorage], cls.zone.id)
        else:
            storage_pool = storage_pool[0]

        cls.storage_pool = storage_pool
        cls.debug(pprint.pformat(storage_pool))


        service_offerings_ssd = list_service_offering(
            cls.apiclient,
            name= cls.testdata[TestData.serviceOffering].get("name")
            )
        if service_offerings_ssd is None:
            service_offerings_ssd = ServiceOffering.create(cls.apiclient, cls.testdata[TestData.serviceOffering])
        else:
            service_offerings_ssd = service_offerings_ssd[0]



        cls.service_offering = service_offerings_ssd
        cls.debug(pprint.pformat(cls.service_offering))

        template = get_template(
             cls.apiclient,
            cls.zone.id,
            account = "system"
        )

        cls.local_cluster = cls.helper.get_local_cluster(cls.apiclient, zoneid = cls.zone.id)
        cls.host = cls.helper.list_hosts_by_cluster_id(cls.apiclient, cls.local_cluster.id)

        cls.debug(pprint.pformat(template))
        cls.debug(pprint.pformat(cls.hypervisor))

        if template == FAILED:
            assert False, "get_template() failed to return template\
                    with description %s" % cls.services["ostype"]

        cls.services["domainid"] = cls.domain.id
        cls.services["zoneid"] = cls.zone.id
        cls.services["template"] = template.id
        cls.services["diskofferingid"] = cls.disk_offerings.id

        # Create VMs, VMs etc
        cls.account = Account.create(
                            cls.apiclient,
                            cls.services["account"],
                            domainid=cls.domain.id
                            )

        securitygroup = SecurityGroup.list(cls.apiclient, account = cls.account.name, domainid= cls.account.domainid)[0]
        cls.helper.set_securityGroups(cls.apiclient, account = cls.account.name, domainid= cls.account.domainid, id = securitygroup.id)
        cls._cleanup.append(cls.account)

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

        cls.volume = Volume.create(
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
            accountid=cls.account.name,
            domainid=cls.account.domainid,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            hostid = cls.host[0].id,
            rootdisksize=10
        )

        cls.virtual_machine3 = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
            accountid=cls.account.name,
            domainid=cls.account.domainid,
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
        return

    @classmethod
    def tearDownClass(cls):
        cls.cleanUpCloudStack()

    @classmethod
    def cleanUpCloudStack(cls):
        try:
            # Cleanup resources used
            cls.debug("================ %s" % cls._cleanup)
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
    def test_01_snapshot_to_template(self):
        ''' Create template from snapshot without bypass secondary storage
        '''
        volume = Volume.list(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            type = "ROOT",
            listall = True,
            )

        Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "false")
        snapshot = Snapshot.create(
           self.apiclient,
            volume_id = volume[0].id,
            account=self.account.name,
            domainid=self.account.domainid,
            )
        self.assertIsNotNone(snapshot, "Could not create snapshot")
        self.assertIsInstance(snapshot, Snapshot, "Snapshot is not an instance of Snapshot")

        template = self.helper.create_template_from_snapshot(
            self.apiclient,
            self.services,
            snapshotid = snapshot.id
            )
        virtual_machine = VirtualMachine.create(self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            accountid=self.account.name,
            domainid=self.account.domainid,
            templateid=template.id,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
            )
        ssh_client = virtual_machine.get_ssh_client(reconnect=True)

        self.assertIsNotNone(template, "Template is None")
        self.assertIsInstance(template, Template, "Template is instance of template")
        self._cleanup.append(template)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_02_snapshot_to_template_bypass_secondary(self):
        ''' Test Create Template from snapshot bypassing secondary storage
        '''
        ##cls.virtual_machine
        volume = list_volumes(
                        self.apiclient,
                        virtualmachineid = self.virtual_machine.id,
                        type = "ROOT",
                        listall = True,
                        )
        try:
            name = volume[0].path.split("/")[3]
            sp_volume = self.spapi.volumeList(volumeName = "~" + name)
            self.debug('################ %s' % sp_volume)
        except spapi.ApiError as err:
            raise Exception(err)

        Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "true")

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

        snapshot = Snapshot.create(
           self.apiclient,
            volume_id = volume[0].id,
            account=self.account.name,
            domainid=self.account.domainid,
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
                    flag = True
                    self.debug('################ %s' % sp_snapshot)
            if flag == False:
                raise Exception("Could not find snasphot in snapshot_details")
        except spapi.ApiError as err:
               raise Exception(err)

        self.assertIsNotNone(snapshot, "Could not create snapshot")
        self.assertIsInstance(snapshot, Snapshot, "Snapshot is not an instance of Snapshot")

        template = self.helper.create_template_from_snapshot(
            self.apiclient,
            self.services,
            snapshotid = snapshot.id
            )

        flag = False
        sp_snapshots = self.spapi.snapshotsList()
        for snap in sp_snapshots:
            tags = snap.tags
            for t in tags:
                if tags[t] == template.id:
                    flag = True
                    break
            else:
                continue
            break

        if flag is False:
            raise Exception("Template does not exists in Storpool")
        virtual_machine = VirtualMachine.create(self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=template.id,
            accountid=self.account.name,
            domainid=self.account.domainid,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
            )

        try:
            ssh_client = virtual_machine.get_ssh_client(reconnect=True)

            cmds = [
                "cat %s/%s" % (self.test_dir, self.random_data)
            ]

            for c in cmds:
                self.debug(c)
                result = ssh_client.execute(c)
                self.debug(result)

        except Exception:
            self.fail("SSH failed for Virtual machine: %s" %
                      virtual_machine.ipaddress)

        self.assertEqual(
            self.random_data_0,
            result[0],
            "Check the random data is equal with the ramdom file!"
        )
        self.assertIsNotNone(template, "Template is None")
        self.assertIsInstance(template, Template, "Template is instance of template")
        self._cleanup.append(template)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_03_snapshot_volume_with_secondary(self):
        '''
            Test Create snapshot and backup to secondary
        '''
        Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "false")
        volume = list_volumes(
                        self.apiclient,
                        virtualmachineid = self.virtual_machine.id,
                        type = "ROOT",
                        listall = True,
                        )
        snapshot = Snapshot.create(
           self.apiclient,
            volume_id = volume[0].id,
            account=self.account.name,
            domainid=self.account.domainid,
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
                    flag = True
                    self.debug('################ %s' % sp_snapshot)
            if flag == False:
                raise Exception("Could not find snapshot in snapshot_details")
        except spapi.ApiError as err:
            raise Exception(err)
        self.assertIsNotNone(snapshot, "Could not create snapshot")

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_04_snapshot_volume_bypass_secondary(self):
        '''
            Test snapshot bypassing secondary
        '''
        Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "true")
        volume = list_volumes(
                        self.apiclient,
                        virtualmachineid = self.virtual_machine.id,
                        type = "ROOT",
                        listall = True,
                        )
        snapshot = Snapshot.create(
           self.apiclient,
            volume_id = volume[0].id,
            account=self.account.name,
            domainid=self.account.domainid,
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
                    flag = True
                    self.debug('################ %s' % sp_snapshot)
            if flag == False:
                raise Exception("Could not find snapshot in snapshot details")
        except spapi.ApiError as err:
            raise Exception(err)
        self.assertIsNotNone(snapshot, "Could not create snapshot")

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_05_delete_template_bypassed_secondary(self):
        ''' Test delete template from snapshot bypassed secondary storage
        '''
        volume = list_volumes(
                        self.apiclient,
                        virtualmachineid = self.virtual_machine.id,
                        type = "ROOT",
                        listall = True,
                        )
        try:
            name = volume[0].path.split("/")[3]
            sp_volume = self.spapi.volumeList(volumeName = "~" + name)
            self.debug('################ %s' % sp_volume)
        except spapi.ApiError as err:
            raise Exception(err)

        Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "true")

        snapshot = Snapshot.create(
           self.apiclient,
            volume_id = volume[0].id,
            account=self.account.name,
            domainid=self.account.domainid,
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
                    flag = True
                    self.debug('################ %s' % sp_snapshot)
            if flag == False:
                raise Exception("Could not find snapshot in snapshot details")
        except spapi.ApiError as err:
            raise Exception(err)

        self.assertIsNotNone(snapshot, "Could not create snapshot")
        self.assertIsInstance(snapshot, Snapshot, "Snapshot is not an instance of Snapshot")

        template = self.helper.create_template_from_snapshot(
            self.apiclient,
            self.services,
            snapshotid = snapshot.id
            )

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
            raise Exception("Template does not exists in Storpool")

        self.assertIsNotNone(template, "Template is None")
        self.assertIsInstance(template, Template, "Template is instance of template")
        temp = Template.delete(template, self.apiclient, self.zone.id)
        self.assertIsNone(temp, "Template was not deleted")

        try:
            sp_snapshot = self.spapi.snapshotList(snapshotName = "~" + storpoolGlId)
            if sp_snapshot is not None:
                raise Exception("Snapshot exists on StorPool name " + storpoolGlId)
        except spapi.ApiError as err:
                self.debug("Do nothing the template has to be deleted")

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_06_template_from_snapshot(self):
        ''' Test create template bypassing secondary from snapshot which is backed up on secondary storage
        '''
        ##cls.virtual_machine
        volume = list_volumes(
                        self.apiclient,
                        virtualmachineid = self.virtual_machine.id,
                        type = "ROOT",
                        listall = True,
                        )
        try:
            name = volume[0].path.split("/")[3]
            sp_volume = self.spapi.volumeList(volumeName = "~" + name)
            self.debug('################ %s' % sp_volume)
        except spapi.ApiError as err:
            raise Exception(err)

        Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "false")

        snapshot = Snapshot.create(
           self.apiclient,
            volume_id = volume[0].id,
            account=self.account.name,
            domainid=self.account.domainid,
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
                    flag = True
                    self.debug('################ %s' % sp_snapshot)
            if flag == False:
                raise Exception("Could not find snapshot in snapsho details")
        except spapi.ApiError as err:
           raise Exception(err)

        self.assertIsNotNone(snapshot, "Could not create snapshot")
        self.assertIsInstance(snapshot, Snapshot, "Snapshot is not an instance of Snapshot")

        Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "true")

        template = self.helper.create_template_from_snapshot(
            self.apiclient,
            self.services,
            snapshotid = snapshot.id
            )

        flag = False
        globalId = None
        sp_snapshots = self.spapi.snapshotsList()
        for snap in sp_snapshots:
            tags = snap.tags
            for t in tags:
                if tags[t] == template.id:
                    flag = True
                    globalId = snap.globalId
                    break
            else:
                continue
            break

        if flag is False:
            raise Exception("Template does not exists in Storpool")


        self.assertIsNotNone(template, "Template is None")
        self.assertIsInstance(template, Template, "Template is instance of template")
        temp = Template.delete(template, self.apiclient, self.zone.id)
        self.assertIsNone(temp, "Template was not deleted")

        if globalId is not None:
            try:
                sp_snapshot = self.spapi.snapshotList(snapshotName = "~" + globalId)
                if sp_snapshot is not None:
                    raise Exception("Snapshot does not exists on Storpool name" + globalId)
            except spapi.ApiError as err:
                self.debug("Do nothing the template has to be deleted")
        else:
            flag = False
            sp_snapshots = self.spapi.snapshotsList()
            for snap in sp_snapshots:
                tags = snap.tags
                for t in tags:
                    if tags[t] == template.id:
                        flag = True
                        break
                else:
                    continue
                break

            if flag is True:
                raise Exception("Template should not exists in Storpool")

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_07_delete_snapshot_of_deleted_volume(self):
        ''' Delete snapshot and template if volume is already deleted, not bypassing secondary
        '''

        Configurations.update(self.apiclient,
        name = "sp.bypass.secondary.storage",
        value = "false")

        volume = Volume.create(
            self.apiclient,
            {"diskname":"StorPoolDisk-Delete" },
            zoneid = self.zone.id,
            diskofferingid = self.disk_offerings.id,
            account=self.account.name,
            domainid=self.account.domainid,
            )
        delete = volume
        self.virtual_machine2.stop(self.apiclient, forced=True)
        self.virtual_machine2.attach_volume(
            self.apiclient,
            volume
            )
        self.virtual_machine2.detach_volume(
            self.apiclient,
            volume
            )

        volume = list_volumes(self.apiclient, id = volume.id, listall = True,)

        name = volume[0].path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
        except spapi.ApiError as err:
           raise Exception(err)

        snapshot = Snapshot.create(
            self.apiclient,
            volume_id = volume[0].id,
            account=self.account.name,
            domainid=self.account.domainid,
            )

        try:
            cmd = getVolumeSnapshotDetails.getVolumeSnapshotDetailsCmd()
            cmd.snapshotid = snapshot.id
            snapshot_details = self.apiclient.getVolumeSnapshotDetails(cmd)
            flag = False
            for s in snapshot_details:
                if s["snapshotDetailsName"] == snapshot.id:
                    name = s["snapshotDetailsValue"].split("/")[3]
                    try:
                        sp_snapshot = self.spapi.snapshotList(snapshotName = "~" + name)
                        self.debug('################ %s' % sp_snapshot)
                        flag = True
                    except spapi.ApiError as err:
                       raise Exception(err)
            if flag == False:
                raise Exception("Could not finad snapshot in snapshot details")
        except Exception as err:
            raise Exception(err)

        template = self.helper.create_template_from_snapshot(self.apiclient, self.services, snapshotid = snapshot.id)

        template_from_volume = self.helper.create_template_from_snapshot(self.apiclient, self.services, volumeid = volume[0].id)

        Volume.delete(delete, self.apiclient, )
        Snapshot.delete(snapshot, self.apiclient)

        flag = False

        try:
            cmd = getVolumeSnapshotDetails.getVolumeSnapshotDetailsCmd()
            cmd.snapshotid = snapshot.id
            snapshot_details = self.apiclient.getVolumeSnapshotDetails(cmd)
            if snapshot_details is not None:
                try:
                    for s in snapshot_details:
                        if s["snapshotDetailsName"] == snapshot.id:
                            name = s["snapshotDetailsValue"].split("/")[3]
                            sp_snapshot = self.spapi.snapshotList(snapshotName = "~" + name)
                            self.debug('################ The snapshot had to be deleted %s' % sp_snapshot)
                            flag = True
                except spapi.ApiError as err:
                    flag = False
    
            if flag is True:
                raise Exception("Snapshot was not deleted")
        except Exception as err:
            self.debug('Snapshot was deleted %s' % err)

        Template.delete(template, self.apiclient, zoneid = self.zone.id)
        Template.delete(template_from_volume, self.apiclient, zoneid = self.zone.id)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_08_delete_snapshot_of_deleted_volume(self):
        ''' Delete snapshot and template if volume is already deleted, bypassing secondary
        '''

        Configurations.update(self.apiclient,
        name = "sp.bypass.secondary.storage",
        value = "true")

        volume = Volume.create(
            self.apiclient,
            {"diskname":"StorPoolDisk-Delete" },
            zoneid = self.zone.id,
            diskofferingid = self.disk_offerings.id,
            account=self.account.name,
            domainid=self.account.domainid,
            )
        delete = volume
        self.virtual_machine2.attach_volume(
            self.apiclient,
            volume
            )
        self.virtual_machine2.detach_volume(
            self.apiclient,
            volume
            )

        volume = list_volumes(self.apiclient, id = volume.id, listall = True,)

        name = volume[0].path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
        except spapi.ApiError as err:
           raise Exception(err)

        snapshot = Snapshot.create(
            self.apiclient,
             volume_id = volume[0].id
            )

        try:
            cmd = getVolumeSnapshotDetails.getVolumeSnapshotDetailsCmd()
            cmd.snapshotid = snapshot.id
            snapshot_details = self.apiclient.getVolumeSnapshotDetails(cmd)
            if snapshot_details is not None:
                flag = False
                for s in snapshot_details:
                    if s["snapshotDetailsName"] == snapshot.id:
                        name = s["snapshotDetailsValue"].split("/")[3]
                        try:
                            sp_snapshot = self.spapi.snapshotList(snapshotName = "~" + name)
                            self.debug('################ %s' % sp_snapshot)
                            flag = True
                        except spapi.ApiError as err:
                           raise Exception(err)
                if flag == False:
                    raise Exception("Could not find snapshot in snapshot details")
        except Exception as err:
            raise Exception(err)  

        template = self.helper.create_template_from_snapshot(self.apiclient, self.services, snapshotid = snapshot.id)

        Volume.delete(delete, self.apiclient, )
        Snapshot.delete(snapshot, self.apiclient)

        flag = False
        try:
            cmd = getVolumeSnapshotDetails.getVolumeSnapshotDetailsCmd()
            cmd.snapshotid = snapshot.id
            snapshot_details = self.apiclient.getVolumeSnapshotDetails(cmd)
            if snapshot_details is not None:
                try:
                    for s in snapshot_details:
                        if s["snapshotDetailsName"] == snapshot.id:
                            name = s["snapshotDetailsValue"].split("/")[3]
                            sp_snapshot = self.spapi.snapshotList(snapshotName = "~" + name)
                            self.debug('################ The snapshot had to be deleted %s' % sp_snapshot)
                            flag = True
                except spapi.ApiError as err:
                    flag = False
    
            if flag is True:
                raise Exception("Snapshot was not deleted")
        except Exception as err:
            self.debug('Snapshot was deleted %s' % err)
            

        Template.delete(template, self.apiclient, zoneid = self.zone.id)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_09_vm_from_bypassed_template(self):
        '''Create virtual machine with sp.bypass.secondary.storage=false
        from template created on StorPool and Secondary Storage'''

        volume = list_volumes(
                        self.apiclient,
                        virtualmachineid = self.virtual_machine.id,
                        type = "ROOT",
                        listall = True,
                        )

        name = volume[0].path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
        except spapi.ApiError as err:
           raise Exception(err)

        Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "true")

        snapshot = Snapshot.create(
           self.apiclient,
            volume_id = volume[0].id,
            account=self.account.name,
            domainid=self.account.domainid,
            )

        try:
            cmd = getVolumeSnapshotDetails.getVolumeSnapshotDetailsCmd()
            cmd.snapshotid = snapshot.id
            snapshot_details = self.apiclient.getVolumeSnapshotDetails(cmd)
            flag = False
            for s in snapshot_details:
                if s["snapshotDetailsName"] == snapshot.id:
                    name = s["snapshotDetailsValue"].split("/")[3]
                    try:
                        sp_snapshot = self.spapi.snapshotList(snapshotName = "~" + name)
                        self.debug('################ %s' % sp_snapshot)
                        flag = True
                    except spapi.ApiError as err:
                       raise Exception(err)
            if flag == False:
                raise Exception("Could not find snapshot in snapshot details")
        except Exception as err:
            raise Exception(err)

        self.assertIsNotNone(snapshot, "Could not create snapshot")
        self.assertIsInstance(snapshot, Snapshot, "Snapshot is not an instance of Snapshot")

        template = self.helper.create_template_from_snapshot(
            self.apiclient,
            self.services,
            snapshotid = snapshot.id
            )
        self._cleanup.append(template)

        flag = False
        sp_snapshots = self.spapi.snapshotsList()
        for snap in sp_snapshots:
            tags = snap.tags
            for t in tags:
                if tags[t] == template.id:
                    flag = True
                    break
            else:
                continue
            break

        if flag is False:
            raise Exception("Template does not exists in Storpool")


        self.assertIsNotNone(template, "Template is None")
        self.assertIsInstance(template, Template, "Template is instance of template")

        Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "false")  

        vm = VirtualMachine.create(
            self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid = template.id,
            accountid=self.account.name,
            domainid=self.account.domainid,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            hostid = self.host[0].id,
            rootdisksize=10,
            )

        ssh_client = vm.get_ssh_client(reconnect=True)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_10_snapshot_to_template_bypass_secondary(self):
        ''' Test Create Template bypassing secondary storage from snapshot on secondary storage
        '''
        ##cls.virtual_machine
        volume = list_volumes(
                        self.apiclient,
                        virtualmachineid = self.virtual_machine.id,
                        type = "ROOT",
                        listall = True,
                        )
        try:
            name = volume[0].path.split("/")[3]
            sp_volume = self.spapi.volumeList(volumeName = "~" + name)
            self.debug('################ %s' % sp_volume)
        except spapi.ApiError as err:
            raise Exception(err)

        Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "false")

        try:
            # Login to VM and write data to file system
            ssh_client = self.virtual_machine.get_ssh_client(reconnect = True)

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

        snapshot = Snapshot.create(
           self.apiclient,
            volume_id = volume[0].id,
            account=self.account.name,
            domainid=self.account.domainid,
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
                    flag = True
                    self.debug('################ %s' % sp_snapshot)
            if flag == False:
                raise Exception("Could not find snasphot in snapshot_details")
        except spapi.ApiError as err:
               raise Exception(err)

        self.assertIsNotNone(snapshot, "Could not create snapshot")
        self.assertIsInstance(snapshot, Snapshot, "Snapshot is not an instance of Snapshot")

        Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "true")

        template = self.helper.create_template_from_snapshot(
            self.apiclient,
            self.services,
            snapshotid = snapshot.id
            )

        flag = False
        sp_snapshots = self.spapi.snapshotsList()
        for snap in sp_snapshots:
            tags = snap.tags
            for t in tags:
                if tags[t] == template.id:
                    flag = True
                    break
            else:
                continue
            break

        if flag is False:
            raise Exception("Template does not exists in Storpool")
        virtual_machine = VirtualMachine.create(self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=template.id,
            accountid=self.account.name,
            domainid=self.account.domainid,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
            )

        try:
            ssh_client = virtual_machine.get_ssh_client(reconnect=True)

            cmds = [
                "cat %s/%s" % (self.test_dir, self.random_data)
            ]

            for c in cmds:
                self.debug(c)
                result = ssh_client.execute(c)
                self.debug(result)

        except Exception:
            self.fail("SSH failed for Virtual machine: %s" %
                      virtual_machine.ipaddress)

        self.assertEqual(
            self.random_data_0,
            result[0],
            "Check the random data is equal with the ramdom file!"
        )
        self.assertIsNotNone(template, "Template is None")
        self.assertIsInstance(template, Template, "Template is instance of template")
        self._cleanup.append(template)

