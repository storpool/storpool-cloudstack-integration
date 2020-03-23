package com.cloud.hypervisor.kvm.resource.wrapper;

import static com.cloud.hypervisor.kvm.storage.StorpoolStorageAdaptor.SP_LOG;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.util.HashMap;
import java.util.Map;

import org.apache.cloudstack.storage.command.CopyCmdAnswer;
import org.apache.cloudstack.storage.to.SnapshotObjectTO;
import org.apache.cloudstack.storage.to.TemplateObjectTO;
import org.apache.cloudstack.utils.qemu.QemuImg;
import org.apache.cloudstack.utils.qemu.QemuImg.PhysicalDiskFormat;
import org.apache.cloudstack.utils.qemu.QemuImgFile;
import org.apache.commons.io.FileUtils;
import org.apache.log4j.Logger;

import com.cloud.agent.api.storage.StorpoolBackupTemplateFromSnapshotCommand;
import com.cloud.agent.api.to.DataStoreTO;
import com.cloud.agent.api.to.NfsTO;
import com.cloud.hypervisor.kvm.resource.LibvirtComputingResource;
import com.cloud.hypervisor.kvm.storage.KVMStoragePool;
import com.cloud.hypervisor.kvm.storage.KVMStoragePoolManager;
import com.cloud.hypervisor.kvm.storage.StorpoolStorageAdaptor;
import com.cloud.resource.CommandWrapper;
import com.cloud.resource.ResourceWrapper;
import com.cloud.storage.Storage.ImageFormat;
import com.cloud.storage.template.Processor;
import com.cloud.storage.template.QCOW2Processor;
import com.cloud.storage.template.TemplateLocation;
import com.cloud.storage.template.TemplateProp;
import com.cloud.storage.template.Processor.FormatInfo;
import com.cloud.storage.StorageLayer;

@ResourceWrapper(handles = StorpoolBackupTemplateFromSnapshotCommand.class)
public class StorpoolBackupTemplateFromSnapshotCommandWrapper extends CommandWrapper<StorpoolBackupTemplateFromSnapshotCommand, CopyCmdAnswer, LibvirtComputingResource> {

    private static final Logger s_logger = Logger.getLogger(StorpoolBackupTemplateFromSnapshotCommandWrapper.class);

    @Override
    public CopyCmdAnswer execute(final StorpoolBackupTemplateFromSnapshotCommand cmd, final LibvirtComputingResource libvirtComputingResource) {
        String srcPath = null;
        KVMStoragePool secondaryPool = null;

        try {
            final SnapshotObjectTO src = cmd.getSrcTO();
            final TemplateObjectTO dst = cmd.getDstTO();
            final KVMStoragePoolManager storagePoolMgr = libvirtComputingResource.getStoragePoolMgr();
            StorageLayer storage = libvirtComputingResource.getStorage();
            Processor processor = new QCOW2Processor();
            String _tmpltpp = "template.properties";

            SP_LOG("StorpoolBackupTemplateFromSnapshotCommandWrapper.execute: src=" + src.getPath() + "dst=" + dst.getPath());
            StorpoolStorageAdaptor.attachOrDetachVolume("attach", "snapshot", src.getPath());
            srcPath = src.getPath();

            final QemuImgFile srcFile = new QemuImgFile(srcPath, PhysicalDiskFormat.RAW);

            final DataStoreTO dstDataStore = dst.getDataStore();
            if (!(dstDataStore instanceof NfsTO)) {
                return new CopyCmdAnswer("Backup Storpool snapshot: Only NFS secondary supported at present!");
            }

            secondaryPool = storagePoolMgr.getStoragePoolByURI(dstDataStore.getUrl());

            final String dstDir = secondaryPool.getLocalPath() + File.separator + dst.getPath();
            FileUtils.forceMkdir(new File(dstDir));

            final String dstPath = dstDir + File.separator + dst.getName() + "." + src.getVolume().getFormat().getFileExtension();
            final QemuImgFile dstFile = new QemuImgFile(dstPath, PhysicalDiskFormat.QCOW2);

            final QemuImg qemu = new QemuImg(cmd.getWaitInMillSeconds());
            qemu.convert(srcFile, dstFile);

            storage.create(dstDir, _tmpltpp);
            String metaFileName = dstDir + File.separator + _tmpltpp;
            File metaFile = new File(metaFileName);

            try ( FileWriter writer = new FileWriter(metaFile);
                BufferedWriter bufferWriter = new BufferedWriter(writer);) {
                bufferWriter.write("uniquename=" + dst.getName());
                bufferWriter.write("\n");
                bufferWriter.write("filename=" + src.getName() +"."+ src.getVolume().getFormat().getFileExtension());
            }
            Map<String, Object> params = new HashMap<String, Object>();
            params.put(StorageLayer.InstanceConfigKey, storage);

            processor.configure("template processor", params);

            FormatInfo info = processor.process(dstDir, null, dst.getName());
            TemplateLocation loc = new TemplateLocation(storage, dstDir);
            loc.create(1, true, dst.getName());
            loc.addFormat(info);
            loc.save();

            TemplateProp prop = loc.getTemplateInfo();
            final TemplateObjectTO template = new TemplateObjectTO();
            template.setPath(dst.getPath() + File.separator + dst.getName());
            template.setFormat(ImageFormat.QCOW2);
            template.setSize(prop.getSize());
            template.setPhysicalSize(prop.getPhysicalSize());

            return new CopyCmdAnswer(template);
        } catch (final Exception e) {
            final String error = "failed to backup snapshot: " + e.getMessage();
            SP_LOG(error);
            s_logger.debug(error);
            return new CopyCmdAnswer(error);
        } finally {
            if (srcPath != null) {
                StorpoolStorageAdaptor.attachOrDetachVolume("detach", "snapshot", srcPath);
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
