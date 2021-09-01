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
                             Tag,
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

class MigrationUuidToGlobalIdTags(unittest.TestCase): 
    ARGS = ""
    @classmethod
    def setUpClass(cls):
        super(MigrationUuidToGlobalIdTags, cls).setUpClass()
        try:
            cls.setUpCloudStack()
        except Exception:
            cls.cleanUpCloudStack()
            raise

    @classmethod
    def setUpCloudStack(cls):
        super(MigrationUuidToGlobalIdTags, cls).setUpClass()
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
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=cls.template.id,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            rootdisksize=10
        )
        cls._cleanup.append(cls.virtual_machine)   
        cls.virtual_machine2 = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
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

        cls.virtual_machine4 = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=cls.template.id,
            serviceofferingid=cls.service_offering.id,
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

        cls.volume2 = Volume.create(
            cls.apiclient,
            cls.testdata[TestData.volume_2],
            account=cls.account.name,
            domainid=cls.domain.id,
            zoneid=cls.zone.id,
            diskofferingid=cls.disk_offering.id
        )
        cls._cleanup.append(cls.volume2)

        cls.volume3 = Volume.create(
            cls.apiclient,
            cls.testdata[TestData.volume_3],
            account=cls.account.name,
            domainid=cls.domain.id,
            zoneid=cls.zone.id,
            diskofferingid=cls.disk_offering.id
        )
        cls._cleanup.append(cls.volume3)

        cls.volume4 = Volume.create(
            cls.apiclient,
            cls.testdata[TestData.volume_4],
            account=cls.account.name,
            domainid=cls.domain.id,
            zoneid=cls.zone.id,
            diskofferingid=cls.disk_offering.id
        )
        cls._cleanup.append(cls.volume4)

        cls.random_data_vm_snapshot1 = random_gen(size=100)
        cls.test_dir = "/tmp"
        cls.random_data = "random.data"

        volume_attached = cls.virtual_machine3.attach_volume(
            cls.apiclient,
            cls.volume3
            )

        cls.helper.write_on_disks(cls.random_data_vm_snapshot1, cls.virtual_machine3, cls.test_dir, cls.random_data)
        
        MemorySnapshot = False
        cls.vm_snapshot1 = cls.helper.create_vm_snapshot(MemorySnapshot, cls.virtual_machine3)
        cls.helper.delete_random_data_after_vmsnpashot(cls.vm_snapshot1, cls.virtual_machine3, cls.test_dir, cls.random_data)

        #for test 01
        cls.virtual_machine.attach_volume(cls.apiclient, cls.volume)

        #for test 03 the volume has to be created with uuid before to switch to commit with globalid implementation
        cls.virtual_machine.attach_volume(cls.apiclient, cls.volume4)
        cls.virtual_machine.stop(cls.apiclient, forced = True)
        cls.virtual_machine.detach_volume(cls.apiclient, cls.volume4)
        cls.virtual_machine.start(cls.apiclient)


        #change to latest commit with globalId implementation
        cls.helper.switch_to_globalid_commit(cls.ARGS.globalid, cls.ARGS)
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


            raise Exception("Warning: Exception during cleanup : %s" % e)

        cfg.logger.info("Stopping CloudStack")
        os.killpg(cls.mvn_proc_grp, signal.SIGTERM)

        time.sleep(30)

        return


#set vc_policy tag to vm with uuid with attached disk with uuid
    def test_01_vc_policy_with_attached_disk_uuid(self):
        list = list_volumes(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            id = self.volume.id
            )
        self.assertIsNotNone(list, "Volume=%s was not attached to vm=%s" %(self.volume.id, self.virtual_machine.id))

        tag = Tag.create(
            self.apiclient,
            resourceIds=self.virtual_machine.id,
            resourceType='UserVm',
            tags={'vc-policy': 'testing_vc-policy'}
        )
        vm = list_virtual_machines(self.apiclient,id = self.virtual_machine.id)
        vm_tags = vm[0].tags
        volumes = list_volumes(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            )
        for v in volumes:
            self.helper.vc_policy_tags_global_id(v, vm_tags, False)


#set vc_policy tag to vm with uuid with attached disk with globalid
    def test_02_vc_policy_with_attached_disk_globalid(self):
        self.virtual_machine2.attach_volume(self.apiclient, self.volume2)
        list = list_volumes(
            self.apiclient,
            virtualmachineid = self.virtual_machine2.id,
            id = self.volume2.id
            )
        self.assertIsNotNone(list, "Volume=%s was not attached to vm=%s" %(self.volume.id, self.virtual_machine.id))

        tag = Tag.create(
            self.apiclient,
            resourceIds=self.virtual_machine2.id,
            resourceType='UserVm',
            tags={'vc-policy': 'testing_vc-policy'}
        )
        vm = list_virtual_machines(self.apiclient,id = self.virtual_machine2.id)
        vm_tags = vm[0].tags
        volumes = list_volumes(
            self.apiclient,
            virtualmachineid = self.virtual_machine2.id,
            )
        for v in volumes:
            if v.type == "ROOT":
                self.helper.vc_policy_tags_global_id(v, vm_tags, False)
            else:
                self.helper.vc_policy_tags_global_id(v, vm_tags, False)


#set vc policy tag to volume with uuid which will be attached to vm with uuid
    def test_03_attach_volume_to_vm_with_vc_policy_uuid(self):
        self.virtual_machine.attach_volume(self.apiclient, self.volume4)

        vm = list_virtual_machines(self.apiclient,id = self.virtual_machine.id)
        vm_tags = vm[0].tags
        volumes = list_volumes(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            )
        self.assertTrue(len(volumes) == 3, "Volume length should be == 3")
        for v in volumes:
            self.helper.vc_policy_tags_global_id(v, vm_tags, False)
        

#set vc policy tag to volume with global which will be attached to vm with uuid
    def test_04_vc_policy_attach_vol_global_id_vm_uuid(self):

        tag = Tag.create(
            self.apiclient,
            resourceIds=self.virtual_machine4.id,
            resourceType='UserVm',
            tags={'vc-policy': 'testing_vc-policy'}
        )

        vm = list_virtual_machines(self.apiclient,id = self.virtual_machine4.id)
        vm_tags = vm[0].tags
        volumes = list_volumes(
            self.apiclient,
            virtualmachineid = self.virtual_machine4.id,
            )
        self.assertTrue(len(volumes) == 1, "Volume length should be == 1")
        for v in volumes:
            self.helper.vc_policy_tags_global_id(v, vm_tags, False)

        volume = Volume.create(self.apiclient,
            {"diskname":"StorPoolDisk-GlId-%d" % random.randint(0, 100) },
            zoneid=self.zone.id,
            diskofferingid=self.disk_offering.id,
            )

        self.virtual_machine4.attach_volume(self.apiclient, volume)

        vm = list_virtual_machines(self.apiclient,id = self.virtual_machine4.id)
        vm_tags = vm[0].tags
        volumes = list_volumes(
            self.apiclient,
            virtualmachineid = self.virtual_machine4.id,
            id = volume.id
            )
        self.assertTrue(len(volumes) == 1, "Volume length should be == 1")
        self.helper.vc_policy_tags_global_id(volumes[0], vm_tags, False)
        self._cleanup.append(volume)

#set vc policy tag to volume with global which will be attached to vm with globalid
    def test_05_vc_policy_to_volume_and_vm_with_glid(self):
        vm = VirtualMachine.create(
            self.apiclient,
           {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=self.template.id,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
            )

        tag = Tag.create(
            self.apiclient,
            resourceIds=vm.id,
            resourceType='UserVm',
            tags={'vc-policy': 'testing_vc-policy'}
        )

        vm_list = list_virtual_machines(self.apiclient,id = vm.id)
        vm_tags = vm_list[0].tags
        self._cleanup.append(vm)

def main():
    original = (sys.stdout, sys.stderr)
    try:
        helper = HelperUtil()
        parser = argparse.ArgumentParser()
        MigrationUuidToGlobalIdTags.ARGS = helper.argument_parser(parser)
        cfg.logger.info("Arguments  %s", MigrationUuidToGlobalIdTags.ARGS)         

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
