package com.cloud.agent.api.storage;

import java.util.List;

import org.apache.cloudstack.storage.to.VolumeObjectTO;

import com.cloud.agent.api.Answer;

public class StorpoolDeleteVMSnapshotAnswer  extends Answer {
     private List<VolumeObjectTO> volumeTOs;

     public StorpoolDeleteVMSnapshotAnswer() {
     }

     public StorpoolDeleteVMSnapshotAnswer(StorpoolDeleteSnapshotVMCommand cmd, boolean result, String message) {
         super(cmd, result, message);
     }

     public StorpoolDeleteVMSnapshotAnswer(StorpoolDeleteSnapshotVMCommand cmd, List<VolumeObjectTO> volumeTOs) {
         super(cmd, true, "");
         this.volumeTOs = volumeTOs;
     }

     public List<VolumeObjectTO> getVolumeTOs() {
         return volumeTOs;
     }

     public void setVolumeTOs(List<VolumeObjectTO> volumeTOs) {
         this.volumeTOs = volumeTOs;
     }
}
