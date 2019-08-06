package com.cloud.hypervisor.kvm.resource.wrapper;

import java.util.List;

import org.apache.cloudstack.storage.datastore.util.StorpoolUtil;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil.SpApiResponse;
import org.apache.cloudstack.storage.to.VolumeObjectTO;
import org.apache.log4j.Logger;

import com.cloud.agent.api.Answer;
import com.cloud.agent.api.storage.StorpoolDeleteSnapshotVMCommand;
import com.cloud.agent.api.storage.StorpoolDeleteVMSnapshotAnswer;
import com.cloud.hypervisor.kvm.resource.LibvirtComputingResource;
import com.cloud.hypervisor.kvm.storage.StorpoolStorageAdaptor;
import com.cloud.resource.CommandWrapper;
import com.cloud.resource.ResourceWrapper;
import com.cloud.utils.exception.CloudRuntimeException;

@ResourceWrapper(handles = StorpoolDeleteSnapshotVMCommand.class)
public class StorpoolDeleteVMCommandWrapper
          extends CommandWrapper<StorpoolDeleteSnapshotVMCommand, Answer, LibvirtComputingResource> {
     private static final Logger log = Logger.getLogger(StorpoolDeleteVMCommandWrapper.class);

     @Override
     public Answer execute(StorpoolDeleteSnapshotVMCommand command, LibvirtComputingResource serverResource) {
          // TODO Auto-generated method stub
          log.info("StorpoolDeleteVMCommandWrapper execute" + command.getVmName());
          List<VolumeObjectTO> volumeTOs = command.getVolumeTOs();
          SpApiResponse resp = null;
          for (VolumeObjectTO volumeObjectTO : volumeTOs) {
               String snapshotName = command.getVmName() + "_" + StorpoolStorageAdaptor.getVolumeNameFromPath(volumeObjectTO.getPath());
               log.info("StorpoolDeleteVMCommandWrapper snapshotName="+ snapshotName);
               resp = StorpoolUtil.snapshotDelete(snapshotName);
               log.info("StorpoolVMSnapshotCommandWrapper ");
               log.debug(String.format("  SpApiResponse response=%s ", resp));
               String err = null;
               try {
                    if (resp.getError() != null) {
                         err = String.format("Could not create storpool vm error=%s", resp.getError());
                         log.error("Could not create snapshot for vm:" + err);
                         return new StorpoolDeleteVMSnapshotAnswer(command, false, err);
                    }

               } catch (Exception e) {
                    // TODO: handle exception
                    log.error("CreateKVMVMSnapshotAnswer exception:" + e.getMessage());
                    throw new CloudRuntimeException("CreateKVMVMSnapshotAnswer failed:" + e.getMessage());
               }
          }
          return new StorpoolDeleteVMSnapshotAnswer(command, command.getVolumeTOs());
     }

}
