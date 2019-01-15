//
// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements.  See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership.  The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License.  You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied.  See the License for the
// specific language governing permissions and limitations
// under the License.
//

package com.cloud.hypervisor.kvm.resource.wrapper;

import java.util.List;
import java.io.File;
import org.apache.log4j.Logger;

import org.apache.cloudstack.storage.command.CopyCmdAnswer;
import org.apache.cloudstack.storage.to.VolumeObjectTO;
import org.apache.cloudstack.utils.qemu.QemuImg;
import org.apache.cloudstack.utils.qemu.QemuImg.PhysicalDiskFormat;
import org.apache.cloudstack.utils.qemu.QemuImgFile;

import com.cloud.agent.api.storage.StorpoolDownloadVolumeCommand;
import com.cloud.agent.api.to.DataStoreTO;
import com.cloud.agent.api.to.NfsTO;
import com.cloud.hypervisor.kvm.resource.LibvirtComputingResource;
import com.cloud.hypervisor.kvm.storage.KVMPhysicalDisk;
import com.cloud.hypervisor.kvm.storage.KVMStoragePool;
import com.cloud.hypervisor.kvm.storage.KVMStoragePoolManager;
import com.cloud.hypervisor.kvm.storage.StorpoolStorageAdaptor;
import com.cloud.resource.CommandWrapper;
import com.cloud.resource.ResourceWrapper;

import static com.cloud.hypervisor.kvm.storage.StorpoolStorageAdaptor.SP_LOG;

@ResourceWrapper(handles = StorpoolDownloadVolumeCommand.class)
public final class StorpoolDownloadVolumeCommandWrapper extends CommandWrapper<StorpoolDownloadVolumeCommand, CopyCmdAnswer, LibvirtComputingResource> {

    private static final Logger s_logger = Logger.getLogger(StorpoolDownloadVolumeCommandWrapper.class);

    @Override
    public CopyCmdAnswer execute(final StorpoolDownloadVolumeCommand cmd, final LibvirtComputingResource libvirtComputingResource) {
        String dstPath = null;
        KVMStoragePool secondaryPool = null;

        try {
            final VolumeObjectTO src = cmd.getSrcTO();
            final VolumeObjectTO dst = cmd.getDstTO();
            final KVMStoragePoolManager storagePoolMgr = libvirtComputingResource.getStoragePoolMgr();
            SP_LOG("StorpoolDownloadVolumeCommandWrapper.execute: src=" + src.getPath() + " srcName=" + src.getName() + " dst=" + dst.getPath());

            final DataStoreTO srcDataStore = src.getDataStore();
            if (!(srcDataStore instanceof NfsTO)) {
                return new CopyCmdAnswer("Download volume to Storpool: Only NFS secondary supported at present!");
            }

            final NfsTO nfsImageStore = (NfsTO)srcDataStore;
            final String tmplturl = nfsImageStore.getUrl() + File.separator + src.getPath();
            final int index = tmplturl.lastIndexOf("/");
            final String mountpoint = tmplturl.substring(0, index);
            String tmpltname = null;
            if (index < tmplturl.length() - 1) {
                tmpltname = tmplturl.substring(index + 1);
            }

            secondaryPool = storagePoolMgr.getStoragePoolByURI(mountpoint);

            KVMPhysicalDisk srcDisk = null;

            if (tmpltname == null) {
                secondaryPool.refresh();
                final List<KVMPhysicalDisk> disks = secondaryPool.listPhysicalDisks();
                if (disks == null || disks.isEmpty()) {
                    SP_LOG("Failed to get volumes from pool: " + secondaryPool.getUuid());
                    return new CopyCmdAnswer("Failed to get volumes from pool: " + secondaryPool.getUuid());
                }
                for (final KVMPhysicalDisk disk : disks) {
                    if (disk.getName().endsWith("qcow2")) {
                        srcDisk = disk;
                        break;
                    }
                }
            } else {
                srcDisk = secondaryPool.getPhysicalDisk(tmpltname);
            }

            if (srcDisk == null) {
                SP_LOG("Failed to get volume from pool: " + secondaryPool.getUuid());
                return new CopyCmdAnswer("Failed to get volume from pool: " + secondaryPool.getUuid());
            }

            SP_LOG("got src path: " + srcDisk.getPath() + " srcSize " + srcDisk.getVirtualSize());

            final QemuImgFile srcFile = new QemuImgFile(srcDisk.getPath(), srcDisk.getFormat());

            final QemuImg qemu = new QemuImg(cmd.getWaitInMillSeconds());
            StorpoolStorageAdaptor.resize( Long.toString(srcDisk.getVirtualSize()), dst.getPath());

            dstPath = dst.getPath();
            StorpoolStorageAdaptor.attachOrDetachVolume("attach", "volume", dstPath);

            final QemuImgFile dstFile = new QemuImgFile(dstPath, PhysicalDiskFormat.RAW);

            qemu.convert(srcFile, dstFile);
            return new CopyCmdAnswer(dst);
        } catch (final Exception e) {
            final String error = "Failed to copy volume to primary: " + e.getMessage();
            s_logger.debug(error);
            return new CopyCmdAnswer(error);
        } finally {
            if (dstPath != null) {
                StorpoolStorageAdaptor.attachOrDetachVolume("detach", "volume", dstPath);
            }

            if (secondaryPool != null) {
                try {
                    secondaryPool.delete();
                } catch (final Exception e) {
                    s_logger.debug("Failed to delete secondary storage", e);
                }
            }
        }
    }
}
