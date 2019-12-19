package com.cloud.hypervisor.kvm.storage;

import org.apache.cloudstack.storage.datastore.util.StorpoolUtil;
import org.apache.log4j.Logger;
import org.aspectj.lang.annotation.AfterReturning;
import org.aspectj.lang.annotation.Aspect;

import com.cloud.storage.Volume;

@Aspect
public class StorpoolStorageListner {
    private static final Logger log = Logger.getLogger(StorpoolStorageListner.class);

    @AfterReturning(pointcut = "execution (* com.cloud.storage.VolumeApiServiceImpl.attachVolumeToVM(..)) && args(vmId, volumeId, deviceId)", returning="retVal")
    public void afterAttachVolumeToVM(Object retVal, Long vmId, Long volumeId, Long deviceId) {
        updateVolumeTags(retVal, vmId);
    }

    @AfterReturning(pointcut = "execution (* com.cloud.storage.VolumeApiServiceImpl.detachVolumeFromVM(..))", returning="retVal")
    public void afterDetachVolumeToVM(Object retVal) {
        updateVolumeTags(retVal, null);
    }

    private void updateVolumeTags(Object retVal, Long vmId ) {
        if (retVal instanceof Volume) {
            Volume vol = (Volume) retVal;
            log.info(String.format("Volume id=%s, name=%s, instanceId=%s, path=%s", vol.getId(), vol.getName(),
                    vol.getInstanceId(), vol.getPath()));
            String name = StorpoolStorageAdaptor.getVolumeNameFromPath(vol.getPath());
            if (name != null) {
                StorpoolUtil.volumeUpadateTags(name, vmId, null);
            }
        }
    }
}
