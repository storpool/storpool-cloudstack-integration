package com.cloud.hypervisor.kvm.resource.wrapper;

import java.util.List;

import org.apache.cloudstack.storage.datastore.util.StorpoolUtil;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil.SpApiResponse;
import org.apache.cloudstack.storage.to.VolumeObjectTO;
import org.apache.log4j.Logger;

import com.cloud.agent.api.Answer;
import com.cloud.agent.api.storage.StorpoolRevertToVMSnapshotAnswer;
import com.cloud.agent.api.storage.StorpoolRevertToVMSnapshotCommand;
import com.cloud.hypervisor.kvm.resource.LibvirtComputingResource;
import com.cloud.hypervisor.kvm.storage.StorpoolStorageAdaptor;
import com.cloud.resource.CommandWrapper;
import com.cloud.resource.ResourceWrapper;
import com.cloud.vm.VirtualMachine.PowerState;

@ResourceWrapper(handles = StorpoolRevertToVMSnapshotCommand.class)
public class StorpoolRevertToVMSnapshotCommandWrapper
          extends CommandWrapper<StorpoolRevertToVMSnapshotCommand, Answer, LibvirtComputingResource> {

     private static final Logger log = Logger.getLogger(StorpoolRevertToVMSnapshotCommandWrapper.class);

     @Override
     public Answer execute(StorpoolRevertToVMSnapshotCommand command, LibvirtComputingResource serverResource) {
          // TODO Auto-generated method stub
          log.info("StorpoolRevertToVMSnapshotCommandWrapper execute");
          List<VolumeObjectTO> volumeObjectTOs = command.getVolumeTOs();
          try {
               for (VolumeObjectTO volumeObjectTO : volumeObjectTOs) {
                    String snapshotName = command.getVmName() + "_"
                              + StorpoolStorageAdaptor.getVolumeNameFromPath(volumeObjectTO.getPath());
                    String volumeName = StorpoolStorageAdaptor.getVolumeNameFromPath(volumeObjectTO.getPath());
                    String backupSnapshot = volumeName + "to_be_removed";
                    Long size = volumeObjectTO.getSize();
                    log.info(String.format(
                              "StorpoolRevertToVMSnapshotCommandWrapper.execute snapshotName=%s, volumeName=%s, backupSnapshot=%s, size=%s",
                              snapshotName, volumeName, backupSnapshot, size));
                    StorpoolUtil.snapshotDelete(backupSnapshot);
                    SpApiResponse resp = StorpoolUtil.volumeSnapshot(volumeName, backupSnapshot);
                    if (resp.getError() != null) {
                         String err = String.format("Could not complete task error=%s", resp.getError());
                         log.error("Snapshot could not complete revert task" + err);
                         return new StorpoolRevertToVMSnapshotAnswer(command, false, err);
                    }

                    resp = StorpoolUtil.volumeDelete(volumeName);
                    if (resp.getError() != null) {
                         StorpoolUtil.snapshotDelete(backupSnapshot);
                         String err = String.format("Could not complete task error=%s", resp.getError());
                         log.error("Delete volume Could not complete revert task" + err);
                         return new StorpoolRevertToVMSnapshotAnswer(command, false, err);
                    }

                    resp = StorpoolUtil.volumeCreate(volumeName, snapshotName, null, size);
                    if (resp.getError() != null) {
                         String err = String.format("Could not complete task error=%s", resp.getError());
                         log.error("Create Could not complete revert task" + err);
                         resp = StorpoolUtil.volumeCreate(volumeName, backupSnapshot, null, size);
                         if (resp.getError() != null) {
                              err = String.format("Could not complete task error=%s", resp.getError());
                         } else {
                              StorpoolUtil.snapshotDelete(backupSnapshot);
                         }
                         return new StorpoolRevertToVMSnapshotAnswer(command, false, err);
                    }
                    StorpoolUtil.snapshotDelete(backupSnapshot);
               }
               return new StorpoolRevertToVMSnapshotAnswer(command, volumeObjectTOs, PowerState.PowerOff);
          } catch (Exception e) {
               throw new UnsupportedOperationException("Revert snapshot failed" + e.getMessage());
          }
     }
}
