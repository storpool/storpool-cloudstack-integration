package com.cloud.agent.api.storage;

import java.util.List;

import org.apache.cloudstack.storage.to.VolumeObjectTO;

import com.cloud.agent.api.RevertToVMSnapshotCommand;
import com.cloud.agent.api.VMSnapshotTO;

public class StorpoolRevertToVMSnapshotCommand  extends RevertToVMSnapshotCommand{

     public StorpoolRevertToVMSnapshotCommand(String vmName, String vmUuid, VMSnapshotTO snapshot,
               List<VolumeObjectTO> volumeTOs, String guestOSType) {
          super(vmName, vmUuid, snapshot, volumeTOs, guestOSType);
          // TODO Auto-generated constructor stub
     }
}
