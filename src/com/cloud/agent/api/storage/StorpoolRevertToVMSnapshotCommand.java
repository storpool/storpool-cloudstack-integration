package com.cloud.agent.api.storage;

import java.util.List;

import org.apache.cloudstack.storage.to.VolumeObjectTO;

import com.cloud.agent.api.RevertToVMSnapshotCommand;
import com.cloud.agent.api.VMSnapshotTO;

public class StorpoolRevertToVMSnapshotCommand  extends RevertToVMSnapshotCommand{

    private Long vmId;
     public StorpoolRevertToVMSnapshotCommand(String vmName, String vmUuid, VMSnapshotTO snapshot,
               List<VolumeObjectTO> volumeTOs, String guestOSType,Long vmId) {
          super(vmName, vmUuid, snapshot, volumeTOs, guestOSType);
          this.vmId = vmId;
     }

    public Long getVmId() {
        return vmId;
    }
    public void setVmId(Long vmId) {
        this.vmId = vmId;
    }

}
