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
import json
import pprint

from StringIO import StringIO

from marvin.cloudstackAPI import (listOsTypes,
                                  listTemplates,
                                  listHosts,
                                  createTemplate,
                                  createVolume,
                                  getVolumeSnapshotDetails,
                                  resizeVolume,
                                  deleteTemplate,
                                  deleteStoragePool,
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
                             Host,
                             Tag,
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
from marvin.marvinInit import MarvinInit
from marvin.marvinLog import MarvinLog

from nose.plugins.attrib import attr
from nose.tools import assert_equal, assert_not_equal

from storpool import spapi
from storpool import sptypes
from logs_and_commands import (TeeStream, TestData, HelperUtil, cfg, TeeTextTestRunner)
from marvin.cloudstackTestCase import cloudstackTestCase

class TestMigrationFromUuidToGlobalIdVolumes(cloudstackTestCase): 
    UUID = ""
    GLOBALID = ""
    ARGS= ""
    @classmethod
    def setUpClass(cls):
        super(TestMigrationFromUuidToGlobalIdVolumes, cls).setUpClass()
        try:
            cls.setUpCloudStack()
        except Exception:
            cls.cleanUpCloudStack()
            raise

    @classmethod
    def setUpCloudStack(cls):
        super(TestMigrationFromUuidToGlobalIdVolumes, cls).setUpClass()
        cls._cleanup = []
        cls.helper = HelperUtil(cls)
        with open(cls.ARGS.cfg) as json_text:
            cfg.logger.info(cls.ARGS.cfg)
            cfg.logger.info(json_text)
            conf = json.load(json_text)
            cfg.logger.info(conf)

            zone = conf['mgtSvr'][0].get('zone')

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
    
        td = TestData()
        cls.testdata = td.testdata
    
    
        cls.services = cls.testClient.getParsedTestDataConfig()
        # Get Zone, Domain and templates
        cls.domain = get_domain(cls.apiclient)
        cls.zone = get_zone(cls.apiclient, zone_name = zone)
        cls.cluster = list_clusters(cls.apiclient)[0]
        cls.hypervisor = get_hypervisor_type(cls.apiclient)
        cls.host = list_hosts(cls.apiclient, zoneid = cls.zone.id)
    
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
        cls.sp_template_1 = "-".join(["test-ssd-b", random_gen()])
        cfg.logger.info(pprint.pformat("############################ %s" % cls.zone))
        storpool_primary_storage = {
            "name" : cls.sp_template_1,
            "zoneid": cls.zone.id,
            "url": "SP_API_HTTP=10.2.87.30:81;SP_AUTH_TOKEN=1234567890;SP_TEMPLATE=%s" % cls.sp_template_1,
            "scope": "zone",
            "capacitybytes": 564325555333,
            "capacityiops": 155466,
            "hypervisor": "kvm",
            "provider": "StorPool",
            "tags": cls.sp_template_1
            }

        cls.storpool_primary_storage = storpool_primary_storage
        host, port, auth = cls.getCfgFromUrl(url = storpool_primary_storage["url"])
        cls.spapi = spapi.Api(host=host, port=port, auth=auth)

        storage_pool = list_storage_pools(
            cls.apiclient,
            name=storpool_primary_storage["name"]
            )

        if storage_pool is None:
            newTemplate = sptypes.VolumeTemplateCreateDesc(name = storpool_primary_storage["name"],placeAll = "ssd", placeTail = "ssd", placeHead = "ssd", replication=1)
            template_on_local = cls.spapi.volumeTemplateCreate(newTemplate)
            storage_pool = StoragePool.create(cls.apiclient, storpool_primary_storage)
        else:
            storage_pool = storage_pool[0]
        cls.primary_storage = storage_pool


        storpool_service_offerings_ssd = {
            "name": cls.sp_template_1,
                "displaytext": "SP_CO_2 (Min IOPS = 10,000; Max IOPS = 15,000)",
                "cpunumber": 1,
                "cpuspeed": 500,
                "memory": 512,
                "storagetype": "shared",
                "customizediops": False,
                "hypervisorsnapshotreserve": 200,
                "tags": cls.sp_template_1
            }

        service_offerings_ssd = list_service_offering(
            cls.apiclient,
            name=storpool_service_offerings_ssd["name"]
            )

        if service_offerings_ssd is None:
            service_offerings_ssd = ServiceOffering.create(cls.apiclient, storpool_service_offerings_ssd)
        else:
            service_offerings_ssd = service_offerings_ssd[0]

        cls.service_offering = service_offerings_ssd
        cls._cleanup.append(cls.service_offering)
        cfg.logger.info(pprint.pformat(cls.service_offering))


        cls.sp_template_2 = "-".join(["test-ssd2-b", random_gen()])

        storpool_primary_storage2 = {
            "name" : cls.sp_template_2,
            "zoneid": cls.zone.id,
            "url": "SP_API_HTTP=10.2.87.30:81;SP_AUTH_TOKEN=1234567890;SP_TEMPLATE=%s" % cls.sp_template_2,
            "scope": "zone",
            "capacitybytes": 564325555333,
            "capacityiops": 1554,
            "hypervisor": "kvm",
            "provider": "StorPool",
            "tags": cls.sp_template_2
            }

        cls.storpool_primary_storage2 = storpool_primary_storage2
        storage_pool = list_storage_pools(
            cls.apiclient,
            name=storpool_primary_storage2["name"]
            )

        if storage_pool is None:
            newTemplate = sptypes.VolumeTemplateCreateDesc(name = storpool_primary_storage2["name"],placeAll = "ssd", placeTail = "ssd", placeHead = "ssd", replication=1)
            template_on_local = cls.spapi.volumeTemplateCreate(newTemplate)
            storage_pool = StoragePool.create(cls.apiclient, storpool_primary_storage2)
        else:
            storage_pool = storage_pool[0]
        cls.primary_storage2 = storage_pool

        storpool_service_offerings_ssd2 = {
            "name": cls.sp_template_2,
                "displaytext": "SP_CO_2",
                "cpunumber": 1,
                "cpuspeed": 500,
                "memory": 512,
                "storagetype": "shared",
                "customizediops": False,
                "tags": cls.sp_template_2
            }

        service_offerings_ssd2 = list_service_offering(
            cls.apiclient,
            name=storpool_service_offerings_ssd2["name"]
            )

        if service_offerings_ssd2 is None:
            service_offerings_ssd2 = ServiceOffering.create(cls.apiclient, storpool_service_offerings_ssd2)
        else:
            service_offerings_ssd2 = service_offerings_ssd2[0]

        cls.service_offering2 = service_offerings_ssd2
        cls._cleanup.append(cls.service_offering2)

        os.killpg(cls.mvn_proc_grp, signal.SIGTERM)

        time.sleep(30)

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

        disk_offering = list_disk_offering(
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
    
    
        assert disk_offering is not None
        assert disk_offering_20 is not None
        assert disk_offering_100 is not None
    
    
        cls.disk_offering = disk_offering[0]
        cls.disk_offering_20 = disk_offering_20[0]
        cls.disk_offering_100 = disk_offering_100[0]   
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

        cls.virtual_machine5 = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=cls.template.id,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            rootdisksize=10
        )
        cls._cleanup.append(cls.virtual_machine5)

        cls.virtual_machine6 = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=cls.template.id,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            rootdisksize=10
        )
        cls._cleanup.append(cls.virtual_machine6)

        cls.volume1 = Volume.create(
            cls.apiclient,
            cls.testdata[TestData.volume_1],
            account=cls.account.name,
            domainid=cls.domain.id,
            zoneid=cls.zone.id,
            diskofferingid=cls.disk_offering.id
        )
        cls._cleanup.append(cls.volume1)

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

        cls.volume5 = Volume.create(
            cls.apiclient,
            cls.testdata[TestData.volume_5],
            account=cls.account.name,
            domainid=cls.domain.id,
            zoneid=cls.zone.id,
            diskofferingid=cls.disk_offering.id
        )

        cls._cleanup.append(cls.volume5)
        cls.volume6 = Volume.create(
            cls.apiclient,
            cls.testdata[TestData.volume_6],
            account=cls.account.name,
            domainid=cls.domain.id,
            zoneid=cls.zone.id,
            diskofferingid=cls.disk_offering.id
        )
        cls._cleanup.append(cls.volume6)

        cls.volume7 = Volume.create(
            cls.apiclient,
            cls.testdata[TestData.volume_7],
            account=cls.account.name,
            domainid=cls.domain.id,
            zoneid=cls.zone.id,
            diskofferingid=cls.disk_offering.id
        )

        cls.volume8 = Volume.create(
            cls.apiclient,
            cls.testdata[TestData.volume_7],
            account=cls.account.name,
            domainid=cls.domain.id,
            zoneid=cls.zone.id,
            diskofferingid=cls.disk_offering.id
        )
        cls.virtual_machine.stop(cls.apiclient, forced=True)

        cls.volume_on_sp_1 = cls.virtual_machine.attach_volume(cls.apiclient, cls.volume1)

        vol = list_volumes(cls.apiclient, id = cls.volume3.id)

        cls.virtual_machine.attach_volume(cls.apiclient, cls.volume3)
        cls.virtual_machine.detach_volume(cls.apiclient, cls.volume3)

        vol = list_volumes(cls.apiclient, id = cls.volume3.id)

        cls.volume_on_sp_3 = vol[0]

        cls.virtual_machine.attach_volume(cls.apiclient, cls.volume2)
        cls.virtual_machine.detach_volume(cls.apiclient, cls.volume2)

        cls.virtual_machine3.attach_volume(cls.apiclient, cls.volume4)
        cls.virtual_machine3.detach_volume(cls.apiclient, cls.volume4)

        cls.virtual_machine.attach_volume(cls.apiclient, cls.volume5)
        cls.virtual_machine.detach_volume(cls.apiclient, cls.volume5)

        cls.virtual_machine.attach_volume(cls.apiclient, cls.volume6)
        cls.virtual_machine.detach_volume(cls.apiclient, cls.volume6)

        cls.virtual_machine.attach_volume(cls.apiclient, cls.volume7)
        cls.virtual_machine.detach_volume(cls.apiclient, cls.volume7)

        cls.virtual_machine.attach_volume(cls.apiclient, cls.volume8)
        cls.virtual_machine.detach_volume(cls.apiclient, cls.volume8)

        cls.virtual_machine.start(cls.apiclient)

        list_root = list_volumes(cls.apiclient, virtualmachineid = cls.virtual_machine5.id, type = "ROOT")

        cls.snapshot_uuid1 = Snapshot.create(cls.apiclient, volume_id = list_root[0].id)
        cls._cleanup.append(cls.snapshot_uuid1)
        cls.snapshot_uuid2 = Snapshot.create(cls.apiclient, volume_id = list_root[0].id)
        cls._cleanup.append(cls.snapshot_uuid2)

        #Snapshot on secondary
        cls.helper.bypass_secondary(False)
        cls.snapshot_uuid_on_secondary = Snapshot.create(cls.apiclient, volume_id = list_root[0].id)
        cls._cleanup.append(cls.snapshot_uuid_on_secondary)
        cls.snapshot_uuid3 = Snapshot.create(cls.apiclient, volume_id = cls.volume7.id)
        cls._cleanup.append(cls.snapshot_uuid3)

        cls.snapshot_uuid4 = Snapshot.create(cls.apiclient, volume_id = cls.volume7.id)
        cls._cleanup.append(cls.snapshot_uuid4)

        cls.snapshot_uuid_bypassed = Snapshot.create(cls.apiclient, volume_id = list_root[0].id)
        cls._cleanup.append(cls.snapshot_uuid_bypassed)

        Volume.delete(cls.volume7, cls.apiclient)
         
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
            cfg.logger.info("Resources for cleanup %s", cls._cleanup)
            cleanup_resources(cls.apiclient, cls._cleanup)

            primary_storage = list_storage_pools(cls.apiclient, name=cls.primary_storage.name)[0]
            primary_storage2 = list_storage_pools(cls.apiclient, name=cls.primary_storage2.name)[0]

            storage_pool1 = StoragePool.enableMaintenance(cls.apiclient, primary_storage.id)
            storage_pool2 = StoragePool.enableMaintenance(cls.apiclient, primary_storage2.id)

            cls.delete_storage_pool(id = primary_storage.id)
            cls.delete_storage_pool(id = primary_storage2.id)

            cls.spapi.volumeTemplateDelete(templateName=cls.sp_template_1)
            cls.spapi.volumeTemplateDelete(templateName=cls.sp_template_2)
        except Exception as e:
            cfg.logger.info("cleanup_resources failed: %s", e)
            os.killpg(cls.mvn_proc_grp, signal.SIGTERM)

            time.sleep(30)

            raise Exception("Warning: Exception during cleanup : %s" % e)

        cfg.logger.info("Stopping CloudStack")
        os.killpg(cls.mvn_proc_grp, signal.SIGTERM)

        time.sleep(30)

        return

    @classmethod
    def delete_storage_pool(cls, id):
        cmd = deleteStoragePool.deleteStoragePoolCmd()
        cmd.id = id
        cls.apiclient.deleteStoragePool(cmd)

#resize root volume created with uuid with virtual machine created with uuid
    def test_01_resize_root_volume(self):

        
        self.assertEqual(VirtualMachine.RUNNING, self.virtual_machine4.state, "Running")

        listvol = Volume.list(
            self.apiclient,
            virtualmachineid = self.virtual_machine4.id,
            type = "ROOT"
            )

        volume = listvol[0]
        #volume is created with UUID, but after DB update, has to be with it's globalId
        self.helper.resizing_volume(volume, globalid=True)

    

#resize attached volume created with uuid with virtual machine with uuid
    def test_02_resize_attached_volume_uuid(self):
        
        self.assertEqual(VirtualMachine.RUNNING, self.virtual_machine.state, "Running")


        listvol = Volume.list(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            id= self.volume_on_sp_1.id
            )
        
        volume = listvol[0]
        #volume is created with UUID, but after DB update, has to be with it's globalId
        self.helper.resizing_volume(volume, globalid=True)

#resize attached volume created with globalid to virtual machine created with uuid
    def test_03_resize_attached_volume_globalid(self):
        self.assertEqual(VirtualMachine.RUNNING, self.virtual_machine2.state, "Running")

        volume = Volume.create(self.apiclient,
            {"diskname":"StorPoolDisk-GlId-%d" % random.randint(0, 100) },
            zoneid=self.zone.id,
            diskofferingid=self.disk_offering.id,
            )

        self.virtual_machine2.attach_volume(self.apiclient, volume)

        listvol = Volume.list(
            self.apiclient,
            virtualmachineid = self.virtual_machine2.id,
            id=volume.id
            )
        self.helper.resizing_volume(listvol[0], globalid=True)
        self.virtual_machine2.detach_volume(self.apiclient, volume)
        Volume.delete(volume, self.apiclient)

#resize attached volume created with uuid with virtual machine with globalid
    def test_04_resize_volume_uuid_vm_glid(self):
        vm = VirtualMachine.create(
                self.apiclient,
                {"name":"StorPool-%s" % uuid.uuid4() },
                zoneid=self.zone.id,
                templateid=self.template.id,
                serviceofferingid=self.service_offering.id,
                hypervisor=self.hypervisor,
                rootdisksize=10
                )
        volume = vm.attach_volume(self.apiclient, self.volume_on_sp_3)
        listvol = Volume.list(
            self.apiclient,
            id=volume.id
            )
        #volume is created with UUID, but after DB update, has to be with it's globalId
        self.helper.resizing_volume(listvol[0], globalid=True)
        vm.delete(self.apiclient, expunge=True)
        

#resize detached volume created with uuid
    def test_05_resize_detached_vol_uuid(self):
        #volume is created with UUID, but after DB update, has to be with it's globalId
        volume = Volume.list(self.apiclient, id = self.volume6.id )
        self.helper.resizing_volume(volume[0], globalid=True)


#resize detached volume created with globalid
    def test_06_resize_detach_vol_globalid(self):
        volume = Volume.create(self.apiclient,
            {"diskname":"StorPoolDisk-GlId-%d" % random.randint(0, 100) },
            zoneid=self.zone.id,
            diskofferingid=self.disk_offering.id,)

        self.virtual_machine2.attach_volume(self.apiclient, volume)

        self.virtual_machine2.detach_volume(self.apiclient, volume)


        listvol = Volume.list(
            self.apiclient,
            id=volume.id
            )
        self.helper.resizing_volume(listvol[0], globalid=True)
        Volume.delete(volume, self.apiclient)

#attach-detach volume created with uuid to vm with uuid
    def test_07_attach_detach_vol_uuid(self):
         #volume is created with UUID, but after DB update, has to be with it's globalId
        volume = Volume.list(self.apiclient, id = self.volume4.id )

        self.helper.storpool_volume_globalid(volume[0])
        self.virtual_machine3.attach_volume(self.apiclient, self.volume4)

        list = list_volumes(self.apiclient,virtualmachineid = self.virtual_machine3.id, id = self.volume4.id)

        self.assertIsNotNone(list, "Volume was not attached")

        detached = self.virtual_machine3.detach_volume(self.apiclient, self.volume4)
        self.assertIsNone(detached.virtualmachineid, "Volume was not detached from vm")

#attach-detach volume created with uuid to vm with globalid
    def test_08_attach_detach_vol_glId(self):
        vm = VirtualMachine.create( self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=self.template.id,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
            )

        vm.attach_volume(self.apiclient, self.volume5)
         #volume is created with UUID, but after DB update, has to be with it's globalId
        volume = Volume.list(self.apiclient, id = self.volume5.id )

        self.helper.storpool_volume_globalid(volume[0])


        list = list_volumes(self.apiclient,virtualmachineid = vm.id, id = self.volume5.id)

        self.assertIsNotNone(list, "Volume was not attached")
        vm.stop(self.apiclient, forced=True)

        detached = vm.detach_volume(self.apiclient, self.volume5)
        self.assertIsNone(detached.virtualmachineid, "Volume was not detached from vm")
        vm.delete(self.apiclient, expunge=True)
        
#attach-detach volume with global id to vm with uuid
    def test_09_attach_detach_vol_glId(self):
        volume = Volume.create(self.apiclient,
            {"diskname":"StorPoolDisk-GlId-%d" % random.randint(0, 100) },
            zoneid=self.zone.id,
            diskofferingid=self.disk_offering.id,
            )
        self.virtual_machine3.attach_volume(self.apiclient, volume)
        list = list_volumes(self.apiclient,virtualmachineid = self.virtual_machine3.id, id = volume.id)

        self.assertIsNotNone(list, "Volume was not attached")
        
        self.helper.storpool_volume_globalid(list[0])
        self.virtual_machine3.stop(self.apiclient, forced=True)

        detached = self.virtual_machine3.detach_volume(self.apiclient, list[0])
        self.assertIsNone(detached.virtualmachineid, "Volume was not detached from vm")
        Volume.delete(volume, self.apiclient)


#attach-detach volume with global id to vm with globalid
    def test_10_attach_detach_instances_with_glId(self):
        volume = Volume.create(
            self.apiclient,
            {"diskname":"StorPoolDisk-GlId-%d" % random.randint(0, 100) },
            zoneid=self.zone.id,
            diskofferingid=self.disk_offering.id,
            )
        vm = VirtualMachine.create( self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=self.template.id,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
            )

        vm.attach_volume(self.apiclient, volume)

        list = list_volumes(self.apiclient,virtualmachineid = vm.id, id = volume.id)
        list_root = list_volumes(self.apiclient,virtualmachineid = vm.id, type = "ROOT")

        self.assertIsNotNone(list, "Volume was not attached")
        self.assertIsNotNone(list_root, "ROOT volume is missing")
       
        self.helper.storpool_volume_globalid(list[0])
        self.helper.storpool_volume_globalid(list_root[0])

        vm.stop(self.apiclient, forced=True)
        detached = vm.detach_volume(self.apiclient, list[0])
        self.assertIsNone(detached.virtualmachineid, "Volume was not detached from vm")
        Volume.delete(volume, self.apiclient)
        vm.delete(self.apiclient, expunge=True)

#snapshot with uuid to volume
    def test_11_volume_from_snapshot_with_uuid(self):
        #snapshot_uuid1
        self.helper.storpool_snapshot_uuid(self.snapshot_uuid1)

        volume = self.helper.create_volume(zoneid = self.zone.id, snapshotid = self.snapshot_uuid1.id)

        self.assertIsNotNone(volume, "Could not create volume from snapshot")

        self.helper.storpool_volume_globalid(volume)

        Volume.delete(volume, self.apiclient)

#snapshot detached volume with uuid
    def test_12_snapshot_detached_vol_with_uuid(self):
        #volume is created with UUID, but after DB update, has to be with it's globalId
        volume = Volume.list(self.apiclient, id = self.volume6.id )

        self.helper.storpool_volume_globalid(volume[0])

        snapshot = Snapshot.create(self.apiclient, volume_id = self.volume6.id,)

        self.assertIsNotNone(snapshot, "Could not create snapshot")

        self.helper.storpool_snapshot_globalid(snapshot)

        self._cleanup.append(snapshot)

#snapshot detached volume with globalid
    def test_13_snapshot_detached_vol_with_glid(self):
        volume = Volume.create(
            self.apiclient,
            {"diskname":"StorPoolDisk-GlId-%d" % random.randint(0, 100) },
            zoneid=self.zone.id,
            diskofferingid=self.disk_offering.id,
            )

        self.virtual_machine3.start(self.apiclient)
        self.virtual_machine3.attach_volume(self.apiclient, volume)
        list = list_volumes(self.apiclient,virtualmachineid = self.virtual_machine3.id, id = volume.id)

        self.assertIsNotNone(list, "Volume was not attached")
        
        self.helper.storpool_volume_globalid(list[0])
        self.virtual_machine3.stop(self.apiclient, forced=True)

        snapshot = Snapshot.create(self.apiclient, volume_id = volume.id,)

        self.assertIsNotNone(snapshot, "Could not create snapshot")

        self.helper.storpool_snapshot_globalid(snapshot)

        self._cleanup.append(volume)
        self._cleanup.append(snapshot)

#snapshot root disk for vm with uuid
    def test_14_snapshot_root_vol_with_uuid(self):
        list = list_volumes(self.apiclient, virtualmachineid = self.virtual_machine.id, type = "ROOT")
        self.assertIsNotNone(list, "Could not find ROOT volume")

        self.helper.storpool_volume_globalid(list[0])

        snapshot = Snapshot.create(self.apiclient, volume_id =  list[0].id,)

        self.assertIsNotNone(snapshot, "Could not create snapshot")

        self.helper.storpool_snapshot_globalid(snapshot)
        self._cleanup.append(snapshot)

#snapshot root disk for vm with globalid
    def test_15_snapshot_root_vol_glid(self):
        vm = VirtualMachine.create( self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=self.template.id,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
            )
        list = list_volumes(self.apiclient, virtualmachineid = vm.id, type = "ROOT")
        self.assertIsNotNone(list, "Could not find ROOT volume")

        self.helper.storpool_volume_globalid(list[0])

        snapshot = Snapshot.create(self.apiclient, volume_id = list[0].id,)
        self.assertIsNotNone(snapshot, "Could not create snapshot")

        self.assertIsInstance(snapshot, Snapshot, "Created snapshot is not instance of Snapshot")

        self.helper.storpool_snapshot_globalid(snapshot)

        self._cleanup.append(vm)
        self._cleanup.append(snapshot)
     

#volume with uuid to template
    def test_16_template_from_volume_with_uuid(self):
        list = list_volumes(self.apiclient, virtualmachineid = self.virtual_machine.id, type = "ROOT")

        self.helper.storpool_volume_globalid(list[0])
        
        self.virtual_machine.stop(self.apiclient, forced = True)

        template = self.helper.create_template_from_snapshot_or_volume(services = self.services, volumeid = list[0].id)

        self.helper.create_vm_from_template(template, False)

        Template.delete(template, self.apiclient, zoneid = self.zone.id)

#volume with global id to template
    def test_17_template_from_vol_glid(self):
        vm = VirtualMachine.create( self.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=self.zone.id,
            templateid=self.template.id,
            serviceofferingid=self.service_offering.id,
            hypervisor=self.hypervisor,
            rootdisksize=10
            )
        list = list_volumes(self.apiclient, virtualmachineid = vm.id, type = "ROOT")
        self.assertIsNotNone(list, "Could not find ROOT volume")

        self.helper.storpool_volume_globalid(list[0])

        vm.stop(self.apiclient, forced = True)

        template = self.helper.create_template_from_snapshot_or_volume(services = self.services, volumeid = list[0].id)

        self.helper.create_vm_from_template(template, False)

        self._cleanup.append(vm)
        self._cleanup.append(template)

#snapshot on secondary with uuid to template on secondary
    def test_18_template_from_snapshot_uuid(self):
        self.helper.storpool_snapshot_uuid(self.snapshot_uuid_on_secondary)

        self.helper.bypass_secondary(False)

        template = self.helper.create_template_from_snapshot_or_volume(services = self.services, snapshotid = self.snapshot_uuid_on_secondary.id)

        self.helper.create_vm_from_template(template, False)

        self._cleanup.append(template)


#snapshot with global id on secondary to template from volume with uuid bypass
    def test_19_template_from_snapshot_glid_on_secondary(self):

        volume = list_volumes(self.apiclient, virtualmachineid = self.virtual_machine6.id, type = "ROOT")

        self.helper.bypass_secondary(False)
        snapshot = Snapshot.create(self.apiclient, volume_id = volume[0].id,)

        self.helper.storpool_snapshot_globalid(snapshot)

        template = self.helper.create_template_from_snapshot_or_volume(services = self.services, snapshotid = snapshot.id)

        self.helper.create_vm_from_template(template, False)

        self._cleanup.append(template)
        self._cleanup.append(snapshot)

#snapshot with global id on secondary to template from volume with uuid on secondary
    def test_20_template_from_snapshot_glid_on_secondary(self):

        volume = list_volumes(self.apiclient, virtualmachineid = self.virtual_machine6.id, type = "ROOT")

        self.helper.bypass_secondary(False)
        snapshot = Snapshot.create(self.apiclient, volume_id = volume[0].id,)

        self.helper.storpool_snapshot_globalid(snapshot)

        template = self.helper.create_template_from_snapshot_or_volume(services = self.services, snapshotid = snapshot.id)

        self.helper.create_vm_from_template(template)

        self._cleanup.append(template)
        self._cleanup.append(snapshot)
    
    def test_21_volume_from_snapshot_secondary(self):
        '''Create volume from snapshot(with uuid) on secondary, which volume was deleted
            and snapshot does not exists on StorPool or snapshot_details DB table
        '''
        #check that snapshot exists on StorPool
        try:
            sp_snapshot = self.spapi.snapshotList(snapshotName = self.snapshot_uuid3.id)
        except spapi.ApiError as err:
           raise Exception(err)

        #remove the snapshot from StorPool so it has to be downloaded from secondary
        self.spapi.snapshotDelete(snapshotName = self.snapshot_uuid3.id)
        volume = self.helper.create_volume(snapshotid = self.snapshot_uuid3.id)
        flag = False
        #new snapshot has to be added to snapshot_details and created new snapshot in StorPool
        try:
            cmd = getVolumeSnapshotDetails.getVolumeSnapshotDetailsCmd()
            cmd.snapshotid = self.snapshot_uuid3.id
            snapshot_details = self.apiclient.getVolumeSnapshotDetails(cmd)
            cfg.logger.info("Snapshot details %s" , snapshot_details)
            cfg.logger.info("Snapshot with uuid %s" , self.snapshot_uuid3.id)
            for s in snapshot_details:
                if s["snapshotDetailsName"] == self.snapshot_uuid3.id:
                    name = s["snapshotDetailsValue"].split("/")[3]
                    sp_snapshot = self.spapi.snapshotList(snapshotName = "~" + name)
                    flag = True
        except spapi.ApiError as err:
           raise Exception(err)
        if flag == False:
            raise Exception("Could not find snapshot in snapshot details")
        self._cleanup.append(volume)

    def test_22_volume_from_snapshot_bypassed(self):
        '''Create volume from snapshot (with uuid) on secondary, which volume was deleted
            and snapshot does not exists on StorPool or snapshot_details DB table
        '''
        #check that the snapshot exists on StorPool
        globalIdName = self.snapshot_uuid4.id
        try:
            sp_snapshot = self.spapi.snapshotList(snapshotName = self.snapshot_uuid4.id)
        except spapi.ApiError as err:
           raise Exception(err)

        volume = self.helper.create_volume(snapshotid = self.snapshot_uuid4.id)
        flag = False
        try:
            cmd = getVolumeSnapshotDetails.getVolumeSnapshotDetailsCmd()
            cmd.snapshotid = self.snapshot_uuid4.id
            snapshot_details = self.apiclient.getVolumeSnapshotDetails(cmd)
            cfg.logger.info("Snapshot details %s" , snapshot_details)
            cfg.logger.info("Snapshot with uuid %s" , self.snapshot_uuid4.id)
            for s in snapshot_details:
                if s["snapshotDetailsName"] == self.snapshot_uuid4.id:
                    name = s["snapshotDetailsValue"].split("/")[3]
                    sp_snapshot = self.spapi.snapshotList(snapshotName = "~" + name)
                    flag = True
        except spapi.ApiError as err:
           raise Exception(err)
        if flag == False:
            raise Exception("Could not find snapshot in snapshot details")
        self._cleanup.append(volume)


#set vc_policy tag to vm with uuid with attached disk with uuid
    def test_23_vc_policy_with_attached_disk_uuid(self):
        self.virtual_machine.attach_volume(self.apiclient, self.volume8)
        list = list_volumes(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            id = self.volume8.id
            )
        self.assertIsNotNone(list, "Volume=%s was not attached to vm=%s" %(self.volume8.id, self.virtual_machine.id))

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


#set vc policy tag to volume with uuid which will be attached to vm with uuid
    def test_24_attach_volume_to_vm_with_vc_policy_uuid(self):
        self.virtual_machine.attach_volume(self.apiclient, self.volume4)

        vm = list_virtual_machines(self.apiclient,id = self.virtual_machine.id)
        vm_tags = vm[0].tags
        volumes = list_volumes(
            self.apiclient,
            virtualmachineid = self.virtual_machine.id,
            )
        for v in volumes:
            self.helper.vc_policy_tags_global_id(v, vm_tags, False)
        

#set vc policy tag to volume with global which will be attached to vm with uuid
    def test_25_vc_policy_attach_vol_global_id_vm_uuid(self):

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
    def test_27_vc_policy_to_volume_and_vm_with_glid(self):
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


    @classmethod
    def getCfgFromUrl(cls, url):
        cfg = dict([
            option.split('=')
            for option in url.split(';')
        ])
        host, port = cfg['SP_API_HTTP'].split(':')
        auth = cfg['SP_AUTH_TOKEN']
        return host, int(port), auth

def main():
    original = (sys.stdout, sys.stderr)
    try:
        helper = HelperUtil()
        parser = argparse.ArgumentParser()
        TestMigrationFromUuidToGlobalIdVolumes.ARGS = helper.argument_parser(parser)
        cfg.logger.info("Arguments  %s", TestMigrationFromUuidToGlobalIdVolumes.ARGS)

        cfg.logger.info("Redirecting sys.stdout and sys.stderr to %s", cfg.misc_name)
        sys.stdout = cfg.misc
        sys.stderr = cfg.misc

        unittest.main(testRunner=TeeTextTestRunner)
    except BaseException as exc:
        sys.stdout, sys.stderr = original
        cfg.logger.info(original)
        raise
    finally:
        sys.stdout, sys.stderr = original


if __name__ == "__main__":
    main()
