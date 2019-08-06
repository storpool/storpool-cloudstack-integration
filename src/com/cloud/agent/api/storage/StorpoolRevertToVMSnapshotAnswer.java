package com.cloud.agent.api.storage;

import java.util.List;

import org.apache.cloudstack.storage.to.VolumeObjectTO;

import com.cloud.agent.api.RevertToVMSnapshotAnswer;
import com.cloud.vm.VirtualMachine.PowerState;

public class StorpoolRevertToVMSnapshotAnswer extends RevertToVMSnapshotAnswer{

     public StorpoolRevertToVMSnapshotAnswer() {
          super();
          // TODO Auto-generated constructor stub
     }

     public StorpoolRevertToVMSnapshotAnswer(StorpoolRevertToVMSnapshotCommand cmd, boolean result, String message) {
          super(cmd, result, message);
     }

     public StorpoolRevertToVMSnapshotAnswer(StorpoolRevertToVMSnapshotCommand cmd, List<VolumeObjectTO> volumeTOs,
               PowerState vmState) {
          super(cmd, volumeTOs, vmState);
     }
}
