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
import random
import time

from marvin.cloudstackAPI import (listTemplates, deleteSnapshot, deleteVolume, destroyVirtualMachine, deleteTemplate)
from marvin.cloudstackTestCase import cloudstackTestCase
from marvin.codes import FAILED, KVM, PASS, XEN_SERVER, RUNNING
from marvin.lib.base import (Account,
                             ServiceOffering,
                             VirtualMachine,
                             VmSnapshot,
                             Snapshot,
                             User,
                             Volume,Template
                             )
from marvin.lib.common import (get_zone,
                               get_domain,
                               get_template,
                               list_clusters,
                               list_snapshots,
                               list_virtual_machines,
                               list_configurations,
                               list_disk_offering,
                               list_accounts,
                               list_storage_pools,
                               list_service_offering,
                               list_volumes,
                               list_templates)
from marvin.lib.utils import random_gen, cleanup_resources, validateList, is_snapshot_on_nfs, isAlmostEqual, get_hypervisor_type
from nose.plugins.attrib import attr


class TestVmSnapshot(cloudstackTestCase):

    @classmethod
    def setUpClass(cls):
        testClient = super(TestVmSnapshot, cls).getClsTestClient()
        cls.apiclient = testClient.getApiClient()
        cls._cleanup = []
        cls.unsupportedHypervisor = False

        cls.services = testClient.getParsedTestDataConfig()
        # Get Zone, Domain and templates
        cls.domain = get_domain(cls.apiclient)
        cls.zone = get_zone(cls.apiclient, testClient.getZoneForTests())
        cls.cluster = list_clusters(cls.apiclient)[0]
        cls.hypervisor = get_hypervisor_type(cls.apiclient)
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

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_01_delete_all_virtual_machines(self):
        """Test to delete VMs
        """
        virtual_machines = list_virtual_machines(self.apiclient)
        for v in virtual_machines:
            try:
                cmd = destroyVirtualMachine.destroyVirtualMachineCmd()
                cmd.id = v.id
                cmd.expunge = True
                self.apiclient.destroyVirtualMachine(cmd)
            except Exception as e:
                continue
     

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_02_delete_all_snapshots(self):
        """Test to delete snapshots
        """
        snapshots = list_snapshots(self.apiclient)
        if snapshots is not None:
            for s in snapshots:
                try:
                    if s.state == 'BackedUp':
                        cmd = deleteSnapshot.deleteSnapshotCmd()
                        cmd.id = s.id
                        self.apiclient.deleteSnapshot(cmd)
                except Exception as e:
                    continue

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_03_delete_all_datadisks(self):
        """Test to delete volumes
        """
        volumes = list_volumes(self.apiclient, listall = True)
        for s in volumes:
            try:
                if s.virtualmachineid is None:
                    cmd = deleteVolume.deleteVolumeCmd()
                    cmd.id = s.id
                    self.apiclient.deleteVolume(cmd)
            except Exception as e:
                continue

    @attr(tags=["advanced", "advancedns", "smoke"], required_hardware="true")
    def test_04_delete_all_templates(self):
        templates = list_templates(self.apiclient, templatefilter='featured')
        for t in templates:
            if t.name.startswith("StorPool"):
                try:
                    cmd = deleteTemplate.deleteTemplateCmd()
                    cmd.id = t.id
                    self.apiclient.deleteTemplate(cmd)
                except Exception as e:
                    continue