package com.cloud.hypervisor.kvm.storage;

import org.apache.cloudstack.storage.datastore.util.StorpoolUtil;
import org.apache.log4j.Logger;
import org.aspectj.lang.annotation.AfterReturning;
import org.aspectj.lang.annotation.Aspect;

import com.cloud.storage.Volume;

@Aspect
public class StorpoolStorageListner {
    private static final Logger log = Logger.getLogger(StorpoolStorageListner.class);

    @AfterReturning(pointcut = "execution (* com.cloud.storage.VolumeApiServiceImpl.attachVolumeToVM(..))", returning="retVal")
    public void afterAttachVolumeToVM(Object retVal) {
        log.info("VolumeApiServiceImpl.attachVolumeToVM");
        log.info(String.format("VolumeApiServiceImpl.attachVolumeToVM obj=%s", retVal));
        log.info(String.format("Object is Volume instance=%s ",retVal instanceof Volume));
        if (retVal instanceof Volume) {
           Volume vol = (Volume) retVal;
           log.info(String.format("Volume id=%s, name=%s, instanceId=%s, path=%s", vol.getId(), vol.getName(),vol.getInstanceId(), vol.getPath()));
           Long vmId = vol.getInstanceId();
           String name = StorpoolStorageAdaptor.getVolumeNameFromPath(vol.getPath());
           StorpoolUtil.volumeUpadateTags(name, vmId);
       }
    }

    @AfterReturning(pointcut = "execution (* com.cloud.storage.VolumeApiServiceImpl.detachVolumeFromVM(..))", returning="retVal")
    public void afterDetachVolumeToVM(Object retVal) {
        log.info("VolumeApiServiceImpl.attachVolumeToVM");
        log.info(String.format("VolumeApiServiceImpl.attachVolumeToVM obj=%s", retVal));
        log.info(String.format("Object is Volume instance=%s ",retVal instanceof Volume));
        if (retVal instanceof Volume) {
           Volume vol = (Volume) retVal;
           log.info(String.format("Volume id=%s, name=%s, instanceId=%s, path=%s", vol.getId(), vol.getName(),vol.getInstanceId(), vol.getPath()));
           Long vmId = vol.getInstanceId();
           String name = StorpoolStorageAdaptor.getVolumeNameFromPath(vol.getPath());
           StorpoolUtil.volumeUpadateTags(name, vmId);
       }
    }
}
