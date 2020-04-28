Prerequisites:
https://cwiki.apache.org/confluence/display/CLOUDSTACK/Marvin+-+Testing+with+Python

Environment setup:

create templates - "ssd" and "ssd2" on StorPool
create two StorPool's primary storages on CloudStack with names "ssd" and "ssd2" 

 
For the tests is used "system" VM template

command to run tests

nosetests --with-marvin  --marvin-config=/path/to/env.cfg /path/to/test --hypervisor=kvm

Multicluster tests information

<table cellpadding="5">
<tr>
  <th>Test Number</th>
  <th>Short description</th>
  <th>test_migration_from_nfs.py</th>
</tr>
<tr>
  <td>#1</td>
   <td>Test migrate virtual machine from NFS primary storage to StorPool</td>
  <td>test_1_migrate_vm_from_nfs_to_storpool</td>
</tr>
<tr>
  <td>#2</td>
  <td>Test migrate volume from NFS primary storage to StorPool</td>
  <td>test_2_migrate_volume_from_nfs_to_storpool</td>
</tr>
</table> 

<table cellpadding="5">
<tr>
  <th>Test Number</th>
  <th>Short description</th>
  <th>test_storpool_tags.py</th>
</tr>
<tr>
  <td>#1</td>
  <td>Test set vc_policy tag to VM with one attached disk</td>
  <td>test_01_set_vcpolicy_tag_to_vm_with_attached_disks</td>
</tr>
<tr>
  <td>#2</td>
  <td>Test set vc_policy tag to new disk attached to VM</td>
  <td>test_02_set_vcpolicy_tag_to_attached_disk</td>
</tr>
<tr>
  <td>#3</td>
  <td>Test tags of group snapshot</td>
  <td>test_03_create_vm_snapshot_vc_policy_tag</td>
</tr>
<tr>
  <td>#4</td>
  <td>Revert revert snapshot test tags</td>
  <td>test_04_revert_vm_snapshots_vc_policy_tag</td>
</tr>
<tr>
  <td>#5</td>
  <td>Tests delete vm snapshot - removing tags</td>
  <td>test_05_delete_vm_snapshots</td>
</tr>
<tr>
  <td>#6</td>
  <td>Test remove vc_policy tag to disk detached from VM</td>
  <td>test_06_remove_vcpolicy_tag_when_disk_detached</td>
</tr>
<tr>
  <td>#7</td>
  <td>Test delete vc_policy tag of VM</td>
  <td>test_07_delete_vcpolicy_tag</td>
</tr>
<tr>
  <td>#8</td>
  <td>Tests revert vm snapshot with vc policy tags</td>
  <td>test_08_vcpolicy_tag_to_reverted_disk</td>
</tr>
</table> 

<table cellpadding="5">
<tr>
  <th>Test Number</th>
  <th>Short description</th>
  <th>test_user_commands.py</th>
</tr>
<tr>
  <td>#1</td>
   <td>Test set vc_policy tag to VM with one attached disk with user rights</td>
  <td>test_01_set_vcpolicy_tag_to_vm_with_attached_disks</td>
</tr>
<tr>
  <td>#2</td>
  <td>Test create virtual machine with user rights</td>
  <td>test_02_create_vm_snapshot_by_user</td>
</tr>
<tr>
	<td>#3</td>
	<td>Revert vm snapshot with user rgihts for Virtual machine with VC policy tag</td>
	<td>test_03_revert_vm_snapshots_vc_policy_tag</td>
</tr>
<tr>
	<td>#5</td>
	<td>Tests set VC policy tag to VM with admin rights, <br/> and try to delete the tag with user rights account</td>
	<td>test_05_set_vcpolicy_tag_with_admin_and_try_delete_with_user</td>
</tr>
</table> 


<table cellpadding="5">
<tr>
  <th>Test Number</th>
  <th>Short description</th>
  <th>test_multicluster_bypass_secondary_storage.py</th>
</tr>
<tr>
  <td>#1</td>
   <td>Create template from snapshot without bypass secondary storage</td>
  <td>test_01_snapshot_to_template</td>
</tr>
<tr>
  <td>#2</td>
  <td>Test Create Template from snapshot bypassing secondary storage</td>
  <td>test_02_snapshot_to_template_bypass_secondary</td>
</tr>
<tr>
	<td>#3</td>
	<td>Test Create snapshot and backup to secondary</td>
	<td>test_03_snapshot_volume_with_secondary</td>
</tr>
<tr>
	<td>#4</td>
	<td>Test create snapshot from volume, bypassing secondary storage</td>
	<td>test_04_snapshot_volume_bypass_secondary</td>
</tr>
<tr>
	<td>#5</td>
	<td>Test delete template from snapshot bypassed secondary storage</td>
	<td>test_05_delete_template_bypassed_secondary</td>
</tr>
<tr>
	<td>#6</td>
	<td>Test create template bypassing secondary from snapshot <br/> which is backed up on secondary storage</td>
	<td>test_06_template_from_snapshot</td>
</tr>
<tr>
	<td>#7</td>
	<td>Delete snapshot and template if volume is already deleted, not bypassing secondary</td>
	<td>test_07_delete_snapshot_of_deleted_volume</td>
</tr>
<tr>
	<td>#8</td>
	<td>Delete snapshot and template if volume is already deleted, bypassing secondary</td>
	<td>test_08_delete_snapshot_of_deleted_volume</td>
</tr>
<tr>
	<td>#9</td>
	<td>Create virtual machine with sp.bypass.secondary.storage=false <br/>
        from template created on StorPool and Secondary Storage</td>
	<td>test_09_vm_from_bypassed_template</td>
</tr>
</table> 

<table cellpadding="5">
<tr>
  <th>Test Number</th>
  <th>Short description</th>
  <th>test_multicluster_on_local_cluster.py</th>
</tr>
<tr>
  <td>#1</td>
   <td>Test Attach Volume To Running Virtual Machine on local cluster</td>
  <td>test_01_attach_detach_volume_to_running_vm</td>
</tr>
<tr>
  <td>#2</td>
   <td>Test Resize Root volume on Running Virtual Machine on local cluster</td>
  <td>test_02_resize_root_volume_on_working_vm</td>
</tr>
<tr>
  <td>#3</td>
   <td>Test Resize Volume and attach To Running Virtual Machine on local cluster</td>
  <td>test_03_resize_attached_volume_on_working_vm</td>
</tr>
<tr>
  <td>#4</td>
   <td>Test Attach-detach Volume To Stopped Virtual Machine on local cluster</td>
  <td>test_04_attach_detach_volume_to_stopped_vm</td>
</tr>
<tr>
  <td>#5</td>
   <td>Test Resize Volume  Attached To Virtual Machine on local cluster</td>
  <td>test_05_resize_attached_volume</td>
</tr>
<tr>
  <td>#6</td>
   <td>Test Resize Volume Detached To Virtual Machine</td>
  <td>test_06_resize_detached_volume</td>
</tr>
<tr>
  <td>#7</td>
   <td>Create volume from snapshot</td>
  <td>test_07_snapshot_to_volume</td>
</tr>
<tr>
  <td>#8</td>
   <td>Snapshot detached volume</td>
  <td>test_08_snapshot_detached_volume</td>
</tr>
<tr>
  <td>#9</td>
   <td>Snapshot ROOT volume</td>
  <td>test_09_snapshot_root_disk</td>
</tr>
<tr>
  <td>#10</td>
   <td>Create Template From ROOT Volume</td>
  <td>test_10_volume_to_template</td>
</tr>
<tr>
  <td>#11</td>
   <td>Migrate VM to another StorPool's Primary Storage</td>
  <td>test_11_migrate_vm_to_another_storage</td>
</tr>
<tr>
  <td>#12</td>
   <td>Migrate Volume To Another StorPool's Primary Storage</td>
  <td>test_12_migrate_volume_to_another_storage</td>
</tr>
<tr>
  <td>#13</td>
   <td>Create Virtual Machine on another StorPool primary StoragePool</td>
  <td>test_13_create_vm_on_another_storpool_storage</td>
</tr>
<tr>
  <td>#14</td>
   <td>Create Virtual Machine On Working Cluster With Template Created on Another</td>
  <td>test_14_create_vm_on_second_cluster_with_template_from_first</td>
</tr>
<tr>
  <td>#15</td>
   <td>Create volume from snapshot</td>
  <td>test_15_snapshot_to_volume_of_root_disk</td>
</tr>
<tr>
  <td>#16</td>
   <td>Download volume</td>
  <td>test_16_download_volume</td>
</tr>
<tr>
  <td>#17</td>
   <td>Create virtual machine from template which for some reason is deleted from StorPool,<br/> but exists in template_spool_ref DB tables</td>
  <td>test_17_create_vm_from_template_not_on_storpool</td>
</tr>
</table>

<table cellpadding="5">
<tr>
  <th>Test Number</th>
  <th>Short description</th>
  <th>test_multicluster_on_remote_cluster.py</th>
</tr>
<tr>
	<td>#1</td>
	<td>Test Attach Volume To Running Virtual Machine</td>
	<td>test_01_start_vm_on_remote_cluster</td>
</tr>
<tr>
	<td>#2</td>
	<td>Test Attach Volume To Running Virtual Machine on remote</td>
	<td>test_02_attach_detach_volume_to_vm_on_remote</td>
</tr>
<tr>
	<td>#3</td>
	<td>Test Resize Root volume on Running Virtual Machine on remote</td>
	<td>test_03_resize_root_volume_of_vm_on_remote</td>
</tr>
	<td>#4</td>
	<td>Test Resize Volume  Attached To Running Virtual Machine on remote</td>
	<td>test_04_resize_attached_volume_of_vm_on_remote</td>
</tr>
<tr>
	<td>#5</td>
	<td>Snapshot root disk on running virtual machine on remotе</td>
	<td>test_05_snapshot_root_disk_working_vm_on_remote</td>
</tr>
<tr>
	<td>#6</td>
	<td>Create template from snapshot</td>
	<td>test_06_snapshot_to_template_secondary_storage</td>
</tr>
<tr>
	<td>#7</td>
	<td>Create template from snapshot bypassing secondary storage</td>
	<td>test_07_snapshot_to_template_bypass_secondary</td>
</tr>
<tr>
	<td>#8</td>
	<td>Create template from snapshot</td>
	<td>test_08_volume_to_template</td>
</tr>
<tr>
	<td>#9</td>
	<td>Test to create VM snapshots</td>		
	<td>test_09_create_vm_snapshots</td>
</tr>
<tr>
	<td>#10</td>
	<td>Test to revert VM snapshots</td>
	<td>test_10_revert_vm_snapshots</td>
</tr>
<tr>
	<td>#11</td>
	<td>Test to delete vm snapshots</td>
	<td>test_11_delete_vm_snapshots</td>
</tr>
</table>

<table cellpadding="5">
<tr>
  <th>Test Number</th>
  <th>Short description</th>
  <th>test_multicluster_vm_snapshot.py</th>
</tr>
<tr>
  <td>#1</td>
   <td>Test to create VM snapshots</td>
  <td>test_multicluster_vm_snapshot.py</td>
</tr>
<tr>
  <td>#2</td>
  <td>Test to revert VM snapshots</td>
  <td>test_02_revert_vm_snapshots</td>
</tr>
<tr>
  <td>#3</td>
  <td>Test to delete vm snapshots</td>
  <td>test_03_delete_vm_snapshots</td>
</tr>
</table>

Tests for migration from UUID names to names with globalId.

The COMMIT parameters has to accept the all commits until the change to globalId commit
the GLOBALID parameter has to accept commits relevant to commits after the change to globalId

Command to run tests:

usage: test_file_name.py [-h] [-b BUILD] [-u UUID] [-g GLOBALID] [-d DIRECTORY]
                       [-c COMMIT] [-f FORKED] [-r REMOTE] [-s SECOND]
                       [unittest_args [unittest_args ...]]

positional arguments:
  unittest_args

optional arguments:
  -h, --help            show this help message and exit
  -b BUILD, --build BUILD
                        build_cloudstack file. It has to be located in marvin
                        directory of StorPool's plug-in
  -u UUID, --uuid UUID  Latest commit id that keeps the logic until globalId
                        change
  -e CFG, --cfg CFG     Environment configuration file for Marvin
                        initialization
  -g GLOBALID, --globalid GLOBALID
                        The commit id that keeps changes for globalId
  -d DIRECTORY, --directory DIRECTORY
                        Destination of local StorPool's plug-in repository
                        information is specified
  -c COMMIT, --commit COMMIT
                        Commit id that has to be build
  -f FORKED, --forked FORKED
                        Folder of CloudStack local repository. It has to be
                        builded
  -r REMOTE, --remote REMOTE
                        Remote IP of first hypervisor
  -s SECOND, --second SECOND
                        Remote IP of second hypervisor
                        
example of command:

python test_file_name.py -b /dir/to/build-cloudstack -u 192f250d8e1d3692ecd6c4781ba87ecd352acde8 -g cddb136d35df5706a95b4f866dcbfdea4fa4ed3c -d /storpool/integration/dir/ -f /cloudstack/dir/ -s root@hv1.ip -r root@hv2.ip

<table cellpadding="5">
<tr>
  <th>Test Number</th>
  <th>Short description</th>
  <th>test_migration_uuid_to_globalid_volumes.py</th>
</tr>
<tr>
<td>#1</td>
<td>resize root volume created with uuid with virtual machine created with uuid</td>
<td>test_01_resize_root_volume</td>
</tr>
<tr>
<td>#2</td>
<td>resize attached volume created with uuid with virtual machine with uuid</td>
<td>test_02_resize_attached_volume_uuid</td>
</tr>
<tr>
<td>#3</td>
<td>resize attached volume created with globalid to virtual machine created with uuid</td>
<td>test_03_resize_attached_volume_globalid</td>
</tr>
<tr>
<td>#4</td>
<td>resize attached volume created with uuid with virtual machine with globalid</td>
<td>test_04_resize_volume_uuid_vm_glid</td>
</tr>
<tr>
<td>#5</td>
<td>resize detached volume created with uuid</td>
<td>test_05_resize_detached_vol_uuid</td>
</tr>
<tr>
<td>#6</td>
<td>resize detached volume created with globalid</td>
<td>test_06_resize_detach_vol_globalid</td>
</tr>
<tr>
<td>#7</td>
<td>attach-detach volume created with uuid to vm with uuid</td>
<td>test_07_attach_detach_vol_uuid</td>
</tr>
<tr>
<td>#8</td>
<td>attach-detach volume created with uuid to vm with globalid</td>
<td>test_08_attach_detach_vol_glId</td>
</tr>
<tr>
<td>#9</td>
<td>attach-detach volume with global id to vm with uuid</td>
<td>test_09_attach_detach_vol_glId</td>
</tr>
<tr>
<td>#10</td>
<td>attach-detach volume with global id to vm with globalid</td>
<td>test_10_attach_detach_instances_with_glId</td>
</tr>
<tr>
<td>#11</td>
<td>snapshot with uuid to volume</td>
<td>test_11_volume_from_snapshot_with_uuid</td>
</tr>
<tr>
<td>#12</td>
<td>snapshot detached volume with uuid</td>
<td>test_12_snapshot_detached_vol_with_uuid</td>
</tr>
<tr>
<td>#13</td>
<td>snapshot detached volume with globalid</td>
<td>test_13_snapshot_detached_vol_with_glid</td>
</tr>
<tr>
<td>#14</td>
<td>snapshot root disk for vm with uuid</td>
<td>test_14_snapshot_root_vol_with_uuid</td>
</tr>
<tr>
<td>#15</td>
<td>snapshot root disk for vm with globalid</td>
<td>test_15_snapshot_root_vol_glid</td>
</tr>
<tr>
<td>#16</td>
<td>volume with uuid to template</td>
<td>test_16_template_from_volume_with_uuid</td>
</tr>
<tr>
<td>#17</td>
<td>volume with global id to template</td>
<td>test_17_template_from_vol_glid</td>
</tr>
<tr>
<td>#18</td>
<td>snapshot on secondary with uuid to template on secondary</td>
<td>test_18_template_from_snapshot_uuid</td>
</tr>
<tr>
<td>#19</td>
<td>snapshot on secondary with uuid to template bypassed</td>
<td>test_19_template_from_snapshot_on_secondary_uuid</td>
</tr>
<tr>
<td>#20</td>
<td>snapshot bypassed with uuid to template bypassed</td>
<td>test_20_template_from_bypassed_snapshot_uuid</td>
</tr>
<tr>
<td>#21</td>
<td>snapshot with global id bypassed to template from volume with uuid bypass</td>
<td>test_21_template_from_snapshot_glid_bypassed</td>
</tr>
<tr>
<td>#22</td>
<td>snapshot with global id on secondary to template from volume with uuid bypass</td>
<td>test_22_template_from_snapshot_glid_on_secondary</td>
</tr>
<tr>
<td>#23</td>
<td>snapshot with global id on secondary to template from volume with uuid on secondary</td>
<td>test_23_template_from_snapshot_glid_on_secondary</td>
</tr>
</table>

<table cellpadding="5">
<tr>
  <th>Test Number</th>
  <th>Short description</th>
  <th>migrating_from_uuid_to_global_id.py</th>
</tr>
<tr>
<td>#1</td>
<td>Create vmsnapshot from virtual machine created with uuid</td>
<td>test_01_create_vm_snapshots_with_globalId</td>
</tr>
<tr>
<td>#2</td>
<td>Delete VM snapshot after revert of one vm snapshot</td>
<td>test_02_delete_vm_snapshot_between_reverts</td>
</tr>
<tr>
<td>#3</td>
<td>Revert few VM snapshots created with UUID and globalId</td>
<td>test_03_revert_vm_snapshot</td>
</tr>
<tr>
<td>#4</td>
<td> Create template from snapshot which is bypassed <br/>
            (snapshot - created with uuid template created with globalid)</td>
<td>test_04_create_and_delete_template_from_snapshot_bypassed</td>
</tr>
<tr>
<td>#5</td>
<td>Revert volume snapshot created with uuid</td>
<td>test_05_revert_delete_volume_snapshot</td>
</tr>
<tr>
<td>#6</td>
<td>Create Virtual machine with template on StorPool, created with uuid <br/>
            Bypass option set to true</td>
<td>test_06_create_vm_with_bypassed_template</td>
</tr>
<tr>
<td>#7</td>
<td>Create Virtual machine with template on secondary, <br/>
	created with uuid bypass option set to  false</td>
<td>test_07_create_vm_with_template_on_secondary</td>
</tr>
<tr>
<td>#8</td>
<td>Test Create virtual machine snapshot with attached disk created with globalid</td>
<td>test_8_create_vm_snpashot</td>
</tr>
</table>

