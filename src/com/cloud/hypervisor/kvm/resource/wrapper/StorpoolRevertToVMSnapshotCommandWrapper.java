package com.cloud.hypervisor.kvm.resource.wrapper;

import org.apache.log4j.Logger;

import com.cloud.agent.api.Answer;
import com.cloud.agent.api.RevertToVMSnapshotCommand;
import com.cloud.hypervisor.kvm.resource.LibvirtComputingResource;
import com.cloud.resource.CommandWrapper;
import com.cloud.resource.ResourceWrapper;

@ResourceWrapper(handles = RevertToVMSnapshotCommand.class)
public class StorpoolRevertToVMSnapshotCommandWrapper extends CommandWrapper<RevertToVMSnapshotCommand, Answer, LibvirtComputingResource> {

     private static final Logger log = Logger.getLogger(StorpoolRevertToVMSnapshotCommandWrapper.class);

     @Override
     public Answer execute(RevertToVMSnapshotCommand command, LibvirtComputingResource serverResource) {
          // TODO Auto-generated method stub
          log.info("StorpoolRevertToVMSnapshotCommandWrapper execute");
          throw new UnsupportedOperationException("Unsupported command");
     }

}
