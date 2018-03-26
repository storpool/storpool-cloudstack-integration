# StorPool CloudStack Integration

## CloudStack Overview

### Primary and Secondary storage

Primary storage is associated with a cluster or zone, and it stores the virtual disks for all the VMs running on hosts in that cluster/zone.

Secondary storage stores the following:
* Templates — OS images that can be used to boot VMs and can include additional configuration information, such as installed applications
* ISO images — disc images containing data or bootable media for operating systems
* Disk volume snapshots — saved copies of VM data which can be used for data recovery or to create new templates


### ROOT and DATA volumes:

ROOT volumes correspond to the boot disk of a VM. They are created automatically by CloudStack during VM creation.
ROOT volumes are created based on a system disk offering, corresponding to the service offering the user VM
is based on. We may change the ROOT volume disk offering but only to another system created disk offering.

DATA volumes correspond to additional disks. These can be created by usera and then attached/detached to VMs.
DATA volumes are created based on a user-defined disk offering.


### Useful links (the information in some of these is outdated, so check the source to be sure):

* http://docs.cloudstack.apache.org/en/latest/concepts.html
* https://cwiki.apache.org/confluence/display/CLOUDSTACK/Storage+subsystem+2.0
* http://docs.cloudstack.apache.org/en/latest/plugins.html
* http://docs.cloudstack.apache.org/en/latest/developer_guide.html
* https://cwiki.apache.org/confluence/display/CLOUDSTACK/Development+101
* http://cloudstack.apache.org/api.html


## Plugin Organization

The StorPool plugin consists of two parts:

### KVM hypervisor plugin patch:

Source directory: ./apache-cloudstack-4.8.0-src/plugins/hypervisors/kvm

This is due to a bug in com.cloud.hypervisor.kvm.storage.IscsiAdmStorageAdaptor:disconnectPhysicalDiskByPath().
Otherwise may have dangling attachments. This fix should be pushed upstream to CloudStack.
It is a one line patch: return false in place of true, as the device in question is not iSCSI, thus it is not
disconnected (detached) by the iSCSI adaptor.

NB! We need to build and install our own copy of the CloudStack KVM hypervisor plugin on each Agent host.


### StorPool primary storage plugin:

Source directory: ./apache-cloudstack-4.8.0-src/plugins/storage/volume

There is one plugin for both the CloudStack management and agents, in the hope that having all the source
in one place will ease development and maintanance. The plugin itself though is separated into two mainly
independent parts:

  * ./src/com/... directory tree: agent related classes and commands send from management to agent
  * ./src/org/... directory tree: management related classes

The plugin is intented to be self contained and non-intrusive, thus ideally deploying it would consist of only
dropping the jar file into the appropriate places. This is the reason why all StorPool related communication
brx. the CloudStack management and agents (ex. data copying, volume resize) is done with StorPool specific
commands even when there is a CloudStack command that does pretty much the same.


## Build, Install, Setup

### Build: go to the source directory and run: mvn -Pdeveloper -DskipTests install

The resulting jar file is located in the target/ subdirectory.

Note: checkstyle errors: before compilation a code style check is performed; if this fails compilation is aborted.
In short: no trailing whitespace, indent using 4 spaces, not tabs, comment-out or remove unused imports.

Note: Need to build both the kvm plugin and the StorPool plugin proper.


### Install

#### KVM hypervisor plugin:

For each CloudStack  agent: scp ./target/cloud-plugin-hypervisor-kvm-4.8.0.jar {AGENT_HOST}:/usr/share/cloudstack-agent/lib/

#### StorPool primary storage plugin:

For each CloudStack agent: scp ./target/cloud-plugin-storage-volume-storpool-4.8.0.jar {AGENT_HOST}:/usr/share/cloudstack-agent/lib/
For each CloudStack management: scp ./target/cloud-plugin-storage-volume-storpool-4.8.0.jar {MGMT_HOST}:/usr/share/cloudstack-management/webapps/client/WEB-INF/lib

Note: Agents should have access to StorPool mgmt, since attach/detach happens on the agent. This is CloudStack design issue, can't do much about it.


### Setup

#### Setting up StorPool:

The usual StorPool setup.

Create a template to be used by CloudStack. Must set placeAll, placeTail and replication.
No need to set default size, as volume size is determined by CloudStack during creation.

#### Setting up a StorPool PRIMARY storage pool in CloudStack:

From the WEB UI, go to Infrastructure -> Primary Storage -> Add Primary Storage

Scope: select Zone-Wide
Hypervisor: select KVM
Zone: pick appropriate zone.
Name: user specified name

Protocol: select SharedMountPoint
Path: enter /dev/storpool (required argument, actually not needed in practice).

Provider: select StorPool
Managed: leave unchecked (currently ignored)
Capacity Bytes: used for accounting purposes only. May be more or less than the actual StorPool template capacity.
Capacity IOPS: currently not used (may use for max IOPS limitations on volumes from this pool).
URL: enter name of the StorPool Template to use. At present one template can be used for at most one Storage Pool.

Storage Tags: If left blank, the StorPool storage plugin will use the pool name to create a corresponding storage tag.
This storage tag may be used later, when defining service or disk offerings.


## Plugin Functionality

<table cellpadding="5">
<tr>
  <th>Plugin Action</th>
  <th>CloudStack Action</th>
  <th>management/agent</th>
  <th>impl. details</th>
</tr>
<tr>
  <td>Create ROOT volume from ISO</td>
  <td>create VM from ISO</td>
  <td>management</td>
  <td>createVolumeAsync</td>
</tr>
<tr>
  <td>Create ROOT volume from Template</td>
  <td>create VM from Template</td>
  <td>management + agent</td>
  <td>copyAsync (T => T, T => V)</td>
</tr>
<tr>
  <td>Create DATA volume</td>
  <td>create Volume</td>
  <td>management</td>
  <td>createVolumeAsync</td>
</tr>
<tr>
  <td>Attach ROOT/DATA volume</td>
  <td>start VM (+attach/detach Volume)</td>
  <td>agent</td>
  <td>connectPhysicalDisk</td>
</tr>
<tr>
  <td>Detach ROOT/DATA volume</td>
  <td>stop VM</td>
  <td>agent</td>
  <td>disconnectPhysicalDiskByPath</td>
</tr>
<tr>
  <td>&nbsp;</td>
  <td>Migrate VM</td>
  <td>agent</td>
  <td>attach + detach</td>
</tr>
<tr>
  <td>Delete ROOT volume</td>
  <td>destroy VM (expunge)</td>
  <td>management</td>
  <td>deleteAsync</td>
</tr>
<tr>
  <td>Delete DATA volume</td>
  <td>delete Volume (detached)</td>
  <td>management</td>
  <td>deleteAsync</td>
</tr>
<tr>
  <td>Create ROOT/DATA volume snapshot</td>
  <td>snapshot volume</td>
  <td>management + agent</td>
  <td>takeSnapshot + copyAsync (S => S)</td>
</tr>
<tr>
  <td>Create volume from snapshoot</td>
  <td>create volume from snapshot</td>
  <td>management + agent(?)</td>
  <td>copyAsync (S => V)</td>
</tr>
<tr>
  <td>Create TEMPLATE from ROOT volume</td>
  <td>create template from volume</td>
  <td>management + agent</td>
  <td>copyAsync (V => T)</td>
</tr>
<tr>
  <td>Create TEMPLATE from snapshot</td>
  <td>create template from snapshot</td>
  <td>SECONDARY STORAGE</td>
  <td>&nbsp;</td>
</tr>
<tr>
  <td>Download volume</td>
  <td>download volume</td>
  <td>management + agent</td>
  <td>copyAsync (V => V)</td>
</tr>
<tr>
  <td>Revert ROOT/DATA volume to snapshot</td>
  <td>revert to snapshot</td>
  <td>NOT IMPLEMENTED</td>
  <td>&nbsp;</td>
</tr>
<tr>
  <td>(Live) resize ROOT/DATA volume</td>
  <td>resize volume</td>
  <td>management + agent</td>
  <td>resize + StorpoolResizeCmd</td>
</tr>
<tr>
  <td>Delete SNAPSHOT (ROOT/DATA)</td>
  <td>delete snapshot</td>
  <td>management</td>
  <td>StorpoolSnapshotStrategy</td>
</tr>
<tr>
  <td>Delete TEMPLATE</td>
  <td>delete template</td>
  <td>agent</td>
  <td>deletePhysicalDisk</td>
</tr>
<tr>
  <td>&nbsp;</td>
  <td>migrate VM/volume to another storage</td>
  <td>NOT IMPLEMENTED</td>
  <td>&nbsp;</td>
</tr>
</table>


### Creating ROOT volume from templates:

When creating the first volume based on the given template, the template is first downloaded (cached) to PRIMARY storage.
This is mapped to a StorPool snapshot so, creating succecutive volumes from the same template does not incur additional 
copying of data to PRIMARY storage.

This cached snapshot is garbage collected when the original template is deleted from CloudStack. This cleanup is done
by a background task in CloudStack.

### Creating a ROOT volume from an ISO image

We just need to create the volume. The ISO installation is handled by CloudStack.

### Creating a DATA volume

DATA volumes are created by CloudStack the first time it is attached to a VM.

### Creating volume from snapshot

Wwe use the fact that the snapshot already exists on PRIMARY, so no data is copied.

TODO: Currently volumes can be created only from StorPool snapshots that already exist on PRIMARY.
TODO: Copy snapshots from SECONDARY to StorPool PRIMARY. Needed, when there is no corresponding StorPool snapshot.

### Resizing volumes

We need to send a resize cmd to agent, where the VM the volume is attached to is running, so that
the resize is visible by the VM.

### Creating snapshots

The snapshot is first created on the PRIMARY storage (i.e. StorPool), then backed-up on SECONDARY storage
(tested with NFS secondary). The original StorPool snapshot is kept, so that creating volumes from the snapshot does not need to copy
the data again to PRIMARY. When the snapshot is deleted from CloudStack so is the corresponding StorPool snapshot.

TODO: Currently snapshots are taken in RAW format. Should we use QCOW2 instead?

### Creating template from snapshot

This is independent of StorPool as snapshots exist on secondary.

### Reverting volume to snapshot

NOT IMPLEMENTED!

TODO: Do we need this?

### Migrating volumes to other Storage pools

NOT IMPLEMENTED!

TODO: Use cases: will both pools be StorPool, i.e. change template; or do we need to support migration to
other storage providers as well. Implementation should be easy for the first case (mgmt only in copyAsync).
For the second case we may need yet another command send to agent.

### BW/IOPS limitations

TODO!

May be enforced for ROOT volumes created from templates with the help of custom service offerings, by adding IOPS limits to the
corresponding system disk offering. Thus, changing the disk offering in "volume resize", may provide a means to manage BW/IOPS
for ROOT volumes.

Currently CloudStack has min IOPS, which is NOT SUPPORTED by StorPool. Thus, min IOPS should always be set to 0. (?)

CloudStack has no way to specify max BW. Do they want to be able to specify max BW, or IOPS limitation only is sufficient.


## Plugin overview: StorPool plugin files and what they're for

### Build infrastructure

#### ./pom.xml

	Build infrastructure (maven). When updating integration to newer versions of CloudStack,
	MUST update <version>4.8.0</version> to whatever the corrsponding CloudStack version is.
	
	For more info about this file, ask google about maven/pom.xml files and cf. the other CloudStack
	pom.xml files.


#### CloudStack Management side classes --

N.B. All of the management side classes are SINGLETONS (yeah, good OOP design, I know), so be careful
not to add any "instance" state in there...

#### ./resources/META-INF/cloudstack/storage-volume-storpool
	+ module.properties
	+ spring-storage-volume-storpool-context.xml

	Used by the Spring framework (dependency injection) to figure out which classes to instantiate
	when the plugin is loaded on CloudStack management. These play no role in CloudStack agents.
	
	In our case these are:
		- StorpoolPrimaryDataStoreProvider: This is the Management side entry point.
		- StorpoolSnapshotStrategy: responsible for cleaning up StorPool snapshots, when corresponding CloudStack snapshots
		are deleted from secondary storage.


#### ./src/org/apache/cloudstack/storage/datastore/provider/StorpoolPrimaryDataStoreProvider.java

	Management side entry point. Called when plugin is loaded.  Creates instances for all other classes
	that constitute the CloudStack management side plugin and injects them into the Spring context.


#### ./src/org/apache/cloudstack/storage/datastore/provider/StorpoolHostListener.java

	Callbacks for Host connect/disconnect events.
	Default host listener path:
	./apache-cloudstack-4.8.0-src/engine/storage/volume/src/org/apache/cloudstack/storage/datastore/provider/DefaultHostListener.java
	
	Cannot use default host listener, as it zeroes our pool's capacity each time a new host is
	connected (CloudStack agent restart). Code was pretty much copied from there.
	
	NB. At present hostDisconnected in never called, so do not use it!


#### ./src/org/apache/cloudstack/storage/datastore/lifecycle/StorpoolPrimaryDataStoreLifeCycle.java

	Manages Primary Data Store (i.e. storage pool) lifecycle operations. Pretty much calls the corresponding
	dataStoreHelper methods, that do all the work (again good OOP design in practice). Code "inspired" by other
	primary storage plugins.


#### ./src/org/apache/cloudstack/storage/datastore/driver/StorpoolPrimaryDataStoreDriver.java

	Management side storage driver that does most of the work. Notes:
	* grantAccess/revokeAccess, which should handle attach/detach oprerations are pretty much useless at the
	moment as they're not called in any of the relevant code paths. Thus attach/detach needs to happen on the
	Agent side.
	
	* createAsync is not called when the CloudStack volume is created, but when it is needed, i.e. when it is
	attached to a VM (if DATA volumes), or when the VM is booted (for ROOT volumes).
	
	* takeSnapshot is called so that the Primary Storage plugin can create a snapshot on Primary. This is subsequently
	copied to Secondary storage via the copyAsync mathod.
	
	* canCopy/copyAsync: one of the many mechanisms determining how data is copied btx. different data stores. It was used
	in stead of the others since it consists of only two methods and thus all the complexity (ugliness) is kept in one place.
	Called pretty much whenever data needs to be copied from/to StorPool, ex. downloading (caching) templates on primary
	storage, backing-up snapshots on secondary storage, downloading volumes to secondary storage, creating volumes from
	snapshots (currently supported only when snapshot is already present on primary, i.e. StorPool snapshots only).
	The idea is to figyre out what the current operation is, and then send the appropriate StorPool copy command to one
	of the agents, which is where the actual copying takes place.


#### ./src/org/apache/cloudstack/storage/datastore/util/StorpoolUtil.java

	Utility functions and classes. Basically a facade for talking with StorPool's API.
	HTTP calls done through Apache's HTTP client library.
	Json serialization/deserialization done through Google's Gson library as this seemed the simplest one to use.
	Both these are used by other parts of CloudStack as well.
	
	Note: Also used for "file log" on the management side (/var/log/cloudstack/management/storpool-plugin.log) which is
	useful for debugging.
	
	Note: At present deleting a StorPool volume/snapshot performes a "detach all forced" operation first, so that
	dangling attachments will not leave left-over volumes/snapshots.


#### ./src/org/apache/cloudstack/storage/snapshot/StorpoolSnapshotStrategy.java

	Responsible for cleaning up StorPool snapshots, when corresponding CloudStack snapshots
	are deleted from secondary storage. This is done by plugging into the CloudStack snapshot deletion
	process and deleting the StorPool snapshot as well.
	
	Note: at present the only sure way to check if the snapshot being deleted has a corresponding StorPool
	snapshot is to ask the StorPool mgmt, and not rely on CloudStack, as records of snapshots on primary
	are pretty much unreliable (ex. when having a chain of snapshots, there is a record of only the last one
	in the CloudStack DB).


### CloudStack Management to Agent communication

#### ./src/com/cloud/agent/api/storage:
	+ StorpoolBackupSnapshotCommand.java
	+ StorpoolCopyCommand.java
	+ StorpoolCopyVolumeToSecondaryCommand.java
	+ StorpoolDownloadTemplateCommand.java
	+ StorpoolResizeVolumeCommand.java

	Commands issued by StorPool management plugin to Agents.
	
	We create our own commands, so that we can integrate non-intrusively with the KVM
	agent side plugin.


### CloudStack Agent side classes

#### ./src/com/cloud/hypervisor/kvm/resource/wrapper:
	+ StorpoolBackupSnapshotCommandWrapper.java
	+ StorpoolCopyVolumeToSecondaryCommandWrapper.java
	+ StorpoolDownloadTemplateCommandWrapper.java
	+ StorpoolResizeVolumeCommandWrapper.java

	Command handler classes for the previously mentioned commands.


#### ./src/com/cloud/hypervisor/kvm/storage:
	+ StorpoolStorageAdaptor.java
	This is the main agent side class: it is responsible for attaching/detaching StorPool's volumes and snapshots
	so that they're usable by VMs or can be copied. It is also responsible for deleting left-over StorPool snapshots
	corresponding to deleted CloudStack templates (method deletePhysicalDisk).
	
	This class also implements file logging (/var/log/cloudstach/agent/storpool-agent.log) useful for debugging.
	
	+ StorpoolStoragePool.java
	Pretty much forwards all calls to the previous class (again good OOP design in practice).


## Useful CloudStack files and directores

### VO: value objects
	
These correspond approximately to entries in the CloudStack database.

The 3 classes that are used in StorPool's plugin code are:

./engine/schema/src/com/cloud/storage/VolumeVO.java
./engine/schema/src/com/cloud/storage/SnapshotVO.java
./engine/schema/src/com/cloud/storage/VMTemplateVO.java

### DataTO: data transfer objects
	
Used in Storage subsystem commands send to agents
 + iface DataTO (apache-cloudstack-4.8.0-src/api/src/com/cloud/agent/api/to/DataTO.java)
  + class VolumeObjectTO		/home/zhilkov/apache-cloudstack-4.8.0-src/core/src/org/apache/cloudstack/storage/to/VolumeObjectTO.java
  + class SnapshotObjectTO		/home/zhilkov/apache-cloudstack-4.8.0-src/core/src/org/apache/cloudstack/storage/to/SnapshotObjectTO.java
  + class TemplateObjectTO		/home/zhilkov/apache-cloudstack-4.8.0-src/core/src/org/apache/cloudstack/storage/to/TemplateObjectTO.java


The usual pattern for the files bewol is to have an interface and a corresponding implementation. Most of the time there is only one
such implementation so no real need for the interface, but enterprise software, so ...

### Volume related classes

./apache-cloudstack-4.8.0-src/engine/api/src/org/apache/cloudstack/engine/subsystem/api/storage/VolumeService.java
./apache-cloudstack-4.8.0-src/engine/storage/volume/src/org/apache/cloudstack/storage/volume/VolumeServiceImpl.java

./apache-cloudstack-4.8.0-src/api/src/com/cloud/storage/VolumeApiService.java
./apache-cloudstack-4.8.0-src/server/src/com/cloud/storage/VolumeApiServiceImpl.java

./apache-cloudstack-4.8.0-src/engine/api/src/org/apache/cloudstack/engine/orchestration/service/VolumeOrchestrationService.java
./apache-cloudstack-4.8.0-src/engine/orchestration/src/org/apache/cloudstack/engine/orchestration/VolumeOrchestrator.java

./apache-cloudstack-4.8.0-src/engine/api/src/org/apache/cloudstack/engine/subsystem/api/storage/StoragePoolAllocator.java
./apache-cloudstack-4.8.0-src/engine/storage/src/org/apache/cloudstack/storage/allocator/\*.java

### Snapshot related classes

./apache-cloudstack-4.8.0-src/engine/storage/snapshot/src/org/apache/cloudstack/storage/snapshot/SnapshotStrategyBase.java
./apache-cloudstack-4.8.0-src/engine/storage/snapshot/src/org/apache/cloudstack/storage/snapshot/StorageSystemSnapshotStrategy.java
./engine/storage/snapshot/src/org/apache/cloudstack/storage/snapshot/XenserverSnapshotStrategy.java

./apache-cloudstack-4.8.0-src/engine/api/src/org/apache/cloudstack/engine/subsystem/api/storage/StorageStrategyFactory.java
./apache-cloudstack-4.8.0-src/engine/storage/src/org/apache/cloudstack/storage/helper/StorageStrategyFactoryImpl.java

./apache-cloudstack-4.8.0-src/engine/api/src/org/apache/cloudstack/engine/subsystem/api/storage/SnapshotService.java
./apache-cloudstack-4.8.0-src/engine/storage/snapshot/src/org/apache/cloudstack/storage/snapshot/SnapshotServiceImpl.java

./apache-cloudstack-4.8.0-src/engine/storage/datamotion/src/org/apache/cloudstack/storage/motion/DataMotionServiceImpl.java
./apache-cloudstack-4.8.0-src/engine/storage/datamotion/src/org/apache/cloudstack/storage/motion/AncientDataMotionStrategy.java
./apache-cloudstack-4.8.0-src/engine/storage/datamotion/src/org/apache/cloudstack/storage/motion/StorageSystemDataMotionStrategy.java

./apache-cloudstack-4.8.0-src/server/src/com/cloud/storage/snapshot/SnapshotManager.java
./apache-cloudstack-4.8.0-src/server/src/com/cloud/storage/snapshot/SnapshotManagerImpl.java

### Other

./apache-cloudstack-4.8.0-src/server/src/com/cloud/storage/StorageManager.java
./apache-cloudstack-4.8.0-src/server/src/com/cloud/storage/StorageManagerImpl.java

./apache-cloudstack-4.8.0-src/server/src/com/cloud/api/ApiDBUtils.java
./apache-cloudstack-4.8.0-src/server/src/com/cloud/server/ManagementServerImpl.java

### User and Admin command classes directories

./apache-cloudstack-4.8.0-src/api/src/org/apache/cloudstack/api/command/user/volume/
./apache-cloudstack-4.8.0-src/api/src/org/apache/cloudstack/api/command/user/snapshot/
./apache-cloudstack-4.8.0-src/api/src/org/apache/cloudstack/api/command/user/template/
./apache-cloudstack-4.8.0-src/api/src/org/apache/cloudstack/api/command/user/vmsnapshot/

./apache-cloudstack-4.8.0-src/api/src/org/apache/cloudstack/api/command/admin/volume/
./apache-cloudstack-4.8.0-src/api/src/org/apache/cloudstack/api/command/admin/template/
./apache-cloudstack-4.8.0-src/api/src/org/apache/cloudstack/api/command/admin/storage/
./apache-cloudstack-4.8.0-src/api/src/org/apache/cloudstack/api/command/admin/vm/

