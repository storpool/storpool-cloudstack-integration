package com.cloud.agent.api.storage;

import java.util.List;

import org.apache.cloudstack.storage.to.VolumeObjectTO;

import com.cloud.agent.api.VMSnapshotBaseCommand;
import com.cloud.agent.api.VMSnapshotTO;

public class StorpoolDeleteSnapshotVMCommand extends VMSnapshotBaseCommand {
     public StorpoolDeleteSnapshotVMCommand(String vmName, VMSnapshotTO snapshot, List<VolumeObjectTO> volumeTOs, String guestOSType) {
          super(vmName, snapshot, volumeTOs, guestOSType);
      }

}
