#!/usr/bin/env python2.7

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
                                  startVirtualMachine,
                                  migrateVirtualMachineWithVolume,
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
from nose.tools import assert_equal, assert_not_equal, assert_true

from storpool import spapi

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
    primaryStorage2 = "primarystorage2"
    provider = "provider"
    serviceOffering = "serviceOffering"
    serviceOfferingssd2 = "serviceOffering-ssd2"
    serviceOfferingsPrimary = "serviceOfferingsPrimary"
    scope = "scope"
    StorPool = "storpool"
    storageTag = ["ssd", "ssd2"]
    tags = "tags"
    virtualMachine = "virtualmachine"
    virtualMachine2 = "virtualmachine2"
    volume_1 = "volume_1"
    volume_2 = "volume_2"
    volume_3 = "volume_3"
    volume_4 = "volume_4"
    volume_5 = "volume_5"
    volume_6 = "volume_6"
    volume_7 = "volume_7"
    zoneId = "zoneId"


    def __init__(self):
        self.testdata = {
            TestData.primaryStorage: {
                "name": "ssd",
                TestData.scope: "ZONE",
                "url": "ssd",
                TestData.provider: "StorPool",
                "path": "/dev/storpool",
                TestData.capacityBytes: 2251799813685248,
                TestData.hypervisor: "KVM"
            },
            TestData.primaryStorage2: {
                "name": "ssd2",
                TestData.scope: "ZONE",
                "url": "ssd2",
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
                "name": "ssd",
                "displaytext": "SP_CO_2 (Min IOPS = 10,000; Max IOPS = 15,000)",
                "cpunumber": 1,
                "cpuspeed": 500,
                "memory": 512,
                "storagetype": "shared",
                "customizediops": False,
                "hypervisorsnapshotreserve": 200,
                "tags": "ssd"
            },
            TestData.serviceOfferingssd2:{
                "name": "ssd2",
                "displaytext": "SP_CO_2 (Min IOPS = 10,000; Max IOPS = 15,000)",
                "cpunumber": 1,
                "cpuspeed": 500,
                "memory": 512,
                "storagetype": "shared",
                "customizediops": False,
                "hypervisorsnapshotreserve": 200,
                "tags": "ssd2"
            },
            TestData.serviceOfferingsPrimary:{
                "name": "nfs",
                "displaytext": "SP_CO_2 (Min IOPS = 10,000; Max IOPS = 15,000)",
                "cpunumber": 1,
                "cpuspeed": 500,
                "memory": 512,
                "storagetype": "shared",
                "customizediops": False,
                "hypervisorsnapshotreserve": 200,
                "tags": "nfs"
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
            TestData.volume_3: {
                TestData.diskName: "test-volume-3",
            },
            TestData.volume_4: {
                TestData.diskName: "test-volume-4",
            },
            TestData.volume_5: {
                TestData.diskName: "test-volume-5",
            },
            TestData.volume_6: {
                TestData.diskName: "test-volume-6",
            },
            TestData.volume_7: {
                TestData.diskName: "test-volume-7",
            },
        }


class TeeStream(object):
    """Copy the output to a stream and a file."""

    def __init__(self, original, filename, encoding="UTF-8"):
        """Store the original stream and stuff."""
        self.original = original
        self.filename = filename
        self.encoding = encoding

        self.outfile = io.open(self.filename, mode="w", encoding=self.encoding)

    def write(self, data):
        """Write the data after maybe decoding it."""
        assert self.outfile is not None
        if not isinstance(data, unicode):
            data = data.decode(self.encoding)

        self.original.write(data)
        self.outfile.write(data)

    def flush(self):
        self.original.flush()
        self.outfile.flush()

    def close(self):
        try:
            return self.outfile.close()
        finally:
            self.outfile = None


class StaticConfig(object):

    def __init__(self):
        self._logdir = None
        self._misc = None
        self._logstream = None
        self._logger = None

    @property
    def logdir(self):
        if self._logdir is not None:
            return self._logdir

        temp_ts = time.strftime("%Y-%m-%d-%H%M%S", time.localtime())
        logdir = "/tmp/storpool-plugin/log-{ts}".format(ts=temp_ts)
        os.mkdir(logdir, 0o700)

        self._logdir = logdir
        return self._logdir

    @property
    def logstream(self):
        if self._logstream is not None:
            return self._logstream

        logstream = TeeStream(
            sys.stdout,
            "{logdir}/runner.log".format(logdir=self.logdir),
        )

        self._logstream = logstream
        return self._logstream

    @property
    def logger(self):
        if self._logger is not None:
            return self._logger

        logger = logging.getLogger(__name__)
        hdlr = logging.StreamHandler(self.logstream)
        logger.addHandler(hdlr)
        logger.setLevel(logging.DEBUG)
        logger.info("Logging to %s", self.logdir)

        self._logger = logger
        return self._logger

    @property
    def misc_name(self):
        return "{logdir}/misc.log".format(logdir=self.logdir)

    @property
    def misc(self):
        if self._misc is not None:
            return self._misc

        misc = open(self.misc_name, mode="w")

        self._misc = misc
        return self._misc


cfg = StaticConfig()

class HelperUtil:
    def __init__(self, object=None):
        self.testClass = object
        self.spapi = spapi.Api.fromConfig(multiCluster=True)

    def switch_to_globalid_commit(cls, GLOBALID, ARGS):
        ''' testing '''
        cfg.logger.info("Switching to the global ID commit %s", GLOBALID)
        cfg.logger.info("Stopping CloudStack")
        cfg.logger.info("Should kill PID %s", cls.testClass.mvn_proc_grp)
        os.killpg(cls.testClass.mvn_proc_grp, signal.SIGTERM)

        time.sleep(30)

        cfg.logger.info("Waiting for a while to give it a chance to stop")
        cls.build_commit(GLOBALID, ARGS)
        cfg.logger.info("Starting CloudStack")
        cls.mvn_proc = subprocess.Popen(
            ['mvn', '-pl', ':cloud-client-ui', 'jetty:run'],
            cwd=ARGS.forked,
            preexec_fn=os.setsid,
            stdout=cfg.misc,
            stderr=subprocess.STDOUT,
            )
        cls.testClass.mvn_proc_grp = os.getpgid(cls.mvn_proc.pid)
        cfg.logger.info("Started CloudStack in process group %d", cls.testClass.mvn_proc_grp)
        cfg.logger.info("Waiting for a while to give it a chance to start")
        proc = subprocess.Popen(["tail", "-f", cfg.misc_name], shell=False, bufsize=0, stdout=subprocess.PIPE)
        while True:
            line = proc.stdout.readline()
            if not line:
                cfg.logger.info("tail ended, was this expected?")
                cfg.logger.info("Stopping CloudStack")
                os.killpg(cls.testClass.mvn_proc_grp, signal.SIGTERM)
                break
            if "[INFO] Started Jetty Server" in line:
                cfg.logger.info("got it!")
                break 
        proc.terminate()
        proc.wait()
        time.sleep(15)
        cfg.logger.info("Processing with Marvin and the tests")
        cls.obj_marvininit = cls.marvin_init(ARGS.cfg)
        cls.testClient = cls.obj_marvininit.getTestClient()
        cls.testClass.apiclient = cls.testClient.getApiClient()
        
    def build_commit(cls, input, args):
        cfg.logger.info("Building CloudStack commit %s", input)
        subprocess.check_call(
                        [
                args.build,
                "-d",
                args.directory,
                "-c",
                input,
                "-f",
                args.forked,
                "-r",
                args.remote,
                "-s",
                args.second,
                "-t",
                args.third,
                "-a",
                args.fourth
            ],
#             [
#                 "/home/test_storpool/cloudstack/marvin/build-cloudstack",
#                 "-d",
#                 "/home/test_storpool/cloudstack",
#                 "-c",
#                 input,
#                 "-f",
#                 "/home/forkedCloudStack/cloudstack",
#                 "-r",
#                 "root@10.2.1.211",
#                 "-s",
#                 "root@10.2.1.210",
#             ],
            shell=False,
            stdout=cfg.misc,
            stderr=subprocess.STDOUT,
        )
        cfg.logger.info("Switched to commit %s", input)

    def marvin_init(cls, cfg):
        try:
            obj_marvininit = MarvinInit(config_file=cfg,
                                            hypervisor_type="kvm",
                                            user_logfolder_path="/tmp")
            if obj_marvininit and obj_marvininit.init() == SUCCESS:
                    obj_marvininit.__testClient = obj_marvininit.getTestClient()
                    obj_marvininit.__tcRunLogger = obj_marvininit.getLogger()
                    obj_marvininit.__parsedConfig = obj_marvininit.getParsedConfig()
                    obj_marvininit.__resultStream = obj_marvininit.getResultFile()
                    obj_marvininit.__logFolderPath = obj_marvininit.getLogFolderPath()
        except Exception as e:
            os.killpg(cls.testClass.mvn_proc_grp, signal.SIGTERM)

            time.sleep(30)
            return FAILED
        return obj_marvininit

    def write_on_disks(cls, random_data_0, virtual_machine, test_dir, random_data):
        try:
            # Login to VM and write data to file system
            ssh_client = virtual_machine.get_ssh_client()

            cmds = [
                "echo %s > %s/%s" %
                (random_data_0, test_dir, random_data),
                "sync",
                "sleep 1",
                "sync",
                "sleep 1",
                "cat %s/%s" %
                (test_dir, random_data)
            ]

            for c in cmds:
                result = ssh_client.execute(c)


        except Exception as e:
            raise  Exception(e)
        assert_equal(
            random_data_0,
            result[0],
            "Check the random data has be write into temp file!"
        )

    def delete_random_data_after_vmsnpashot(cls, vm_snapshot, virtual_machine, test_dir , random_data):
        cfg.logger.info('delete_random_data_after_vmsnpashot')
        assert_equal(
            vm_snapshot.state,
            "Ready",
            "Check the snapshot of vm is ready!"
        )

        try:
            ssh_client = virtual_machine.get_ssh_client()
     
            cmds = [
                "rm -rf %s/%s" % (test_dir, random_data),
                "ls %s/%s" % (test_dir, random_data)
            ]
     
            for c in cmds:
                result = ssh_client.execute(c)
     
        except Exception:
            cls.testClass.fail("SSH failed for Virtual machine: %s" %
                      virtual_machine.ipaddress)
     
        if str(result[0]).index("No such file or directory") == -1:
            cls.testClass.fail("Check the random data has be delete from temp file!")
     
        time.sleep(30)
     
        list_snapshot_response = VmSnapshot.list(
            cls.testClass.apiclient,
            virtualmachineid=virtual_machine.id,
            listall=True)
     
        assert_equal(
            isinstance(list_snapshot_response, list),
            True,
            "Check list response returns a valid list"
        )
        assert_not_equal(
            list_snapshot_response,
            None,
            "Check if snapshot exists in ListSnapshot"
        )
        
    def create_snapshot(cls, bypassed, virtual_machine):
        volume = Volume.list(
            cls.testClass.apiclient,
            virtualmachineid = virtual_machine.id,
            type = "ROOT"
            )
        cls.bypass_secondary(bypassed)
        cfg.logger.info('Create snapshot bypassed secondary %s' % bypassed)
        return Snapshot.create(
           cls.testClass.apiclient,
            volume_id = volume[0].id
            )

    def bypass_secondary(cls, bypassed):
        if bypassed:
            backup_config = Configurations.update(cls.testClass.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "true")
        else:
            backup_config = Configurations.update(cls.testClass.apiclient,
            name = "sp.bypass.secondary.storage",
            value = "false")
        cfg.logger.info(list_configurations(
            cls.testClass.apiclient,
            name = "sp.bypass.secondary.storage"))

    def create_vm_snapshot(cls, MemorySnapshot, virtual_machine):
        return  VmSnapshot.create(
            cls.testClass.apiclient,
            virtual_machine.id,
            MemorySnapshot,
            "TestSnapshot",
            "Display Text"
        )   

    def create_vm_from_template(cls, template, onStorpool=None):
        storpoolGlId = None
        if onStorpool:
            flag = False
            sp_snapshots = cls.testClass.spapi.snapshotsList()
           # cfg.logger.info(sp_snapshots)
            cfg.logger.info(template.id)
            for snap in sp_snapshots:
                tags = snap.tags
                for t in tags:
                    if tags[t] == template.id:
                        cfg.logger.info(snap)
                        storpoolGlId = snap
                        cfg.logger.info("create_vm_from_template snapshotsList %s" % storpoolGlId)
                        flag = True
                        break
                else:
                    continue
                break
                           
            if flag is False:
                try:
                    sp_snapshot = cls.testClass.spapi.snapshotList(snapshotName = template.id)
                    cfg.logger.info("create_vm_from_template snapshotsList %s" % sp_snapshot)
                except spapi.ApiError as err:
                    raise Exception(err)
               # raise Exception("Template does not exists in Storpool")
        virtual_machine = VirtualMachine.create(
            cls.testClass.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4()},
            zoneid=cls.testClass.zone.id,
            templateid=template.id,
            serviceofferingid=cls.testClass.service_offering.id,
            hypervisor=cls.testClass.hypervisor,
            rootdisksize=10
            )
        ssh_client = virtual_machine.get_ssh_client(reconnect=True)
        cls.testClass._cleanup.append(virtual_machine)
        if storpoolGlId is not None:
            return storpoolGlId.globalId

    def check_snapshot_is_deleted_from_storpool(cls, snapshot):
        try:
            sp_snapshot = cls.testClass.spapi.snapshotList(snapshotName = "~" + snapshot)
            cfg.logger.info("check_snapshot_is_deleted_from_storpool snapshotsList %s" % sp_snapshot)
            return False
        except spapi.ApiError as err:
            return True

    def create_template_from_snapshot(cls, services, snapshotid=None, volumeid=None):
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
            ostypes = cls.testClass.apiclient.listOsTypes(sub_cmd)

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
        return Template(cls.testClass.apiclient.createTemplate(cmd).__dict__)

    def resizing_volume(cls, volume, virtual_machine=None, globalid=None, uuid=None):
        #Only data volumes can be resized via a new disk offering.
        if volume.type == "ROOT":
            cfg.logger.info("Resizing Root volume")
            if globalid:
                cls.storpool_volume_globalid(volume)
            elif uuid:
                cls.storpool_volume_uuid(volume)
    
            shrinkOk = False
            if volume.size > int((cls.testClass.disk_offering_20.disksize) * (1024**3)):
                shrinkOk= True
    
            volume = cls.resize_volume(volume, shrinkOk, size = cls.testClass.disk_offering_20.disksize)
    
            if globalid:
                cls.check_size_by_globalid(volume)
            elif uuid:
                cls.check_size_by_uuid(volume)
    
            shrinkOk = False
            if volume.size > int((cls.testClass.disk_offering_100.disksize) * (1024**3)):
                shrinkOk= True
    
            volume = cls.resize_volume(volume, shrinkOk, size = cls.testClass.disk_offering_100.disksize)
    
            if globalid:
                cls.check_size_by_globalid(volume)
            elif uuid:
                cls.check_size_by_uuid(volume)
    
            shrinkOk = False
            if volume.size > int((cls.testClass.disk_offering.disksize)* (1024**3)):
                shrinkOk= True
    
            volume = cls.resize_volume(volume, shrinkOk, size = cls.testClass.disk_offering.disksize)
    
            if globalid:
                cls.check_size_by_globalid(volume)
            elif uuid:
                cls.check_size_by_uuid(volume)

        else:
            #check that volume exists on StorPool
            cfg.logger.info("Resizing Data Disk volume")
            if globalid:
                cls.storpool_volume_globalid(volume)
            elif uuid:
                cls.storpool_volume_uuid(volume)
    
            shrinkOk = False
            if volume.size > int((cls.testClass.disk_offering_20.disksize) * (1024**3)):
                shrinkOk= True
    
            volume = cls.resize_volume(volume, shrinkOk, disk_offering = cls.testClass.disk_offering_20)
    
            if globalid:
                cls.check_size_by_globalid(volume)
            elif uuid:
                cls.check_size_by_uuid(volume)
    
            shrinkOk = False
            if volume.size > int((cls.testClass.disk_offering_100.disksize) * (1024**3)):
                shrinkOk= True
    
            volume = cls.resize_volume(volume, shrinkOk, disk_offering = cls.testClass.disk_offering_100)
    
            if globalid:
                cls.check_size_by_globalid(volume)
            elif uuid:
                cls.check_size_by_uuid(volume)
    
            shrinkOk = False
            if volume.size > int((cls.testClass.disk_offering.disksize)* (1024**3)):
                shrinkOk= True
    
            volume = cls.resize_volume(volume, shrinkOk, disk_offering = cls.testClass.disk_offering)
    
            if globalid:
                cls.check_size_by_globalid(volume)
            elif uuid:
                cls.check_size_by_uuid(volume)

    def storpool_volume_globalid(cls, volume):
        name = volume.path.split("/")[3]
        try:
            spvolume = cls.spapi.volumeList(volumeName = "~" + name)
            cfg.logger.info("storpool_volume_globalid volumeList %s" % spvolume)
        except spapi.ApiError as err:
           raise Exception(err)
        
    def storpool_volume_uuid(cls, volume):
        try:
            spvolume = cls.testClass.spapi.volumeList(volumeName = volume.id)
            cfg.logger.info("storpool_volume_uuid volumeList %s" % spvolume)
        except spapi.ApiError as err:
           raise Exception(err)

    def storpool_snapshot_globalid(cls, snapshot):
        flag = False
        sp_snapshots = cls.testClass.spapi.snapshotsList()
        globalId = None
        for snap in sp_snapshots:
            tags = snap.tags
            for t in tags:
                if tags[t] == snapshot.id:
                    flag = True
                    globalId = snap.name
                    cfg.logger.info("storpool_snapshot_globalid snapshotsList %s" % globalId)
                    break
            else:
                continue
            break
                       
        if flag is False:
            raise Exception(err)
        return globalId
        
    def storpool_snapshot_uuid(cls, snapshot):
        try:
            spsnapshot = cls.testClass.spapi.snapshotList(snapshotName = snapshot.id)
            cfg.logger.info("storpool_snapshot_uuid snapshotList %s" % spsnapshot)
        except spapi.ApiError as err:
           raise Exception(err)

    def check_size_by_globalid(cls, volume):
        name = volume.path.split("/")[3]
        try:
            spvolume = cls.testClass.spapi.volumeList(volumeName = "~" + name)
            cfg.logger.info("check_size_by_globalid volumeList %s" % spvolume)
            if spvolume[0].size != volume.size:
                raise Exception("Storpool volume size is not the same as CloudStack db size")
        except spapi.ApiError as err:
           raise Exception(err)
        
    def check_size_by_uuid(cls, volume):
        try:
            spvolume = cls.testClass.spapi.volumeList(volumeName = volume.id)
            cfg.logger.info("check_size_by_uuid volumeList %s" % spvolume)
            if spvolume[0].size != volume.size:
                raise Exception("Storpool volume size is not the same as CloudStack db size")
        except spapi.ApiError as err:
           raise Exception(err)

    def resize_volume(cls, volume, shrinkOk, disk_offering =None, size=None):

        cmd = resizeVolume.resizeVolumeCmd()
        cmd.id = volume.id

        if disk_offering:
            cmd.diskofferingid = disk_offering.id
            disk_offering_size = int((disk_offering.disksize) * (1024**3))
        if size:
            cmd.size = size
            disk_offering_size = size << 30

        cmd.shrinkok = shrinkOk
        cfg.logger.info("resizing volume=%s to size %s" % (volume.id, disk_offering_size))
        cls.testClass.apiclient.resizeVolume(cmd)

        new_size = Volume.list(
            cls.testClass.apiclient,
            id=volume.id
            )
        volume_size = new_size[0].size

        assert_true(
            volume_size == disk_offering_size,
            "New size is not int((cls.disk_offering_20) * (1024**3)"
            )
        return new_size[0]

    def create_volume(cls, zoneid=None, snapshotid=None):
        """Create Volume"""
        cmd = createVolume.createVolumeCmd()
        cmd.name = "Test"

        if zoneid:
            cmd.zoneid = zoneid

        if snapshotid:
            cmd.snapshotid = snapshotid
        return Volume(cls.testClass.apiclient.createVolume(cmd).__dict__)

    def create_template_from_snapshot_or_volume(cls, services, snapshotid=None, volumeid=None):
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
            ostypes = cls.testClass.apiclient.listOsTypes(sub_cmd)

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
        return Template(cls.testClass.apiclient.createTemplate(cmd).__dict__)

    def start_vm(cls, vmid, hostid):
        """Start the instance"""
        cmd = startVirtualMachine.startVirtualMachineCmd()
        cmd.id = vmid
        if hostid:
            cmd.hostid = hostid
        return (cls.testClass.apiclient.startVirtualMachine(cmd))
    
    def vc_policy_tags_global_id(self, volume, vm_tags, uuid):
        flag = False
        name = None
        if uuid:
            name = volume.path.split("/")[3]
        else:
            name = volume.path.split("/")[3]
            name = "~" + name

        spvolume = self.testClass.spapi.volumeList(volumeName = name)
        cfg.logger.info("vc_policy_tags_global_id volumeList %s" % spvolume)
        tags = spvolume[0].tags
        for t in tags:
            for vm_tag in vm_tags:
                if t == vm_tag.key:
                    flag = True
                    assert_equal(tags[t], vm_tag.value, "Tags are not equal")
        assert_true(flag, "There aren't volumes with vm tags")

    def get_local_cluster(self):
       storpool_clusterid = subprocess.check_output(['storpool_confshow', 'CLUSTER_ID'])
       clusterid = storpool_clusterid.split("=")
       clusters = list_clusters(self.testClass.apiclient)
       for c in clusters:
           configuration = list_configurations(
               self.testClass.apiclient,
               clusterid = c.id
               )
           for conf in configuration:
               if conf.name == 'sp.cluster.id'  and (conf.value in clusterid[1]):
                   return c

    def get_remote_cluster(cls):
       storpool_clusterid = subprocess.check_output(['storpool_confshow', 'CLUSTER_ID'])
       clusterid = storpool_clusterid.split("=")
       clusters = list_clusters(cls.testClass.apiclient)
       for c in clusters:
           configuration = list_configurations(
               cls.testClass.apiclient,
               clusterid = c.id
               )
           for conf in configuration:
               if conf.name == 'sp.cluster.id'  and (conf.value not in clusterid[1]):
                   return c

    def list_hosts_by_cluster_id(self, clusterid):
        """List all Hosts matching criteria"""
        cmd = listHosts.listHostsCmd()
        cmd.clusterid = clusterid  
        return(self.testClass.apiclient.listHosts(cmd))
    
    def migrateVmWithVolumes(self, vm, destinationHost, volumes, pool):
        """
            This method is used to migrate a vm and its volumes using migrate virtual machine with volume API
            INPUTS:
                   1. vm -> virtual machine object
                   2. destinationHost -> the host to which VM will be migrated
                   3. volumes -> list of volumes which are to be migrated
                   4. pools -> list of destination pools
        """
        vol_pool_map = {vol.id: pool.id for vol in volumes}
    
        cmd = migrateVirtualMachineWithVolume.migrateVirtualMachineWithVolumeCmd()
        cmd.hostid = destinationHost.id
        cmd.migrateto = []
        cmd.virtualmachineid = self.virtual_machine.id
        for volume, pool1 in vol_pool_map.items():
            cmd.migrateto.append({
                'volume': volume,
                'pool': pool1
        })
        self.testClass.apiclient.migrateVirtualMachineWithVolume(cmd)

        vm.getState(
            self.testClass.apiclient,
            "Running"
        )
        # check for the VM's host and volume's storage post migration
        migrated_vm_response = list_virtual_machines(self.testClass.apiclient, id=vm.id)
        assert isinstance(migrated_vm_response, list), "Check list virtual machines response for valid list"

        assert migrated_vm_response[0].hostid == destinationHost.id, "VM did not migrate to a specified host"
    
        for vol in volumes:
            migrated_volume_response = list_volumes(
                self.testClass.apiclient,
                virtualmachineid=migrated_vm_response[0].id,
                name=vol.name,
                listall=True)
            assert isinstance(migrated_volume_response, list), "Check list virtual machines response for valid list"
            assert migrated_volume_response[0].storageid == pool.id, "Volume did not migrate to a specified pool"
    
            assert str(migrated_volume_response[0].state).lower().eq('ready'), "Check migrated volume is in Ready state"
    
            return migrated_vm_response[0]

    def getDestinationHost(self, hostsToavoid, hosts):
        destinationHost = None
        for host in hosts:
            if host.id not in hostsToavoid:
                destinationHost = host
                break
        return destinationHost

    def get_destination_pools_hosts(self, vm, hosts):
        vol_list = list_volumes(
            self.testClass.apiclient,
            virtualmachineid=vm.id,
            listall=True)
            # Get destination host
        destinationHost = self.getDestinationHost(vm.hostid, hosts)
        return destinationHost, vol_list

    def migrateVm(self, vm, destinationHost):
        """
        This method is to migrate a VM using migrate virtual machine API
        """
    
        vm.migrate(
            self.testClass.apiclient,
            hostid=destinationHost.id,
        )
        vm.getState(
            self.testClass.apiclient,
            "Running"
        )
        # check for the VM's host and volume's storage post migration
        migrated_vm_response = list_virtual_machines(self.testClass.apiclient, id=vm.id)
        assert isinstance(migrated_vm_response, list), "Check list virtual machines response for valid list"

        assert migrated_vm_response[0].hostid ==  destinationHost.id, "VM did not migrate to a specified host"
        return migrated_vm_response[0]

    def getDestinationPool(self,
                           poolsToavoid,
                           migrateto
                           ):
        """ Get destination pool which has scope same as migrateto
        and which is not in avoid set
        """
    
        destinationPool = None
    
        # Get Storage Pool Id to migrate to
        for storagePool in self.pools:
            if storagePool.scope == migrateto:
                if storagePool.name not in poolsToavoid:
                    destinationPool = storagePool
                    break
    
        return destinationPool



    def argument_parser(self, parser):
        #parser = argparse.ArgumentParser()
        default_dir = os.getcwd()

        parser.add_argument("-b", "--build",action='store',
                          help="build_cloudstack file. It has to be located in marvin directory of StorPool's plug-in",
                          default=os.path.join(default_dir, "marvin/build-cloudstack")
                          )
        parser.add_argument("-u", "--uuid",action='store',
                          help="Latest commit id that keeps the logic until globalId change"
                          )
        parser.add_argument("-e", "--cfg",action='store',
                          help="Environment configuration file for Marvin initialization",
                          default=os.path.join(default_dir, "marvin/env.cfg")
                          )
        parser.add_argument("-g", "--globalid",action='store',
                          help="The commit id that keeps changes for globalId"
                          )
        parser.add_argument("-d", "--directory",action='store',
                          help="Destination of local StorPool's plug-in repository ",
                          default=default_dir)
        parser.add_argument("-c", "--commit", action='store',
                          help="Commit id that has to be build")
        parser.add_argument("-f", "--forked", action='store',
                          help="Folder of CloudStack local repository. It has to be builded",
                          default= os.path.join(default_dir, "cloudstack")
                          )
        parser.add_argument("-r", "--remote",action='store',
                          help="Remote IP of first hypervisor"
                          )
        parser.add_argument("-s", "--second",action='store',
                          help="Remote IP of second hypervisor"
                          )
        parser.add_argument("-t", "--third",action='store',
                          help="Remote IP of third hypervisor",
                          default=""
                          )
        parser.add_argument("-a", "--fourth",action='store',
                          help="Remote IP of fourth hypervisor",
                          default=""
                          )
        
        parser.add_argument('unittest_args', nargs='*')
        args = parser.parse_args()
        cfg.logger.info(args)
        sys.argv[1:] = args.unittest_args
        cfg.logger.info(sys.argv[1:])
        return args

class TeeTextTestRunner(unittest.TextTestRunner):

    def __init__(self, verbosity, failfast, buffer):
        super(TeeTextTestRunner, self).__init__(
            stream=cfg.logstream,
            verbosity=2,
            failfast=failfast,
            buffer=buffer,
        )


