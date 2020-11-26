#!/usr/bin/env python2.7

#Test can be run with: UUID=be9eba6afa2699044a07238ffd9963486208aa10 GLOBALID=ece14627cab275098974b7f888cf00fee901dfce python marvin/migrating_from_uuid_to_global_id.py

from __future__ import print_function

import io
import logging
import os
import random
import signal
import subprocess
import sys
import time
import unittest
import argparse
import uuid

from StringIO import StringIO

from marvin.cloudstackAPI import (listOsTypes,
                                  listTemplates,
                                  listHosts,
                                  createTemplate,
                                  createVolume,
                                  getVolumeSnapshotDetails,
                                  resizeVolume,
                                  deleteTemplate,
                                  migrateVirtualMachine,
                                  migrateVolume
                                  )
from marvin.cloudstackTestClient import CSTestClient
from marvin.codes import(
    XEN_SERVER,
    SUCCESS,
    FAILED
)
from marvin.lib.base import (Account,
                             ServiceOffering,
                             VirtualMachine,
                             VmSnapshot,
                             User,
                             Volume,
                             Template,
                             Configurations,
                             Snapshot,
                             StoragePool,
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
                               list_accounts)
from marvin.lib.utils import get_hypervisor_type, random_gen, cleanup_resources
from marvin.marvinInit import MarvinInit
from marvin.marvinLog import MarvinLog

from nose.plugins.attrib import attr
from nose.tools import assert_equal, assert_not_equal

from storpool import spapi
from logs_and_commands import (TeeStream,TestData, HelperUtil, cfg, TeeTextTestRunner)

class TestMigrationFromUuidToGlobalId(unittest.TestCase): 
    @classmethod
    def setUpClass(cls):
        super(TestMigrationFromUuidToGlobalId, cls).setUpClass()
        try:
            cls.setUpCloudStack()
        except Exception:
            cls.cleanUpCloudStack()
            raise

    @classmethod
    def setUpCloudStack(cls):
        super(TestMigrationFromUuidToGlobalId, cls).setUpClass()

        cls._cleanup = []
        cls.helper = HelperUtil(cls)
        cls.helper.build_commit(cls.ARGS.uuid, cls.ARGS)
        cfg.logger.info("Starting CloudStack")
        cls.mvn_proc = subprocess.Popen(
            ['mvn', '-pl', ':cloud-client-ui', 'jetty:run'],
            cwd=cls.ARGS.forked,
            preexec_fn=os.setsid,
            stdout=cfg.misc,
            stderr=subprocess.STDOUT,
            )
        cls.mvn_proc_grp = os.getpgid(cls.mvn_proc.pid)
        cfg.logger.info("Started CloudStack in process group %d", cls.mvn_proc_grp)
        cfg.logger.info("Waiting for a while to give it a chance to start")
        proc = subprocess.Popen(["tail", "-f", cfg.misc_name], shell=False, bufsize=0, stdout=subprocess.PIPE)
        while True:
            line = proc.stdout.readline()
            if not line:
                cfg.logger.info("tail ended, was this expected?")
                cfg.logger.info("Stopping CloudStack")
                os.killpg(cls.mvn_proc_grp, signal.SIGINT)
                break
            if "[INFO] Started Jetty Server" in line:
                cfg.logger.info("got it!")
                break 
        proc.terminate()
        proc.wait()
        time.sleep(15)
        cfg.logger.info("Processing with the setup")


        cls.obj_marvininit = cls.helper.marvin_init(cls.ARGS.cfg)
        cls.testClient = cls.obj_marvininit.getTestClient()
        cls.apiclient = cls.testClient.getApiClient()
        dbclient = cls.testClient.getDbConnection()
        v = dbclient.execute("select * from configuration where name='sp.migration.to.global.ids.completed'")
        cfg.logger.info("Configuration setting for update of db is %s", v)
        if len(v) > 0:
            update = dbclient.execute("update configuration set value='false' where name='sp.migration.to.global.ids.completed'")
            cfg.logger.info("DB configuration table was updated %s", update)

        cls.spapi = spapi.Api.fromConfig(multiCluster=True)
        
        td = TestData()
        cls.testdata = td.testdata


        cls.services = cls.testClient.getParsedTestDataConfig()
        # Get Zone, Domain and templates
        cls.domain = get_domain(cls.apiclient)
        cls.zone = get_zone(cls.apiclient, cls.testClient.getZoneForTests())
        cls.cluster = list_clusters(cls.apiclient)[0]
        cls.hypervisor = get_hypervisor_type(cls.apiclient)

        #The version of CentOS has to be supported
        cls.template = get_template(
            cls.apiclient,
            cls.zone.id,
            account = "system"
        )

        if cls.template == FAILED:
            assert False, "get_template() failed to return template\
                    with description %s" % cls.services["ostype"]

        cls.services["domainid"] = cls.domain.id
        cls.services["small"]["zoneid"] = cls.zone.id
        cls.services["templates"]["ostypeid"] = cls.template.ostypeid
        cls.services["zoneid"] = cls.zone.id
        primarystorage = cls.testdata[TestData.primaryStorage]
        primarystorage2 = cls.testdata[TestData.primaryStorage2]

        serviceOffering = cls.testdata[TestData.serviceOffering]
        serviceOffering2 = cls.testdata[TestData.serviceOfferingssd2]
        storage_pool = list_storage_pools(
            cls.apiclient,
            name = primarystorage.get("name")
            )
        storage_pool2 = list_storage_pools(
            cls.apiclient,
            name = primarystorage2.get("name")
            )
        cls.primary_storage = storage_pool[0]
        cls.primary_storage2 = storage_pool2[0]

        disk_offering = list_disk_offering(
            cls.apiclient,
            name="Small"
            )

        assert disk_offering is not None


        service_offering = list_service_offering(
            cls.apiclient,
            name="ssd"
            )
        if service_offering is not None:
            cls.service_offering = service_offering[0]
        else:
            cls.service_offering = ServiceOffering.create(
                cls.apiclient,
                serviceOffering)
        assert cls.service_offering is not None

        service_offering2 = list_service_offering(
            cls.apiclient,
            name="ssd2"
            )
        if service_offering2 is not None:
            cls.service_offering2 = service_offering2[0]
        else:
            cls.service_offering2 = ServiceOffering.create(
                cls.apiclient,
                serviceOffering2)
        assert cls.service_offering2 is not None

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

        nfs_storage_pool = list_storage_pools(
            cls.apiclient,
            name='primary'
            )

        nfs_service_offering = list_service_offering(
            cls.apiclient,
            name='nfs'
            )

        if nfs_service_offering is None:
            nfs_service_offering = ServiceOffering.create(cls.apiclient, nfs_service_offerings)
        else:
            nfs_service_offering = nfs_service_offering[0]

        cls.nfs_service_offering = nfs_service_offering

        cls.nfs_storage_pool = nfs_storage_pool[0]

        cls.nfs_storage_pool = StoragePool.cancelMaintenance(cls.apiclient, cls.nfs_storage_pool.id)

        cls.disk_offering = disk_offering[0]

        account = list_accounts(
            cls.apiclient,
            name="admin"
            )
        cls.account = account[0]


        cls.virtual_machine = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=cls.template.id,
            serviceofferingid=cls.nfs_service_offering.id,
            hypervisor=cls.hypervisor,
            rootdisksize=10
        )
        cls._cleanup.append(cls.virtual_machine)

        cls.virtual_machine2 = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=cls.template.id,
            serviceofferingid=cls.nfs_service_offering.id,
            hypervisor=cls.hypervisor,
            rootdisksize=10
        )
        cls._cleanup.append(cls.virtual_machine2)

        cls.virtual_machine3 = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=cls.template.id,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            rootdisksize=10
        )
        cls._cleanup.append(cls.virtual_machine3)

        cls.virtual_machine4 = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=cls.template.id,
            serviceofferingid=cls.service_offering2.id,
            hypervisor=cls.hypervisor,
            rootdisksize=10
        )
        cls._cleanup.append(cls.virtual_machine4)

        cls.volume = Volume.create(
            cls.apiclient,
            cls.testdata[TestData.volume_1],
            account=cls.account.name,
            domainid=cls.domain.id,
            zoneid=cls.zone.id,
            diskofferingid=cls.disk_offering.id
        )

        cls._cleanup.append(cls.volume)    

        cls.primary_storage = StoragePool.update(cls.apiclient,
                                              id=cls.primary_storage.id,
                                              tags = ["ssd, nfs, ssd2"])
        cls.primary_storage2 = StoragePool.update(cls.apiclient,
                                              id=cls.primary_storage2.id,
                                              tags = ["ssd, ssd2"])
        #change to latest commit with globalId implementation
        cls.helper.switch_to_globalid_commit(cls.ARGS.globalid, cls.ARGS)
        cfg.logger.info("The setup is done, proceeding with the tests")
        cls.primary_storage = list_storage_pools(
            cls.apiclient,
            name = primarystorage.get("name")
            )[0]
        cls.primary_storage2 = list_storage_pools(
            cls.apiclient,
            name = primarystorage2.get("name")
            )[0]
    @classmethod
    def tearDownClass(cls):
        cls.cleanUpCloudStack()

    @classmethod
    def cleanUpCloudStack(cls):
        cfg.logger.info("Cleaning up after the whole test run")
        try:
            cls.nfs_storage_pool = StoragePool.enableMaintenance(cls.apiclient, cls.nfs_storage_pool.id)
            cls.storage_pool = StoragePool.update(cls.apiclient,
                                              id=cls.primary_storage.id,
                                              tags = ["ssd"])
            cls.storage_pool2 = StoragePool.update(cls.apiclient,
                                              id=cls.primary_storage2.id,
                                              tags = ["ssd2"])
            # Cleanup resources used
            cleanup_resources(cls.apiclient, cls._cleanup)
        except Exception as e:
            cfg.logger.info("cleanup_resources failed: %s", e)
            os.killpg(cls.mvn_proc_grp, signal.SIGTERM)


            raise Exception("Warning: Exception during cleanup : %s" % e)

        cfg.logger.info("Stopping CloudStack")
        os.killpg(cls.mvn_proc_grp, signal.SIGTERM)

        time.sleep(30)

        return

    def test_01_migrate_vm_from_nfs_to_storpool(self):
        ''' Test migrate virtual machine (created before migration to global id) from NFS primary storage to StorPool'''

        self.virtual_machine.stop(self.apiclient, forced=True)
        cmd = migrateVirtualMachine.migrateVirtualMachineCmd()
        cmd.virtualmachineid = self.virtual_machine.id
        cmd.storageid = self.primary_storage.id
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

            self.assertEqual(v.storageid, self.primary_storage.id, "Did not migrate virtual machine from NFS to StorPool")

    def test_02_migrate_volume_from_nfs_to_storpool(self):
        ''' Test migrate volume (created before migration to global id) from NFS primary storage to StorPool'''

        self.virtual_machine2.stop(self.apiclient, forced=True)
        volumes = list_volumes(
            self.apiclient,
            virtualmachineid = self.virtual_machine2.id
            )
        for v in volumes:
            cmd = migrateVolume.migrateVolumeCmd()
            cmd.storageid = self.primary_storage.id
            cmd.volumeid = v.id
            volume =  self.apiclient.migrateVolume(cmd)
            self.assertEqual(volume.storageid, self.primary_storage.id, "Did not migrate volume from NFS to StorPool")

        volumes = list_volumes(
            self.apiclient,
            virtualmachineid = self.virtual_machine2.id
            )
        for v in volumes:
            name = v.path.split("/")[3]
            try:
                sp_volume = self.spapi.volumeList(volumeName="~" + name)
            except spapi.ApiError as err:
                raise Exception(err)
        
        
#migrate vm with uuid to another storage
    def test_03_vm_uuid_to_another_storage(self):
        volumes = list_volumes(
            self.apiclient,
            virtualmachineid = self.virtual_machine3.id
            )
        for v in volumes:
            try:
                #volumes will be updated to their globalId after the start of CS with commit with migration
                name = v.path.split("/")[3]
                sp_volume = self.spapi.volumeList(volumeName="~" + name)
                for t in self.virtual_machine3.tags:
                    self.debug("self.virtual_machine3.tags %" % self.virtual_machine3.tags)
                    self.debug("StorPool volume response %" % sp_volume)
                    if t == sp_volume.templateName:
                        self.debug("***************")
            except spapi.ApiError as err:
                raise Exception(err)

            self.assertEqual(v.storageid, self.primary_storage.id, "Did not migrate virtual machine from NFS to StorPool vol storageId=%s primary storage id=%s" % (v.storageid, self.primary_storage.id))
        self.virtual_machine3.stop(self.apiclient, forced=True)
        cmd = migrateVirtualMachine.migrateVirtualMachineCmd()
        cmd.virtualmachineid = self.virtual_machine3.id
        cmd.storageid = self.primary_storage.id
        migrated_vm = self.apiclient.migrateVirtualMachine(cmd)
        volumes = list_volumes(
            self.apiclient,
            virtualmachineid = migrated_vm.id
            )
        for v in volumes:
            name = None
            if v.path.startswith("/dev/storpool-byid/"):
                name = v.path.split("/")[3]
                name = "~" + name
            else:
                name = v.id
            try:
                sp_volume = self.spapi.volumeList(volumeName= name)
            except spapi.ApiError as err:
                raise Exception(err)

            self.assertEqual(v.storageid, self.primary_storage.id, "Did not migrate virtual machine from NFS to StorPool")

#migrate vm with globalid to another storage
    def test_04_vm_glid_to_another_storage(self):
        vm = VirtualMachine.create(self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=self.template.id,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
            )
        volumes = list_volumes(
            self.apiclient,
            virtualmachineid = vm.id
            )
        for v in volumes:
            name = v.path.split("/")[3]
            try:
                sp_volume = self.spapi.volumeList(volumeName="~" + name)
            except spapi.ApiError as err:
                raise Exception(err)
        vm.stop(self.apiclient, forced=True)

        migrated_vm = self.migrate_vm(vm, self.primary_storage2)
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

            self.assertEqual(v.storageid, self.primary_storage.id, "Did not migrate virtual machine from NFS to StorPool")
        self._cleanup.append(vm)
        
#migrate volume with uuid to another storage
  #  def test_05_migrate_volume_uuid_to_another_storage(self):

#migrate volume with global id to another storage

#migrate vm with uuid to another storpool storage

#migrate vm with global id to another storpool storage

#Test migrate virtual machine from NFS primary storage to StorPool

#Test migrate virtual machine with uuid to nfs

#test migrate virtual machine with global id to nfs

#migrate volume from nfs to Storpool

    @classmethod
    def migrate_vm(self, vm, primary_storage):
        cmd = migrateVirtualMachine.migrateVirtualMachineCmd()
        cmd.virtualmachineid = vm.id
        cmd.storageid = self.primary_storage.id
        return self.apiclient.migrateVirtualMachine(cmd)
        
def main():
    original = (sys.stdout, sys.stderr)
    try:
        helper = HelperUtil()
        parser = argparse.ArgumentParser()
        TestMigrationFromUuidToGlobalId.ARGS = helper.argument_parser(parser)
        cfg.logger.info("Arguments  %s", TestMigrationFromUuidToGlobalId.ARGS)          

        cfg.logger.info("Redirecting sys.stdout and sys.stderr to %s", cfg.misc_name)
        sys.stdout = cfg.misc
        sys.stderr = cfg.misc

        unittest.main(testRunner=TeeTextTestRunner)
    except BaseException as exc:
        sys.stdout, sys.stderr = original
        raise
    finally:
        sys.stdout, sys.stderr = original


if __name__ == "__main__":
    main()
