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
                                  deleteTemplate)
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
                             Snapshot
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
    ARGS = ""
    vm_snapshot_glId = None
    random_data_vm_snapshot_glid = None
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
                os.killpg(cls.mvn_proc_grp, signal.SIGTERM)
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

        serviceOffering = cls.testdata[TestData.serviceOffering]
        storage_pool = list_storage_pools(
            cls.apiclient,
            name = primarystorage.get("name")
            )
        cls.primary_storage = storage_pool[0]

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

        cls.disk_offering = disk_offering[0]

        account = list_accounts(
            cls.apiclient,
            name="admin"
            )
        cls.account = account[0]


        cls.virtual_machine = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4()},
            zoneid=cls.zone.id,
            templateid=cls.template.id,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            rootdisksize=10
        )
        cls._cleanup.append(cls.virtual_machine)

        cls.virtual_machine2 = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4()},
            zoneid=cls.zone.id,
            templateid=cls.template.id,
            serviceofferingid=cls.service_offering.id,
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

        #check that ROOT disk is created with uuid
        root_volume = list_volumes(
                        cls.apiclient,
                        virtualmachineid = cls.virtual_machine3.id,
                        type = "ROOT"
                        )
        try:
            spvolume = cls.spapi.volumeList(volumeName=root_volume[0].id)

        except spapi.ApiError as err:
           cfg.logger.info("Root volume is not created with UUID")
           raise Exception(err) 

        cls.volume = Volume.create(
            cls.apiclient,
            cls.testdata[TestData.volume_1],
            account=cls.account.name,
            domainid=cls.domain.id,
            zoneid=cls.zone.id,
            diskofferingid=cls.disk_offering.id
        )
        cls._cleanup.append(cls.volume)


        cls.random_data_vm_snapshot1 = random_gen(size=100)
        cls.test_dir = "/tmp"
        cls.random_data = "random.data"

        volume_attached = cls.virtual_machine.attach_volume(
            cls.apiclient,
            cls.volume
            )

        cls.helper.write_on_disks(cls.random_data_vm_snapshot1, cls.virtual_machine, cls.test_dir, cls.random_data)
        
        MemorySnapshot = False
        cls.vm_snapshot1 = cls.helper.create_vm_snapshot(MemorySnapshot, cls.virtual_machine)
        cls.helper.delete_random_data_after_vmsnpashot(cls.vm_snapshot1, cls.virtual_machine, cls.test_dir, cls.random_data)

        cls.random_data_vm_snapshot2 = random_gen(size=100)
        cls.helper.write_on_disks(cls.random_data_vm_snapshot2, cls.virtual_machine, cls.test_dir, cls.random_data)
        
        cls.vm_snapshot2 = cls.helper.create_vm_snapshot(MemorySnapshot, cls.virtual_machine)
        cls.helper.delete_random_data_after_vmsnpashot(cls.vm_snapshot2, cls.virtual_machine, cls.test_dir, cls.random_data)

        #vm snapshot to be deleted without revert
        cls.random_data_vm_snapshot3 = random_gen(size=100)
        cls.helper.write_on_disks(cls.random_data_vm_snapshot3, cls.virtual_machine, cls.test_dir, cls.random_data)

        cls.vm_snapshot_for_delete = cls.helper.create_vm_snapshot(MemorySnapshot, cls.virtual_machine)
        cls.helper.delete_random_data_after_vmsnpashot(cls.vm_snapshot_for_delete, cls.virtual_machine, cls.test_dir, cls.random_data)

        cls.snapshot_on_secondary = cls.helper.create_snapshot(False, cls.virtual_machine2)
        cls._cleanup.append(cls.snapshot_on_secondary)

        cls.template_on_secondary = cls.helper.create_template_from_snapshot(cls.services, snapshotid = cls.snapshot_on_secondary.id)
        cls._cleanup.append(cls.template_on_secondary)

        cls.snapshot_bypassed = cls.helper.create_snapshot(True, cls.virtual_machine2)
        cls._cleanup.append(cls.snapshot_bypassed)

        cls.template_bypased = cls.helper.create_template_from_snapshot(cls.services, snapshotid = cls.snapshot_bypassed.id)
        cls._cleanup.append(cls.template_bypased)

        #change to latest commit with globalId implementation
        cls.helper.switch_to_globalid_commit( cls.ARGS.globalid, cls.ARGS)
        cfg.logger.info("The setup is done, proceeding with the tests")

    @classmethod
    def tearDownClass(cls):
        cls.cleanUpCloudStack()

    @classmethod
    def cleanUpCloudStack(cls):
        cfg.logger.info("Cleaning up after the whole test run")
        try:
            # Cleanup resources used
            cleanup_resources(cls.apiclient, cls._cleanup)
        except Exception as e:
            cfg.logger.info("cleanup_resources failed: %s", e)
            os.killpg(cls.mvn_proc_grp, signal.SIGTERM)

            time.sleep(30)

            raise Exception("Warning: Exception during cleanup : %s" % e)

        cfg.logger.info("Stopping CloudStack")
        os.killpg(cls.mvn_proc_grp, signal.SIGTERM)

        time.sleep(30)

        return


    def test_01_create_vm_snapshots_with_globalId(self):
        '''Create vmsnapshot from virtual machine created with uuid'''
        global vm_snapshot_glId
        global random_data_vm_snapshot_glid
        random_data_vm_snapshot_glid = random_gen(size=100)
        self.helper.write_on_disks(random_data_vm_snapshot_glid, self.virtual_machine, self.test_dir, self.random_data)
        
        MemorySnapshot = False
        vm_snapshot_glId = self.helper.create_vm_snapshot(MemorySnapshot, self.virtual_machine)
        self.helper.delete_random_data_after_vmsnpashot(vm_snapshot_glId, self.virtual_machine, self.test_dir, self.random_data)

    def test_02_delete_vm_snapshot_between_reverts(self):
        '''Delete VM snapshot after revert of one vm snapshot '''
        self.virtual_machine.stop(self.apiclient, forced=True)

        try:
            cfg.logger.info("revert vm snapshot created with UUID")

            VmSnapshot.revertToSnapshot(
                self.apiclient,
                self.vm_snapshot1.id
                )
        except Exception as e:
            cfg.logger.info(e)

        self.virtual_machine.start(self.apiclient)
        time.sleep(20)

        try:
            ssh_client = self.virtual_machine.get_ssh_client(reconnect=True)

            cmds = [
                "cat %s/%s" % (self.test_dir, self.random_data)
            ]

            for c in cmds:
                result = ssh_client.execute(c)

        except Exception:
            self.fail("SSH failed for Virtual machine: %s" %
                      self.virtual_machine.ipaddress)

        self.assertEqual(
            self.random_data_vm_snapshot1,
            result[0],
            "Check the random data is equal with the ramdom file!"
        )
        cfg.logger.info("Data before taking a snapshot %s \n\
        Data after revert of snapshot %s" % (self.random_data_vm_snapshot1 , result[0]))

        vm_snapshot_glid = VmSnapshot.create(
            self.apiclient,
            self.virtual_machine.id,
            False,
            "TestSnapshot",
            "Display Text"
        )  

        deleted_vm = VmSnapshot.deleteVMSnapshot(self.apiclient, vmsnapshotid = vm_snapshot_glid.id)
        self.assertTrue(deleted_vm, "The virtual machine snapshot was not deleted")
        deleted_vm2 = VmSnapshot.deleteVMSnapshot(self.apiclient, vmsnapshotid = self.vm_snapshot_for_delete.id)    
        self.assertTrue(deleted_vm2, "VM snapshot was not deleted")
 

    def test_03_revert_vm_snapshot(self):
        ''' Revert few vm snapshots'''

        # revert vm snapshot created with globalid
        self.virtual_machine.stop(self.apiclient, forced=True)
        global vm_snapshot_glId
        global random_data_vm_snapshot_glid

        try:
            cfg.logger.info("revert vm snapshot created with globalid")
            VmSnapshot.revertToSnapshot(
                self.apiclient,
                vm_snapshot_glId.id
                )
        except Exception as e:
            cfg.logger.info(e)

        self.virtual_machine.start(self.apiclient)
        time.sleep(20)

        try:
            ssh_client = self.virtual_machine.get_ssh_client(reconnect=True)

            cmds = [
                "cat %s/%s" % (self.test_dir, self.random_data)
            ]

            for c in cmds:
                result = ssh_client.execute(c)

        except Exception:
            self.fail("SSH failed for Virtual machine: %s" %
                      self.virtual_machine.ipaddress)

        self.assertEqual(
            random_data_vm_snapshot_glid,
            result[0],
            "Check the random data is equal with the ramdom file!"
        )
        cfg.logger.info("Data before taking a snapshot %s \n\
        Data after revert of snapshot %s" % (random_data_vm_snapshot_glid , result[0]))
        # revert second snapshot
        self.virtual_machine.stop(self.apiclient, forced=True)

        try:
            cfg.logger.info("revert vm snapshot created with UUID")

            VmSnapshot.revertToSnapshot(
                self.apiclient,
                self.vm_snapshot2.id
                )
        except Exception as e:
            cfg.logger.info(e)

        self.virtual_machine.start(self.apiclient)
        time.sleep(20)

        try:
            ssh_client = self.virtual_machine.get_ssh_client(reconnect=True)

            cmds = [
                "cat %s/%s" % (self.test_dir, self.random_data)
            ]

            for c in cmds:
                result = ssh_client.execute(c)

        except Exception:
            self.fail("SSH failed for Virtual machine: %s" %
                      self.virtual_machine.ipaddress)

        self.assertEqual(
            self.random_data_vm_snapshot2,
            result[0],
            "Check the random data is equal with the ramdom file!"
        )
        cfg.logger.info("Data before taking a snapshot %s \n\
        Data after revert of snapshot %s" % (self.random_data_vm_snapshot2, result[0]))



    def test_04_create_and_delete_template_from_snapshot_bypassed(self):
        ''' Create template from snapshot which is bypassed
            (snapshot - created with uuid
            template created with globalid
            )
        '''
        onStorpool = True
        self.helper.bypass_secondary(onStorpool)
        template = self.helper.create_template_from_snapshot(self.services, snapshotid = self.snapshot_bypassed.id)

        storpoolGlId = self.helper.create_vm_from_template(template, onStorpool)
        cfg.logger.info("Created snapshot for a template in StorPool %s" % storpoolGlId)

        cmd = deleteTemplate.deleteTemplateCmd()
        cmd.id = template.id
        cmd.zoneid = self.zone.id
        deleted = self.apiclient.deleteTemplate(cmd)

        self.assertTrue(deleted, "Template was not deleted from CS")
        isTemplateDeleted = self.helper.check_snapshot_is_deleted_from_storpool(storpoolGlId)
        self.assertTrue(isTemplateDeleted, "Template was not deleted from StorPool")

    def test_05_revert_delete_volume_snapshot(self):
        '''Revert volume snapshot created with uuid'''
        # create snapshot with globalid bypassed
        snapshot_bypassed2 = self.helper.create_snapshot(True, self.virtual_machine2)
        #create snapshot with globalid on secondary
        snapshot_on_secondary2 = self.helper.create_snapshot(False, self.virtual_machine2)

        self.virtual_machine2.stop(self.apiclient, forced=True)

        reverted_snapshot = Volume.revertToSnapshot(self.apiclient, volumeSnapshotId = snapshot_bypassed2.id)

        self.virtual_machine2.start(self.apiclient)

        try:
            ssh_client = self.virtual_machine2.get_ssh_client(reconnect=True)
        except Exception:
            self.fail("SSH failed for Virtual machine: %s" %
                      self.virtual_machine2.ipaddress)

        self.virtual_machine2.stop(self.apiclient, forced=True)

        reverted_snapshot1 = Volume.revertToSnapshot(self.apiclient, volumeSnapshotId = snapshot_on_secondary2.id)

        self.virtual_machine2.start(self.apiclient)

        try:
            ssh_client = self.virtual_machine2.get_ssh_client(reconnect=True)
        except Exception:
            self.fail("SSH failed for Virtual machine: %s" %
                      self.virtual_machine2.ipaddress)

        self.virtual_machine2.stop(self.apiclient, forced=True)

        reverted_snapshot2 = Volume.revertToSnapshot(self.apiclient, volumeSnapshotId = self.snapshot_on_secondary.id)

        self.virtual_machine2.start(self.apiclient)

        try:
            ssh_client = self.virtual_machine2.get_ssh_client(reconnect=True)
        except Exception:
            self.fail("SSH failed for Virtual machine: %s" %
                      self.virtual_machine2.ipaddress)

        self.virtual_machine2.stop(self.apiclient, forced=True)

        reverted_snapshot2 = Volume.revertToSnapshot(self.apiclient, volumeSnapshotId = self.snapshot_bypassed.id)

        self.virtual_machine2.start(self.apiclient)

        try:
            ssh_client = self.virtual_machine2.get_ssh_client(reconnect=True)
        except Exception:
            self.fail("SSH failed for Virtual machine: %s" %
                      self.virtual_machine2.ipaddress)

        snapshot_bypassed2.delete(self.apiclient)
        snapshot_on_secondary2.delete(self.apiclient)

    def test_06_create_vm_with_bypassed_template(self):
        '''Create Virtual machine with template on StorPool, created with uuid
            Bypass option set to true
        '''
        self.helper.bypass_secondary(True)
        self.helper.create_vm_from_template(self.template_bypased, True)

    def test_07_create_vm_with_template_on_secondary(self):
        '''Create Virtual machine with template on secondary, created with uuid
            Bypass option set to  false
        '''
        self.helper.bypass_secondary(False)
        self.helper.create_vm_from_template(self.template_bypased, False)

    def test_08_create_vm_snpashot(self):
        '''Test Create virtual machine snapshot with attached disk created with globalid'''

        volume = Volume.create(
            self.apiclient,
            {"diskname":"StorPoolDisk-GlId" },
            zoneid=self.zone.id,
            diskofferingid=self.disk_offering.id,
            )
        self._cleanup.append(volume)

        self.virtual_machine3.attach_volume(self.apiclient, volume)
        #attached disk created with globalid
        list = list_volumes(self.apiclient,virtualmachineid = self.virtual_machine3.id, id = volume.id)
        volume = list[0]
        name = volume.path.split("/")[3]
        try:
            spvolume = self.spapi.volumeList(volumeName="~" + name)
        except spapi.ApiError as err:
           cfg.logger.info(err)
           raise Exception(err)

        random_data_vm_snapshot = random_gen(size=100)

        self.helper.write_on_disks(random_data_vm_snapshot, self.virtual_machine3, self.test_dir, self.random_data)
        
        MemorySnapshot = False
        vm_snapshot = self.helper.create_vm_snapshot(MemorySnapshot, self.virtual_machine3)
        self.helper.delete_random_data_after_vmsnpashot(vm_snapshot, self.virtual_machine3, self.test_dir, self.random_data)

        self.virtual_machine3.stop(self.apiclient, forced=True)

        try:
            cfg.logger.info("revert vm snapshot created with globalId")

            VmSnapshot.revertToSnapshot(
                self.apiclient,
                vm_snapshot.id
                )
        except Exception as e:
            cfg.logger.info(e)

        self.virtual_machine3.start(self.apiclient)
        time.sleep(20)

        try:
            ssh_client = self.virtual_machine3.get_ssh_client(reconnect=True)

            cmds = [
                "cat %s/%s" % (self.test_dir, self.random_data)
            ]

            for c in cmds:
                result = ssh_client.execute(c)

        except Exception:
            self.fail("SSH failed for Virtual machine: %s" %
                      self.virtual_machine3.ipaddress)

        self.assertEqual(
            random_data_vm_snapshot,
            result[0],
            "Check the random data is equal with the ramdom file!"
        )
        cfg.logger.info("Data before taking a snapshot %s \n\
        Data after revert of snapshot %s" % (random_data_vm_snapshot, result[0]))
        
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
