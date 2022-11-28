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
import pprint
import random
import subprocess
import time
import uuid

from marvin.cloudstackAPI import (listOsTypes,
                                  listTemplates,
                                  listHosts,
                                  createTemplate,
                                  createVolume,
                                  resizeVolume,
                                  startVirtualMachine,
                                  migrateVirtualMachine,
                                  migrateVolume,
                                  listClusters,
                                  listConfigurations
                                  )
from marvin.cloudstackTestCase import cloudstackTestCase
from marvin.codes import FAILED, KVM, PASS, XEN_SERVER, RUNNING
from marvin.configGenerator import configuration, cluster
from marvin.lib.base import (Account,
                             Configurations,
                             ServiceOffering,
                             Snapshot,
                             StoragePool,
                             Template,
                             Tag,
                             VirtualMachine,
                             VmSnapshot,
                             Volume,
                             SecurityGroup,
                             DiskOffering,
                             )
from marvin.lib.common import (get_zone,
                               get_domain,
                               get_template,
                               list_disk_offering,
                               list_snapshots,
                               list_storage_pools,
                               list_volumes,
                               list_virtual_machines,
                               list_configurations,
                               list_service_offering,
                               list_clusters,
                               list_zones)
from marvin.lib.utils import random_gen, cleanup_resources, validateList, is_snapshot_on_nfs, isAlmostEqual
from nose.plugins.attrib import attr

from storpool import spapi
from sp_util import (TestData, StorPoolHelper)


class TestMigrateVMWithVolumes(cloudstackTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestMigrateVMWithVolumes, cls).setUpClass()
        try:
            cls.setUpCloudStack()
        except Exception:
            cls.cleanUpCloudStack()
            raise

    @classmethod
    def setUpCloudStack(cls):
        cls.spapi = spapi.Api.fromConfig(multiCluster=True)
        testClient = super(TestMigrateVMWithVolumes, cls).getClsTestClient()
        cls.apiclient = testClient.getApiClient()

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

        td = TestData()
        cls.testdata = td.testdata
        cls.helper = StorPoolHelper()
        StorPoolHelper.logger = cls
        cls.logger = StorPoolHelper.logger

        storpool_primary_storage = cls.testdata[TestData.primaryStorage]
        cls.template_name = storpool_primary_storage.get("name")
        storpool_service_offerings = cls.testdata[TestData.serviceOffering]

        nfs_service_offerings = cls.testdata[TestData.serviceOfferingsPrimary]
        ceph_service_offerings = cls.testdata[TestData.serviceOfferingsCeph]

        nfs_disk_offerings = cls.testdata[TestData.nfsDiskOffering]
        ceph_disk_offerings = cls.testdata[TestData.cephDiskOffering]

        storage_pool = list_storage_pools(
            cls.apiclient,
            name=cls.template_name
            )

        nfs_storage_pool = list_storage_pools(
            cls.apiclient,
            name='primary'
            )

        ceph_primary_storage = cls.testdata[TestData.primaryStorage4]

        cls.ceph_storage_pool = list_storage_pools(
            cls.apiclient,
            name=ceph_primary_storage.get("name")
            )[0]

        ceph_cluster = cls.testdata[TestData.primaryStorage5]

        cls.ceph_cluster_wide = list_storage_pools(
            cls.apiclient,
            name=ceph_cluster.get("name")
            )[0]

        nfs_cluster = cls.testdata[TestData.primaryStorage6]

        cls.nfs_cluster_wide = list_storage_pools(
            cls.apiclient,
            name=nfs_cluster.get("name")
            )[0]

        service_offerings = list_service_offering(
            cls.apiclient,
            name=cls.template_name
            )
        nfs_service_offering = list_service_offering(
            cls.apiclient,
            name='nfs'
            )

        ceph_service_offering = list_service_offering(
            cls.apiclient,
            name=ceph_primary_storage.get("name")
            )

        ceph_cluster_service_offering = list_service_offering(
            cls.apiclient,
            name=ceph_cluster.get("name")
            )[0]

        nfs_cluster_service_offering = list_service_offering(
            cls.apiclient,
            name=nfs_cluster.get("name")
            )[0]

        if storage_pool is None:
            storage_pool = StoragePool.create(cls.apiclient, storpool_primary_storage)
        else:
            storage_pool = storage_pool[0]
        cls.storage_pool = storage_pool
        cls.debug(pprint.pformat(storage_pool))
        if service_offerings is None:
            service_offerings = ServiceOffering.create(cls.apiclient, storpool_service_offerings)
        else:
            service_offerings = service_offerings[0]
        if nfs_service_offering is None:
            nfs_service_offering = ServiceOffering.create(cls.apiclient, nfs_service_offerings)
        else:
            nfs_service_offering = nfs_service_offering[0]

        if ceph_service_offering is None:
            ceph_service_offering = ServiceOffering.create(cls.apiclient, ceph_service_offerings)
        else:
            ceph_service_offering = ceph_service_offering[0]

        nfs_disk_offering = list_disk_offering(
            cls.apiclient,
            name="nfs"
            )
        if nfs_disk_offering is None:
            nfs_disk_offering = DiskOffering.create(cls.apiclient, nfs_disk_offerings)
        else:
            cls.nfs_disk_offering = nfs_disk_offering[0]

        ceph_disk_offering = list_disk_offering(
            cls.apiclient,
            name="ceph"
            )

        ceph_cluster_disk_offering = list_disk_offering(
            cls.apiclient,
            name=ceph_cluster.get("name")
            )[0]

        nfs_cluster_disk_offering = list_disk_offering(
            cls.apiclient,
            name=nfs_cluster.get("name")
            )[0]
        if ceph_disk_offering is None:
            cls.ceph_disk_offering = DiskOffering.create(cls.apiclient, ceph_disk_offerings)
        else:
            cls.ceph_disk_offering = ceph_disk_offering[0]

        template = get_template(
             cls.apiclient,
            cls.zone.id,
            account = "system"
        )

        cls.nfs_storage_pool = nfs_storage_pool[0]
        if cls.nfs_storage_pool.state == "Maintenance":
            cls.nfs_storage_pool = StoragePool.cancelMaintenance(cls.apiclient, cls.nfs_storage_pool.id)

        if cls.ceph_storage_pool.state == "Maintenance":
            cls.ceph_storage_pool = StoragePool.cancelMaintenance(cls.apiclient, cls.ceph_storage_pool.id)

        if cls.nfs_cluster_wide.state == "Maintenance":
            cls.nfs_cluster_wide = StoragePool.cancelMaintenance(cls.apiclient, cls.nfs_cluster_wide.id)

        if cls.ceph_cluster_wide.state == "Maintenance":
            cls.ceph_cluster_wide = StoragePool.cancelMaintenance(cls.apiclient, cls.ceph_cluster_wide.id)

        cls.account = cls.helper.create_account(
                            cls.apiclient,
                            cls.services["account"],
                            accounttype = 1,
                            domainid=cls.domain.id,
                            roleid = 1
                            )
        cls._cleanup.append(cls.account)

        securitygroup = SecurityGroup.list(cls.apiclient, account = cls.account.name, domainid= cls.account.domainid)[0]
        cls.helper.set_securityGroups(cls.apiclient, account = cls.account.name, domainid= cls.account.domainid, id = securitygroup.id)

        cls.clusters = cls.helper.getClustersWithStorPool(cls.apiclient, cls.zone.id,)

        cls.vm = VirtualMachine.create(cls.apiclient,
            {"name":"NFS-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            clusterid = cls.clusters[0],
            templateid=template.id,
            accountid=cls.account.name,
            domainid=cls.account.domainid,
            serviceofferingid=nfs_service_offering.id,
            diskofferingid=cls.nfs_disk_offering.id,
            hypervisor=cls.hypervisor,
            rootdisksize=10
            )

        cls.vm2 = VirtualMachine.create(cls.apiclient,
            {"name":"Ceph-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            clusterid=cls.clusters[0],
            templateid=template.id,
            accountid=cls.account.name,
            domainid=cls.account.domainid,
            serviceofferingid=ceph_service_offering.id,
            diskofferingid=cls.ceph_disk_offering.id,
            hypervisor=cls.hypervisor,
            rootdisksize=10
            )

        cls.vm3 = VirtualMachine.create(cls.apiclient,
            {"name":"CephCluster-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
            accountid=cls.account.name,
            domainid=cls.account.domainid,
            serviceofferingid=ceph_cluster_service_offering.id,
            diskofferingid=ceph_cluster_disk_offering.id,
            hypervisor=cls.hypervisor,
            rootdisksize=10,
            size=5
            )

        cls.vm4 = VirtualMachine.create(cls.apiclient,
            {"name":"NFSCluster-%s" % uuid.uuid4() },
            zoneid=cls.zone.id,
            templateid=template.id,
            accountid=cls.account.name,
            domainid=cls.account.domainid,
            serviceofferingid=nfs_cluster_service_offering.id,
            diskofferingid=nfs_cluster_disk_offering.id,
            hypervisor=cls.hypervisor,
            rootdisksize=10,
            size=5
            )
        cls.debug(pprint.pformat(template))
        cls.debug(pprint.pformat(cls.hypervisor))

        if template == FAILED:
            assert False, "get_template() failed to return template\
                    with description %s" % cls.services["ostype"]

        cls.services["domainid"] = cls.domain.id
        cls.services["small"]["zoneid"] = cls.zone.id
        cls.services["templates"]["ostypeid"] = template.ostypeid
        cls.services["zoneid"] = cls.zone.id


        cls.service_offering = service_offerings
        cls.nfs_service_offering = nfs_service_offering
        cls.debug(pprint.pformat(cls.service_offering))


        cls.template = template
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
            if cls.nfs_storage_pool.state is not "Maintenance":
                cls.nfs_storage_pool = StoragePool.enableMaintenance(cls.apiclient, cls.nfs_storage_pool.id)

            if cls.ceph_storage_pool.state is not "Maintenance":
                cls.ceph_storage_pool = StoragePool.enableMaintenance(cls.apiclient, cls.ceph_storage_pool.id)

            if cls.nfs_cluster_wide.state is not "Maintenance":
                cls.nfs_cluster_wide = StoragePool.enableMaintenance(cls.apiclient, cls.nfs_cluster_wide.id)

            if cls.ceph_cluster_wide.state is not "Maintenance":
                cls.ceph_cluster_wide = StoragePool.enableMaintenance(cls.apiclient, cls.ceph_cluster_wide.id)
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

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_01_migrate_vm_from_nfs_to_storpool_live(self):
        """
        Migrate VMs/Volumes live
        """
        self.storage_pool = StoragePool.update(self.apiclient,
                                              id=self.storage_pool.id,
                                              tags = ["ssd, nfs"])
        random_data = self.writeToFile(self.vm)
        cmd = listHosts.listHostsCmd()
        cmd.type = "Routing"
        cmd.state = "Up"
        cmd.zoneid= self.zone.id
        hosts = self.apiclient.listHosts(cmd)
        destinationHost = self.helper.getHostToDeployOrMigrate(self.apiclient, self.vm.hostid, self.clusters)
        vol_pool_map = {}
        volumes = list_volumes(
            self.apiclient,
            virtualmachineid=self.vm.id,
            listall=True)
        for v in volumes:
            vol_pool_map[v.id] = self.storage_pool.id

        # Migrate the VM
        print(vol_pool_map)
        vm = self.vm.migrate_vm_with_volume(self.apiclient, hostid = destinationHost.id, migrateto = vol_pool_map)
        self.checkFileAndContentExists(self.vm, random_data)

        self.storage_pool = StoragePool.update(self.apiclient,
                                              id=self.storage_pool.id,
                                              tags = ["ssd"])

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_02_migrate_vm_from_ceph_to_storpool_live(self):
        """
        Migrate VMs/Volumes live
        """
        self.storage_pool = StoragePool.update(self.apiclient,
                                              id=self.storage_pool.id,
                                              tags = ["ssd, ceph"])
        random_data = self.writeToFile(self.vm2)
        cmd = listHosts.listHostsCmd()
        cmd.type = "Routing"
        cmd.state = "Up"
        cmd.zoneid= self.zone.id
        hosts = self.apiclient.listHosts(cmd)
        destinationHost = self.helper.getHostToDeployOrMigrate(self.apiclient, self.vm2.hostid, self.clusters)
        vol_pool_map = {}
        volumes = list_volumes(
            self.apiclient,
            virtualmachineid=self.vm2.id,
            listall=True)
        for v in volumes:
            vol_pool_map[v.id] = self.storage_pool.id

        # Migrate the vm2
        print(vol_pool_map)
        vm2 = self.vm2.migrate_vm_with_volume(self.apiclient, hostid = destinationHost.id, migrateto = vol_pool_map)
        self.checkFileAndContentExists(self.vm2, random_data)

        self.storage_pool = StoragePool.update(self.apiclient,
                                              id=self.storage_pool.id,
                                              tags = ["ssd"])

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_03_live_migrate_nfs_sp(self):
        """
        Live migration with storage
        NFS - cluster-wide with no StorPool on the host to StorPool - Partial zone-wide
        """
        random_data = self.writeToFile(self.vm3)

        destinationHost = self.getHostOnClusterForMigrate(self.vm3.hostid)
        vol_pool_map = {}
        volumes = list_volumes(
            self.apiclient,
            virtualmachineid=self.vm3.id,
            listall=True)
        for v in volumes:
            vol_pool_map[v.id] = self.storage_pool.id

        # Migrate the vm2
        print(vol_pool_map)
        vm3 = self.vm3.migrate_vm_with_volume(self.apiclient, hostid=destinationHost.id, migrateto=vol_pool_map)
        self.checkFileAndContentExists(self.vm3, random_data)

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_04_live_migrate_ceph_sp(self):
        """
        Live migration with storage
        Ceph - cluster-wide with no StorPool on the host to StorPool - Partial zone-wide
        """
        random_data = self.writeToFile(self.vm4)

        destinationHost = self.getHostOnClusterForMigrate(self.vm4.hostid)
        vol_pool_map = {}
        volumes = list_volumes(
            self.apiclient,
            virtualmachineid=self.vm4.id,
            listall=True)
        for v in volumes:
            vol_pool_map[v.id] = self.storage_pool.id

        # Migrate the vm2
        print(vol_pool_map)
        vm4 = self.vm4.migrate_vm_with_volume(self.apiclient, hostid=destinationHost.id, migrateto=vol_pool_map)
        self.checkFileAndContentExists(self.vm4, random_data)

    def getHostOnClusterForMigrate(self, hostid):
        cmd = listClusters.listClustersCmd()
        cmd.zoneid = self.zone.id
        cmd.allocationstate = "Enabled"
        clusters = self.apiclient.listClusters(cmd)

        hosts_cmd = listHosts.listHostsCmd()
        hosts_cmd.zoneid = self.zone.id
        hosts_cmd.type = 'Routing'
        hosts = self.apiclient.listHosts(hosts_cmd)

        for host in hosts:
            self.logger.debug(host.id)
            self.logger.debug(hostid)
            self.logger.debug(clusters)
            self.logger.debug(host.clusterid)

            if host.id is None:
                continue
            if host.id in hostid:
                continue
            for cluster in clusters:
                if host.clusterid not in cluster.id:
                    return host

        return None

    def writeToFile(self, vm):
        random_data_0 = random_gen(size=100)
        try:
            # Login to VM and write data to file system
            ssh_client = vm.get_ssh_client(reconnect = True)

            cmds = [
                "echo %s > %s/%s" %
                (random_data_0, self.test_dir, self.random_data),
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
                      vm.ipaddress)
        self.assertEqual(
            random_data_0,
            result[0],
            "Check the random data has be write into temp file!"
        )
        return random_data_0

    def checkFileAndContentExists(self, vm, random_data_0):
        try:
            ssh_client = vm.get_ssh_client(reconnect=True)

            cmds = [
                "cat %s/%s" % (self.test_dir, self.random_data)
            ]

            for c in cmds:
                self.debug(c)
                result = ssh_client.execute(c)
                self.debug(result)

        except Exception as err:
            self.fail("SSH failed for Virtual machine: %s" %
                      err)

        self.assertEqual(
            random_data_0,
            result[0],
            "Check the random data is equal with the ramdom file!"
        )

