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

class MigrationUuidToGlobalIdLiveMigration(unittest.TestCase): 
    ARGS = ""
    vm = ""
    vm2 = ""
    data_disk_1 = ""
    data_disk_2 = ""
    @classmethod
    def setUpClass(cls):
        super(MigrationUuidToGlobalIdLiveMigration, cls).setUpClass()
        try:
            cls.setUpCloudStack()
        except Exception:
            cls.cleanUpCloudStack()
            raise

    @classmethod
    def setUpCloudStack(cls):
        super(MigrationUuidToGlobalIdLiveMigration, cls).setUpClass()
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

        disk_offering_20 = list_disk_offering(
            cls.apiclient,
            name="Medium"
            )

        cls.disk_offering_20 = disk_offering_20[0]

        account = list_accounts(
            cls.apiclient,
            name="admin"
            )
        cls.account = account[0]

        cls.local_cluster = cls.helper.get_local_cluster()
        cls.host = cls.helper.list_hosts_by_cluster_id(cls.local_cluster.id)

        assert len(cls.host) > 1, "Hosts list is less than 1"
        cls.host_on_local_1 = cls.host[0]
        cls.host_on_local_2 = cls.host[1]

        cls.remote_cluster = cls.helper.get_remote_cluster()
        cls.host_remote = cls.helper.list_hosts_by_cluster_id(cls.remote_cluster.id)
        assert len(cls.host_remote) > 1, "Hosts list is less than 1"

        cls.host_on_remote1 = cls.host_remote[0]
        cls.host_on_remote2 = cls.host_remote[1]

        cls.virtual_machine = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=cls.template.id,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            hostid = cls.host_on_local_1.id,
            rootdisksize=10
        )
        cls._cleanup.append(cls.virtual_machine)   

        cls.volume = Volume.create(
            cls.apiclient,
            cls.testdata[TestData.volume_1],
            account=cls.account.name,
            domainid=cls.domain.id,
            zoneid=cls.zone.id,
            diskofferingid=cls.disk_offering.id
        )
        cls._cleanup.append(cls.volume)

        #vm and volume on remote
        cls.virtual_machine_remote = VirtualMachine.create(
            cls.apiclient,
            {"name":"StorPool-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=cls.template.id,
            serviceofferingid=cls.service_offering.id,
            hypervisor=cls.hypervisor,
            hostid = cls.host_on_remote1.id,
            rootdisksize=10
        )
        cls._cleanup.append(cls.virtual_machine_remote) 

        cls.volume_remote = Volume.create(
            cls.apiclient,
            cls.testdata[TestData.volume_1],
            account=cls.account.name,
            domainid=cls.domain.id,
            zoneid=cls.zone.id,
            diskofferingid=cls.disk_offering.id
        )
        cls._cleanup.append(cls.volume_remote)
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


    def test_01_migrate_vm_live_on_local(self):
        global vm

        # Get destination host
        destinationHost = self.helper.getDestinationHost(self.virtual_machine.hostid, self.host)
        # Migrate the VM
        vm = self.helper.migrateVm(self.virtual_machine, destinationHost)

        destinationHost,  vol_list = self.helper.get_destination_pools_hosts(vm, self.host)
        vm = self.helper.migrateVm(self.virtual_machine, destinationHost)

    def test_02_migrate_vm_live_attach_disk_on_local(self):
        global vm
        global data_disk_1

        data_disk_1 = Volume.create(
            self.apiclient,
            {"diskname":"StorPoolDisk-4" },
            zoneid=self.zone.id,
            diskofferingid=self.disk_offering.id,
        )

        cfg.logger.info("Created volume with ID: %s" % data_disk_1.id)

        self.virtual_machine.attach_volume(
            self.apiclient,
            data_disk_1
        )

#         vm = list_virtual_machines(self.apiclient, id=self.virtual_machine.id)
#         vm = vm[0]

        destinationHost, vol_list = self.helper.get_destination_pools_hosts(vm, self.host)
        vm = self.helper.migrateVm(self.virtual_machine, destinationHost)


        self.virtual_machine.attach_volume(
            self.apiclient,
            self.volume
        )

        destinationHost, vol_list = self.helper.get_destination_pools_hosts(vm, self.host)
        vm = self.helper.migrateVm(self.virtual_machine, destinationHost)

    def test_03_migrate_vm_live_with_snapshots_on_local(self):
        """
        Create snapshots on all the volumes, Migrate all the volumes and VM.
        """
        global vm
#         vm = list_virtual_machines(self.apiclient, id=self.virtual_machine.id)
#         vm = vm[0]
        vol_for_snap = list_volumes(
            self.apiclient,
            virtualmachineid=vm.id,
            listall=True)
        for vol in vol_for_snap:
            snapshot = Snapshot.create(
                self.apiclient,
                volume_id=vol.id
            )
            snapshot.validateState(
                self.apiclient,
                snapshotstate="backedup",
            )
        # Migrate all volumes and VMs

        destinationHost, vol_list = self.helper.get_destination_pools_hosts(vm, self.host)
        vm = self.helper.migrateVm(self.virtual_machine, destinationHost)


    def test_04_migrate_vm_live_resize_volume_on_local(self):
        """
        Resize the data volume , Migrate all the volumes and VM.
        """
        global vm
        global data_disk_1
#         vm = list_virtual_machines(self.apiclient, id=self.virtual_machine.id)
#         vm = vm[0]
        data_disk_1.resize(
            self.apiclient,
            diskofferingid=self.disk_offering_20.id
        )
        # Migrate all volumes and VMs
        destinationHost,  vol_list = self.helper.get_destination_pools_hosts(vm, self.host)
        vm = self.helper.migrateVm(self.virtual_machine, destinationHost)

    def test_05_migrate_vm_live_restore_on_local(self):
        """
        Restore the VM , Migrate all the volumes and VM.
        """
        global vm
#         vm = list_virtual_machines(self.apiclient, id=self.virtual_machine.id)
#         vm = vm[0]
        self.virtual_machine.restore(self.apiclient)
        self.virtual_machine.getState(
            self.apiclient,
            "Running"
        )
        # Migrate the VM and its volumes

        destinationHost, vol_list = self.helper.get_destination_pools_hosts(vm, self.host)
        vm = self.helper.migrateVm(self.virtual_machine, destinationHost)

    def test_06_migrate_vm_live_on_remote(self):
        global vm2

        # Get destination host
        destinationHost = self.helper.getDestinationHost(self.virtual_machine_remote.hostid, self.host_remote)
        # Migrate the VM
        vm2 = self.helper.migrateVm(self.virtual_machine_remote, destinationHost)

        destinationHost,  vol_list = self.helper.get_destination_pools_hosts(vm2, self.host_remote)
        vm2 = self.helper.migrateVm(self.virtual_machine_remote, destinationHost)

    def test_07_migrate_vm_live_attach_disk_on_remote(self):
        global vm2
        global data_disk_2

        data_disk_2 = Volume.create(
            self.apiclient,
            {"diskname":"StorPoolDisk-4" },
            zoneid=self.zone.id,
            diskofferingid=self.disk_offering.id,
        )

        cfg.logger.info("Created volume with ID: %s" % data_disk_2.id)

        self.virtual_machine_remote.attach_volume(
            self.apiclient,
            data_disk_2
        )

        destinationHost, vol_list = self.helper.get_destination_pools_hosts(vm2, self.host_remote)
        vm2 = self.helper.migrateVm(self.virtual_machine_remote, destinationHost)


        self.virtual_machine_remote.attach_volume(
            self.apiclient,
            self.volume_remote
        )

        destinationHost, vol_list = self.helper.get_destination_pools_hosts(vm2, self.host_remote)
        vm2 = self.helper.migrateVm(self.virtual_machine_remote, destinationHost)

    def test_08_migrate_vm_live_with_snapshots_on_remote(self):
        """
        Create snapshots on all the volumes, Migrate all the volumes and VM.
        """
        global vm2
#         vm = list_virtual_machines(self.apiclient, id=self.virtual_machine.id)
#         vm = vm[0]
        vol_for_snap = list_volumes(
            self.apiclient,
            virtualmachineid=vm2.id,
            listall=True)
        for vol in vol_for_snap:
            snapshot = Snapshot.create(
                self.apiclient,
                volume_id=vol.id
            )
            snapshot.validateState(
                self.apiclient,
                snapshotstate="backedup",
            )
        # Migrate all volumes and VMs

        destinationHost, vol_list = self.helper.get_destination_pools_hosts(vm2, self.host_remote)
        vm2 = self.helper.migrateVm(self.virtual_machine_remote, destinationHost)


    def test_09_migrate_vm_live_resize_volume_on_remote(self):
        """
        Resize the data volume , Migrate all the volumes and VM.
        """
        global vm2
        global data_disk_2
#         vm = list_virtual_machines(self.apiclient, id=self.virtual_machine.id)
#         vm = vm[0]
        data_disk_2.resize(
            self.apiclient,
            diskofferingid=self.disk_offering_20.id
        )
        # Migrate all volumes and VMs
        destinationHost,  vol_list = self.helper.get_destination_pools_hosts(vm2, self.host_remote)
        vm2 = self.helper.migrateVm(self.virtual_machine_remote, destinationHost)

    def test_10_migrate_vm_live_restore_on_remote(self):
        """
        Restore the VM , Migrate all the volumes and VM.
        """
        global vm2
#         vm = list_virtual_machines(self.apiclient, id=self.virtual_machine.id)
#         vm = vm[0]
        self.virtual_machine_remote.restore(self.apiclient)
        self.virtual_machine_remote.getState(
            self.apiclient,
            "Running"
        )
        # Migrate the VM and its volumes

        destinationHost, vol_list = self.helper.get_destination_pools_hosts(vm2, self.host_remote)
        vm2 = self.helper.migrateVm(self.virtual_machine_remote, destinationHost)

def main():
    original = (sys.stdout, sys.stderr)
    try:
        helper = HelperUtil()
        parser = argparse.ArgumentParser()
        MigrationUuidToGlobalIdLiveMigration.ARGS = helper.argument_parser(parser)
        cfg.logger.info("Arguments  %s", MigrationUuidToGlobalIdLiveMigration.ARGS)         

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
