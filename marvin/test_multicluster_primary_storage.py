import os
import random
import signal
import subprocess
import time
import unittest
import argparse
import uuid

from marvin.cloudstackAPI import (listOsTypes,
                                  listTemplates,
                                  listHosts,
                                  createTemplate,
                                  createVolume,
                                  getVolumeSnapshotDetails,
                                  resizeVolume,
                                  deleteTemplate)
from marvin.cloudstackTestClient import CSTestClient
from marvin.codes import(
    XEN_SERVER,
    SUCCESS,
    FAILED
)
from marvin.cloudstackTestCase import cloudstackTestCase

from marvin.lib.base import (Account,
                             ServiceOffering,
                             VirtualMachine,
                             VmSnapshot,
                             User,
                             Tag,
                             Volume,
                             Template,
                             Configurations,
                             Snapshot,
                             StoragePool,
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
                               list_accounts,
                               list_zones)
from marvin.lib.utils import get_hypervisor_type, random_gen, cleanup_resources

from nose.plugins.attrib import attr

from storpool import spapi
from storpool import sptypes
import json
import pprint
from sp_util import (TestData, StorPoolHelper)

class TestNewPrimaryStorage(cloudstackTestCase): 
    @classmethod
    def setUpClass(cls):
        super(TestNewPrimaryStorage, cls).setUpClass()
        try:
            cls.setUpCloudStack()
        except Exception:
            cls.cleanUpCloudStack()
            raise

    @classmethod
    def setUpCloudStack(cls):
        cls.testClient = super(TestNewPrimaryStorage, cls).getClsTestClient()

        cls.cleanup = []

        cls.apiclient = cls.testClient.getApiClient()
        cls.unsupportedHypervisor = False
        cls.hypervisor = cls.testClient.getHypervisorInfo()
        if cls.hypervisor.lower() in ("hyperv", "lxc"):
            cls.unsupportedHypervisor = True
            return

        td = TestData()
        cls.testdata = td.testdata
        cls.helper = StorPoolHelper()

        cls.services = cls.testClient.getParsedTestDataConfig()
        # Get Zone, Domain and templates
        cls.domain = get_domain(cls.apiclient)
        cls.zone = None


        zones = list_zones(cls.apiclient)

        for z in zones:
            if z.internaldns1 == cls.getClsConfig().mgtSvr[0].mgtSvrIp:
                cls.zone = z

        cls.debug("################## zone %s" % cls.zone)
        cls.template_name = cls.testdata[TestData.primaryStorage3].get("name")
        cls.debug("################## template_name %s" % cls.template_name)

        cls.storage_pool_id = "spStoragePoolId"
        cls.sp_primary_storage, cls.spapiRemote, cls.spapi = cls.helper.create_sp_template_and_storage_pool(cls.apiclient, cls.template_name, cls.testdata[TestData.primaryStorage3], cls.zone.id)

        disk_offerings = list_disk_offering(
            cls.apiclient,
            name="Small"
            )

        cls.disk_offerings = disk_offerings[0]

        diskOffering = {
                "name": cls.template_name,
                "displaytext": "test new primary storage disk offerigns",
                "disksize": 128,
                "tags": cls.template_name,
                "storagetype": "shared"
            }

        cls.sp_disk_offering = DiskOffering.create(cls.apiclient, diskOffering)
        cls.cleanup.append(cls.sp_disk_offering)

        sp_offerings = {
            "name": cls.template_name,
            "displaytext": cls.template_name,
            "cpunumber": 1,
            "cpuspeed": 500,
            "memory": 512,
            "storagetype": "shared",
            "tags" : cls.template_name
            }
        cls.serviceOfferings = ServiceOffering.create(
            cls.apiclient,
            sp_offerings
            )

        cls.template = get_template(
            cls.apiclient,
            cls.zone.id,
            account = "system"
        )
        
    @classmethod
    def tearDownClass(cls):
        cls.cleanUpCloudStack()

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
    def cleanUpCloudStack(cls):
        spapiRemote = spapi.Api.fromConfig()
        remote_cluster = cls.helper.get_remote_storpool_cluster()
        try:

            # Cleanup resources used
            cleanup_resources(cls.apiclient, cls.cleanup)
            
            StoragePool.delete(cls.sp_primary_storage, cls.apiclient)
            ServiceOffering.delete(cls.serviceOfferings, cls.apiclient)
            spapiRemote.volumeTemplateDelete(templateName=cls.template_name, clusterName=remote_cluster)
            spapiRemote.volumeTemplateDelete(templateName=cls.template_name,)
        except Exception as e:
            raise Exception("Warning: Exception during cleanup : %s" % e)

        return

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_01_create_vm_on_new_primary_storage(self):
        ''' Test create Virtual machine on new StorPool's primary storage
        '''
        virtual_machine = VirtualMachine.create(
            self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=self.template.id,
            serviceofferingid=self.serviceOfferings.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
        )

        volume = list_volumes(
            self.apiclient,
            virtualmachineid = virtual_machine.id,
            type = "ROOT"
            )

        volume = volume[0]

        name = volume.path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
            if spvolume[0].templateName != self.template_name:
                raise Exception("Storpool volume's template %s  is not with the same template %s"  % (spvolume[0].templateName ,self.template_name))
        except spapi.ApiError as err:
           raise Exception(err)
        virtual_machine.delete(self.apiclient, expunge=True)


    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_02_create_volume_on_new_primary_storage(self):
        ''' Test create Virtual machine on new StorPool's primary storage
        '''

        volume = Volume.create(
            self.apiclient,
            {"diskname":"StorPoolDisk-1" },
            zoneid=self.zone.id,
            diskofferingid=self.sp_disk_offering.id,
        )

        virtual_machine = VirtualMachine.create(
            self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=self.template.id,
            serviceofferingid=self.serviceOfferings.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
        )
        virtual_machine.attach_volume(
            self.apiclient,
            volume
            )

        volumes = list_volumes(
            self.apiclient,
            virtualmachineid = virtual_machine.id,
            )


        for vol in volumes:
            name = vol.path.split("/")[3]
            try:
                spvolume = self.spapi.volumeList(volumeName="~" + name)
                if spvolume[0].templateName != self.template_name:
                    raise Exception("Storpool volume's template %s  is not with the same template %s"  % (spvolume[0].templateName ,self.template_name))
            except spapi.ApiError as err:
               raise Exception(err)

        virtual_machine.stop(self.apiclient, forced= True)
        virtual_machine.detach_volume(self.apiclient, volume)
        Volume.delete(volume, self.apiclient)
        virtual_machine.delete(self.apiclient, expunge=True)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_03_try_delete_primary_with_snapshots(self):
        virtual_machine = VirtualMachine.create(
            self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=self.template.id,
            serviceofferingid=self.serviceOfferings.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
        )

        volume = list_volumes(
            self.apiclient,
            virtualmachineid = virtual_machine.id,
            type = "ROOT"
            )

        volume = volume[0]

        name = volume.path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
            if spvolume[0].templateName != self.template_name:
                raise Exception("Storpool volume's template %s  is not with the same template %s"  % (spvolume[0].templateName ,self.template_name))
        except spapi.ApiError as err:
           raise Exception(err)

        snapshot = Snapshot.create(self.apiclient, volume_id = volume.id,)
        id = self.helper.get_snapshot_template_id(self.apiclient, snapshot, self.storage_pool_id)
        if id is None:
            raise Exception("There isn't primary storgae id")
        virtual_machine.delete(self.apiclient, expunge= True)
        pool = list_storage_pools(self.apiclient, id = id)
        if pool[0].name == self.template_name:
            try:
                StoragePool.delete(self.sp_primary_storage, self.apiclient)
            except Exception as err:
                StoragePool.cancelMaintenance(self.apiclient, id = self.sp_primary_storage.id)
                self.debug("Storage pool could not be delete due to %s" % err)
        else:
            self.cleanup.append(snapshot)
            raise Exception("Snapshot is not on the same pool")
        Snapshot.delete(snapshot, self.apiclient)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_04_try_delete_primary_with_template(self):
        virtual_machine = VirtualMachine.create(
            self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=self.template.id,
            serviceofferingid=self.serviceOfferings.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
        )

        volume = list_volumes(
            self.apiclient,
            virtualmachineid = virtual_machine.id,
            type = "ROOT",
            listall = True
            )

        volume = volume[0]

        name = volume.path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
            if spvolume[0].templateName != self.template_name:
                raise Exception("Storpool volume's template %s  is not with the same template %s"  % (spvolume[0].templateName ,self.template_name))
        except spapi.ApiError as err:
           raise Exception(err)

        backup_config = list_configurations(
            self.apiclient,
            name = "sp.bypass.secondary.storage")
        if (backup_config[0].value == "false"):
            backup_config = Configurations.update(self.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "true")

        snapshot = Snapshot.create(self.apiclient, volume_id = volume.id,)
        self.debug("###################### %s" % snapshot)
        id = self.helper.get_snapshot_template_id(self.apiclient, snapshot, self.storage_pool_id)
        if id is None:
            raise Exception("There isn't primary storgae id")
        virtual_machine.delete(self.apiclient, expunge=True)
        pool = list_storage_pools(self.apiclient, id = id)

        services = {"displaytext": "Template-1", "name": "Template-1-name", "ostypeid": self.template.ostypeid, "ispublic": "true"}
        template = Template.create_from_snapshot(self.apiclient, snapshot = snapshot, services= services)
        Snapshot.delete(snapshot, self.apiclient)

        try:
            StoragePool.delete(self.sp_primary_storage, self.apiclient)
        except Exception as err:
            StoragePool.cancelMaintenance(self.apiclient, id = self.sp_primary_storage.id)
            self.debug("Storge pool could not be delete due to %s" % err)

        Template.delete(template, self.apiclient)

