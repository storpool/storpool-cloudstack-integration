/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
package org.apache.cloudstack.storage.datastore.driver;

import java.util.Map;

import javax.inject.Inject;

import org.apache.cloudstack.engine.subsystem.api.storage.ChapInfo;
import org.apache.cloudstack.engine.subsystem.api.storage.CopyCommandResult;
import org.apache.cloudstack.engine.subsystem.api.storage.CreateCmdResult;
import org.apache.cloudstack.engine.subsystem.api.storage.DataObject;
import org.apache.cloudstack.engine.subsystem.api.storage.DataStore;
import org.apache.cloudstack.engine.subsystem.api.storage.EndPoint;
import org.apache.cloudstack.engine.subsystem.api.storage.EndPointSelector;
import org.apache.cloudstack.engine.subsystem.api.storage.PrimaryDataStoreDriver;
import org.apache.cloudstack.engine.subsystem.api.storage.SnapshotInfo;
import org.apache.cloudstack.engine.subsystem.api.storage.TemplateInfo;
import org.apache.cloudstack.engine.subsystem.api.storage.VolumeInfo;
import org.apache.cloudstack.framework.async.AsyncCompletionCallback;
import org.apache.cloudstack.framework.config.dao.ConfigurationDao;
import org.apache.cloudstack.storage.command.CommandResult;
import org.apache.cloudstack.storage.command.CopyCmdAnswer;
import org.apache.cloudstack.storage.command.CopyCommand;
import org.apache.cloudstack.storage.command.CreateObjectAnswer;
import org.apache.cloudstack.storage.command.StorageSubSystemCommand;
import org.apache.cloudstack.storage.datastore.db.PrimaryDataStoreDao;
import org.apache.cloudstack.storage.datastore.db.StoragePoolVO;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil.SpApiResponse;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil.SpConnectionDesc;
import org.apache.cloudstack.storage.to.PrimaryDataStoreTO;
import org.apache.cloudstack.storage.to.SnapshotObjectTO;
import org.apache.cloudstack.storage.to.TemplateObjectTO;
import org.apache.cloudstack.storage.to.VolumeObjectTO;
import org.apache.cloudstack.storage.volume.VolumeObject;
import org.apache.log4j.Logger;

import com.cloud.agent.api.Answer;
import com.cloud.agent.api.storage.ResizeVolumeAnswer;
import com.cloud.agent.api.storage.StorpoolBackupSnapshotCommand;
import com.cloud.agent.api.storage.StorpoolCopyVolumeToSecondaryCommand;
import com.cloud.agent.api.storage.StorpoolDownloadTemplateCommand;
import com.cloud.agent.api.storage.StorpoolDownloadVolumeCommand;
import com.cloud.agent.api.storage.StorpoolResizeVolumeCommand;
import com.cloud.agent.api.to.DataObjectType;
import com.cloud.agent.api.to.DataStoreTO;
import com.cloud.agent.api.to.DataTO;
import com.cloud.agent.api.to.StorageFilerTO;
import com.cloud.configuration.Config;
import com.cloud.host.Host;
import com.cloud.hypervisor.kvm.storage.StorpoolStorageAdaptor;
import com.cloud.storage.ResizeVolumePayload;
import com.cloud.storage.Storage.StoragePoolType;
import com.cloud.storage.StorageManager;
import com.cloud.storage.StoragePool;
import com.cloud.storage.VMTemplateStoragePoolVO;
import com.cloud.storage.VolumeVO;
import com.cloud.storage.dao.VMTemplatePoolDao;
import com.cloud.storage.dao.VolumeDao;
import com.cloud.utils.NumbersUtil;
import com.cloud.vm.VirtualMachineManager;


public class StorpoolPrimaryDataStoreDriver implements PrimaryDataStoreDriver {
    private static final Logger log = Logger.getLogger(StorpoolPrimaryDataStoreDriver.class);

    @Inject VolumeDao volumeDao;
    @Inject StorageManager storageMgr;
    @Inject PrimaryDataStoreDao primaryStoreDao;
    @Inject EndPointSelector selector;
    @Inject ConfigurationDao configDao;
    @Inject VMTemplatePoolDao vmTemplatePoolDao;

    @Override
    public Map<String, String> getCapabilities() {
        return null;
    }

    @Override
    public DataTO getTO(DataObject data) {
        return null;
    }

    @Override
    public DataStoreTO getStoreTO(DataStore store) {
        return null;
    }

    @Override
    public long getUsedBytes(StoragePool storagePool) {
        return 0;
    }

    @Override
    public long getUsedIops(StoragePool storagePool) {
        return 0;
    }

    @Override
    public boolean grantAccess(DataObject data, Host host, DataStore dataStore) {
        log.debug("grantAccess");
        return false;
    }

    @Override
    public void revokeAccess(DataObject data, Host host, DataStore dataStore) {
        log.debug("revokeAccess");
    }

    private void updateStoragePool(final long poolId, final long deltaUsedBytes) {
        StoragePoolVO storagePool = primaryStoreDao.findById(poolId);
        final long capacity = storagePool.getCapacityBytes();
        final long used = storagePool.getUsedBytes() + deltaUsedBytes;

        storagePool.setUsedBytes(used < 0 ? 0 : (used > capacity ? capacity : used));
        primaryStoreDao.update(poolId, storagePool);
    }

    private Long getVMInstance(long id) {
         VolumeVO volume = volumeDao.findById(id);
         return volume.getInstanceId();
    }

    protected void _completeResponse(final CreateObjectAnswer answer, final String err, final AsyncCompletionCallback<CommandResult> callback)
    {
        final CreateCmdResult res = new CreateCmdResult(null, answer);
        res.setResult(err);
        callback.complete(res);
    }

    protected void completeResponse(final DataTO result, final AsyncCompletionCallback<CommandResult> callback)
    {
        _completeResponse(new CreateObjectAnswer(result), null, callback);
    }

    protected void completeResponse(final String err, final AsyncCompletionCallback<CommandResult> callback)
    {
        _completeResponse(new CreateObjectAnswer(err), err, callback);
    }

    @Override
    public long getDataObjectSizeIncludingHypervisorSnapshotReserve(DataObject dataObject, StoragePool pool) {
        return dataObject.getSize();
    }

    @Override
    public long getBytesRequiredForTemplate(TemplateInfo templateInfo, StoragePool storagePool) {
        return 0;
    }

    @Override
    public ChapInfo getChapInfo(DataObject dataObject) {
        return null;
    }

    @Override
    public void createAsync(DataStore dataStore, DataObject data, AsyncCompletionCallback<CreateCmdResult> callback) {
        String path = null;
        String err = null;
        if (data.getType() == DataObjectType.VOLUME) {
            VolumeInfo vinfo = (VolumeInfo)data;
            String name = vinfo.getUuid();
            Long size = vinfo.getSize();
            SpConnectionDesc conn = new SpConnectionDesc(dataStore.getUuid());

            StorpoolUtil.spLog("volume: name=%s, uuid=%s, isAttached=%s vm=%s, payload=%s, template: %s", vinfo.getName(), vinfo.getUuid(), vinfo.isAttachedVM(), vinfo.getAttachedVmName(), vinfo.getpayload(), conn.getTemplateName());

            SpApiResponse resp = StorpoolUtil.volumeCreate(name, null, size, conn);
            if (resp.getError() == null) {
                path = StorpoolUtil.devPath(name);

                VolumeVO volume = volumeDao.findById(vinfo.getId());
                volume.setPoolId(dataStore.getId());
                volume.setPoolType(StoragePoolType.SharedMountPoint);
                volume.setPath(path);
                volumeDao.update(volume.getId(), volume);

                updateStoragePool(dataStore.getId(), size);
            } else {
                err = String.format("Could not create StorPool volume %s. Error: %s", name, resp.getError());
            }
        } else {
            err = String.format("Invalid object type \"%s\"  passed to createAsync", data.getType());
        }

        CreateCmdResult res = new CreateCmdResult(path, new Answer(null, err == null, err));
        res.setResult(err);
        callback.complete(res);
    }

    @Override
    public void resize(DataObject data, AsyncCompletionCallback<CreateCmdResult> callback) {
        String path = null;
        String err = null;
        ResizeVolumeAnswer answer = null;

        if (data.getType() == DataObjectType.VOLUME) {
            VolumeObject vol = (VolumeObject)data;
            StoragePool pool = (StoragePool)data.getDataStore();
            ResizeVolumePayload payload = (ResizeVolumePayload)vol.getpayload();

            final String name = StorpoolStorageAdaptor.getVolumeNameFromPath(vol.getPath());
            final long oldSize = vol.getSize();
            SpConnectionDesc conn = new SpConnectionDesc(data.getDataStore().getUuid());

            StorpoolUtil.spLog("StorpoolPrimaryDataStoreDriverImpl.resize: name=%s, uuid=%s, oldSize=%d, newSize=%s, shrinkOk=%s", vol.getName(), vol.getUuid(), oldSize, payload.newSize, payload.shrinkOk);

            SpApiResponse resp = StorpoolUtil.volumeUpdate(name, payload.newSize, payload.shrinkOk, conn);
            if (resp.getError() != null) {
                err = String.format("Could not resize StorPool volume %s. Error: %s", name, resp.getError());
            } else {
                try {
                    StorpoolResizeVolumeCommand resizeCmd = new StorpoolResizeVolumeCommand(vol.getPath(), new StorageFilerTO(pool), vol.getSize(),
                                payload.newSize, payload.shrinkOk, payload.instanceName);
                    answer = (ResizeVolumeAnswer)storageMgr.sendToPool(pool, payload.hosts, resizeCmd);

                    if (answer == null || !answer.getResult()) {
                        err = answer != null ? answer.getDetails() : "return a null answer, resize failed for unknown reason";
                    } else {
                        path = StorpoolUtil.devPath(name);

                        vol.setSize(payload.newSize);
                        vol.update();

                        updateStoragePool(vol.getPoolId(), payload.newSize - oldSize);
                    }
                } catch (Exception e) {
                    log.debug("sending resize command failed", e);
                    err = e.toString();
                }
            }

            if (err != null) {
                // try restoring volume to its initial size
                resp = StorpoolUtil.volumeUpdate(name, oldSize, true, conn);
                if (resp.getError() != null) {
                    log.debug(String.format("Could not resize StorPool volume %s back to its original size. Error: %s", name, resp.getError()));
                }
            }
        } else {
            err = String.format("Invalid object type \"%s\"  passed to resize", data.getType());
        }

        CreateCmdResult res = new CreateCmdResult(path, answer);
        res.setResult(err);
        callback.complete(res);
    }

    @Override
    public void deleteAsync(DataStore dataStore, DataObject data, AsyncCompletionCallback<CommandResult> callback) {
        String err = null;
        if (data.getType() == DataObjectType.VOLUME) {
            VolumeInfo vinfo = (VolumeInfo)data;
            String name = StorpoolStorageAdaptor.getVolumeNameFromPath(vinfo.getPath());
            if (name == null) {
                name = vinfo.getUuid();
            }
            StorpoolUtil.spLog("delete volume: name=%s, uuid=%s, isAttached=%s vm=%s, payload=%s dataStore=%s", vinfo.getName(), name, vinfo.isAttachedVM(), vinfo.getAttachedVmName(), vinfo.getpayload(), dataStore.getUuid());
            SpConnectionDesc conn = new SpConnectionDesc(dataStore.getUuid());

            SpApiResponse resp = StorpoolUtil.volumeDelete(name, conn);
            if (resp.getError() == null) {
                updateStoragePool(dataStore.getId(), - vinfo.getSize());
            } else {
                err = String.format("Could not delete StorPool volume %s. Error: %s", name, resp.getError());
            }
        } else {
            err = String.format("Invalid DataObjectType \"%s\" passed to deleteAsync", data.getType());
        }

        if (err != null) {
            log.error(err);
            StorpoolUtil.spLog(err);
        }

        CommandResult res = new CommandResult();
        res.setResult(err);
        callback.complete(res);
    }

    private void logDataObject(final String pref, DataObject data) {
        final DataStore dstore = data.getDataStore();
        String name = null;
        Long size = null;

        if (data.getType() == DataObjectType.VOLUME) {
            VolumeInfo vinfo = (VolumeInfo)data;
            name = vinfo.getName();
            size = vinfo.getSize();
        } else if (data.getType() == DataObjectType.SNAPSHOT) {
            SnapshotInfo sinfo = (SnapshotInfo)data;
            name = sinfo.getName();
            size = sinfo.getSize();
        } else if (data.getType() == DataObjectType.TEMPLATE) {
            TemplateInfo tinfo = (TemplateInfo)data;
            name = tinfo.getName();
            size = tinfo.getSize();
        }

        StorpoolUtil.spLog("%s: name=%s, size=%s, uuid=%s, type=%s, dstore=%s:%s:%s", pref, name, size, data.getUuid(), data.getType(), dstore.getUuid(), dstore.getName(), dstore.getRole());
    }

    private int getTimeout(Config cfg) {
        final String value = configDao.getValue(cfg.toString());
        return NumbersUtil.parseInt(value, Integer.parseInt(cfg.getDefaultValue()));
    }

    @Override
    public boolean canCopy(DataObject srcData, DataObject dstData) {
        return true;
    }

    @Override
    public void copyAsync(DataObject srcData, DataObject dstData, AsyncCompletionCallback<CopyCommandResult> callback) {
        // TODO: we maybe need to consider the data-stores as well (like migrate btx. different Storpool templates)
        StorpoolUtil.spLog("StorpoolPrimaryDataStoreDriverImpl.copyAsnc:");
        logDataObject("SRC", srcData);
        logDataObject("DST", dstData);

        final DataObjectType srcType = srcData.getType();
        final DataObjectType dstType = dstData.getType();
        String err = null;
        Answer answer = null;
        StorageSubSystemCommand cmd = null;

        try {
            if (srcType == DataObjectType.SNAPSHOT && dstType == DataObjectType.VOLUME) {
                // create volume from snapshot
                // TODO: currently supported only if snapshot is already present on primary
                // (which is the case for Storpool created snapshots)
                SnapshotInfo sinfo = (SnapshotInfo)srcData;
                final String snapshotName = sinfo.getUuid();

                VolumeInfo vinfo = (VolumeInfo)dstData;
                final String volumeName = vinfo.getUuid();
                final Long size = vinfo.getSize();
                SpConnectionDesc conn = new SpConnectionDesc(vinfo.getDataStore().getUuid());

                SpApiResponse resp = StorpoolUtil.volumeCreate(volumeName, snapshotName, size, conn);
                if (resp.getError() == null) {
                    updateStoragePool(dstData.getDataStore().getId(), size);

                    VolumeObjectTO to = (VolumeObjectTO)dstData.getTO();
                    to.setPath(StorpoolUtil.devPath(volumeName));
                    to.setSize(size);

                    answer = new CopyCmdAnswer(to);
                } else {
                    err = String.format("Could not create Storpool volume %s from snapshot %s. Error: %s", volumeName, snapshotName, resp.getError());
                }
            } else if (srcType == DataObjectType.SNAPSHOT && dstType == DataObjectType.SNAPSHOT) {
                // copy snapshot to secondary storage (backup snapshot)
                cmd = new StorpoolBackupSnapshotCommand(srcData.getTO(), dstData.getTO(), getTimeout(Config.BackupSnapshotWait), VirtualMachineManager.ExecuteInSequence.value());

                EndPoint ep = selector.select(srcData, dstData);
                if (ep == null) {
                    err = "No remote endpoint to send command, check if host or ssvm is down?";
                } else {
                    answer = ep.sendMessage(cmd);
                    // if error during snapshot backup, cleanup the StorPool snapshot
                    if( answer != null && !answer.getResult() ) {
                        final String snapName = ((SnapshotInfo)srcData).getUuid();
                        StorpoolUtil.spLog(String.format("Error while backing-up snapshot '%s' - cleaning up StorPool snapshot. Error: %s", snapName, answer.getDetails()));
                        SpConnectionDesc conn = new SpConnectionDesc(srcData.getDataStore().getUuid());

                        SpApiResponse resp = StorpoolUtil.snapshotDelete(snapName, conn);
                        if( resp.getError() != null ) {
                            final String err2 = String.format("Failed to cleanup StorPool snapshot '%s'. Error: %s.", snapName, resp.getError());
                            log.error(err2);
                            StorpoolUtil.spLog(err2);
                        }
                    }
                }
            } else if (srcType == DataObjectType.VOLUME && dstType == DataObjectType.TEMPLATE) {
                // create template from volume
                cmd = new CopyCommand(srcData.getTO(), dstData.getTO(), getTimeout(Config.PrimaryStorageDownloadWait), VirtualMachineManager.ExecuteInSequence.value());

                EndPoint ep = selector.select(srcData, dstData);
                if (ep == null) {
                    err = "No remote endpoint to send command, check if host or ssvm is down?";
                } else {
                    answer = ep.sendMessage(cmd);
                }
            } else if (srcType == DataObjectType.TEMPLATE && dstType == DataObjectType.TEMPLATE) {
                // copy template to primary storage
                TemplateInfo tinfo = (TemplateInfo)dstData;
                Long size = tinfo.getSize();
                if(size == null || size == 0)
                    size = 1L*1024*1024*1024;
                SpConnectionDesc conn = new SpConnectionDesc(dstData.getDataStore().getUuid());

                String name = conn.getTemplateName() + "-" + tinfo.getUuid();

                SpApiResponse resp = StorpoolUtil.volumeCreate(name, null, size, conn);
                if (resp.getError() != null) {
                    err = String.format("Could not create Storpool volume for CS template %s. Error: %s", name, resp.getError());
                } else {
                    TemplateObjectTO dstTO = (TemplateObjectTO)dstData.getTO();
                    dstTO.setPath(StorpoolUtil.devPath(name));
                    dstTO.setSize(size);

                    cmd = new StorpoolDownloadTemplateCommand(srcData.getTO(), dstTO, getTimeout(Config.PrimaryStorageDownloadWait), VirtualMachineManager.ExecuteInSequence.value());

                    EndPoint ep = selector.select(srcData, dstData);
                    if (ep == null) {
                        err = "No remote endpoint to send command, check if host or ssvm is down?";
                    } else {
                        answer = ep.sendMessage(cmd);
                    }

                    if (answer != null && answer.getResult()) {
                        // successfully downloaded template to primary storage
                        SpApiResponse resp2 = StorpoolUtil.volumeFreeze(name, conn);
                        if (resp2.getError() != null) {
                            err = String.format("Could not freeze Storpool volume %s. Error: %s", name, resp2.getError());
                        }
                    } else {
                        err = answer != null ? answer.getDetails() : "Unknown error while downloading template. Null answer returned.";
                    }

                    if (err != null) {
                        SpApiResponse resp3 = StorpoolUtil.volumeDelete(name, conn);
                        if (resp3.getError() != null) {
                            log.warn(String.format("Could not clean-up Storpool volume %s. Error: %s", name, resp3.getError()));
                        }
                    }
                }
            } else if (srcType == DataObjectType.TEMPLATE && dstType == DataObjectType.VOLUME) {
                // create volume from template on Storpool PRIMARY
                TemplateInfo tinfo = (TemplateInfo)srcData;

                VolumeInfo vinfo = (VolumeInfo)dstData;
                VMTemplateStoragePoolVO templStoragePoolVO = vmTemplatePoolDao.findByPoolTemplate(vinfo.getPoolId(), tinfo.getId());
                final String parentName = StorpoolStorageAdaptor.getVolumeNameFromPath(templStoragePoolVO.getInstallPath());
                final String name = vinfo.getUuid();
                SpConnectionDesc conn = new SpConnectionDesc(vinfo.getDataStore().getUuid());

                if (StorpoolUtil.volumeExists(name, conn)) {
                    // reinstall template: delete current volume, then re-create
                    SpApiResponse resp = StorpoolUtil.volumeDelete(name, conn);
                    if (resp.getError() == null) {
                        updateStoragePool(dstData.getDataStore().getId(), - vinfo.getSize());
                    } else {
                        err = String.format("Could not delete old Storpool volume %s. Error: %s", name, resp.getError());
                    }
                }

                if (err == null) {
                    long size = vinfo.getSize();
                    long snapshotSize = StorpoolUtil.snapshotSize(parentName, conn);
                    if( size < snapshotSize )
                    {
                        StorpoolUtil.spLog(String.format("provided size is too small for snapshot. Provided %d, snapshot %d. Using snapshot size", size, snapshotSize));
                        size = snapshotSize;
                    }
                    StorpoolUtil.spLog(String.format("volume size is: %d", size));
                    SpApiResponse resp = StorpoolUtil.volumeCreate(name, parentName, size, conn);
                    if (resp.getError() == null) {
                        updateStoragePool(dstData.getDataStore().getId(), vinfo.getSize());

                        VolumeObjectTO to = (VolumeObjectTO)vinfo.getTO();
                        to.setSize(vinfo.getSize());
                        to.setPath(StorpoolUtil.devPath(name));

                        answer = new CopyCmdAnswer(to);
                    } else {
                        err = String.format("Could not create Storpool volume %s. Error: %s", name, resp.getError());
                    }
                }
            } else if (srcType == DataObjectType.VOLUME && dstType == DataObjectType.VOLUME) {
//                if( srcData.getDataStore().getRole().isImageStore() ) {
                if( !(srcData.getDataStore().getDriver() instanceof StorpoolPrimaryDataStoreDriver ) ) {
                    // copy "VOLUME" to primary storage
                    VolumeInfo vinfo = (VolumeInfo)dstData;
                    String name = vinfo.getUuid();
                    Long size = vinfo.getSize();
                    if(size == null || size == 0)
                        size = 1L*1024*1024*1024;
                    SpConnectionDesc conn = new SpConnectionDesc(dstData.getDataStore().getUuid());
                    VolumeInfo srcInfo = (VolumeInfo) srcData;
                    Long vmId = srcInfo.getInstanceId();

                    SpApiResponse resp = StorpoolUtil.volumeCreateWithTags(name, null, size, vmId, conn);
                    if (resp.getError() != null) {
                        err = String.format("Could not create Storpool volume for CS template %s. Error: %s", name, resp.getError());
                    } else {
                        //updateVolume(dstData.getId());
                        VolumeObjectTO dstTO = (VolumeObjectTO)dstData.getTO();
                        dstTO.setPath(StorpoolUtil.devPath(name));
                        dstTO.setSize(size);

                        cmd = new StorpoolDownloadVolumeCommand(srcData.getTO(), dstTO, getTimeout(Config.PrimaryStorageDownloadWait), VirtualMachineManager.ExecuteInSequence.value());

                        EndPoint ep = selector.select(srcData, dstData);

                        if( ep == null) {
                            StorpoolUtil.spLog("select(srcData, dstData) returned NULL. trying srcOnly");
                            ep = selector.select(srcData); // Storpool is zone
                        }
                        if (ep == null) {
                            err = "No remote endpoint to send command, check if host or ssvm is down?";
                        } else {
                            StorpoolUtil.spLog("Sending command to %s", ep.getHostAddr());
                            answer = ep.sendMessage(cmd);

                            if (answer != null && answer.getResult()) {
                                // successfully downloaded volume to primary storage
                            } else {
                                err = answer != null ? answer.getDetails() : "Unknown error while downloading volume. Null answer returned.";
                            }
                        }

                        if (err != null) {
                            SpApiResponse resp3 = StorpoolUtil.volumeDelete(name, conn);
                            if (resp3.getError() != null) {
                               log.warn(String.format("Could not clean-up Storpool volume %s. Error: %s", name, resp3.getError()));
                            }
                        }
                    }
                } else {
                    // download volume - first copies to secondary
                    VolumeObjectTO srcTO = (VolumeObjectTO)srcData.getTO();
                    StorpoolUtil.spLog("StorpoolPrimaryDataStoreDriverImpl.copyAsnc SRC path=%s ", srcTO.getPath());
                    StorpoolUtil.spLog("StorpoolPrimaryDataStoreDriverImpl.copyAsnc DST canonicalName=%s ", dstData.getDataStore().getClass().getCanonicalName());
                    PrimaryDataStoreTO checkStoragePool = (PrimaryDataStoreTO)dstData.getTO().getDataStore();
                    SpConnectionDesc conn = new SpConnectionDesc(srcData.getDataStore().getUuid());
                    final String name = StorpoolStorageAdaptor.getVolumeNameFromPath(srcTO.getPath());
                    final String tmpSnapName = String.format("tmp-for-download-%s", name);
                    StorpoolUtil.spLog("StorpoolPrimaryDataStoreDriverImpl.copyAsnc DST tmpSnapName=%s ,srcUUID=%s", tmpSnapName, srcTO.getUuid());
                    final SpApiResponse resp = StorpoolUtil.volumeSnapshot(name, tmpSnapName, conn);
                    if (resp.getError() == null) {
                        if (checkStoragePool.getPoolType().equals(StoragePoolType.SharedMountPoint)) {
                            String baseOn = StorpoolStorageAdaptor.getVolumeNameFromPath(srcTO.getPath());
                            String volumeName = dstData.getUuid();
                            StorpoolUtil.spLog("StorpoolPrimaryDataStoreDriverImpl.copyAsnc volumeName=%s, baseOn=%s", volumeName,baseOn );
                            final SpApiResponse response = StorpoolUtil.volumeCopy(volumeName, baseOn, conn);
                            VolumeObjectTO to = (VolumeObjectTO)srcData.getTO();
                            to.setSize(srcData.getSize());
                            to.setPath(StorpoolUtil.devPath(volumeName));
                            StorpoolUtil.spLog("StorpoolPrimaryDataStoreDriverImpl.copyAsnc DST to=%s", to);

                            answer = new CopyCmdAnswer(to);
                        }else {
                            srcTO.setPath(StorpoolUtil.devPath(tmpSnapName));

                            cmd = new StorpoolCopyVolumeToSecondaryCommand(srcTO, dstData.getTO(), getTimeout(Config.CopyVolumeWait), VirtualMachineManager.ExecuteInSequence.value());

                            StorpoolUtil.spLog("StorpoolPrimaryDataStoreDriverImpl.copyAsnc command=%s ", cmd);

                            EndPoint ep = selector.select(srcData, dstData);
                            StorpoolUtil.spLog("selector.select(srcData, dstData) ", ep);
                            if( ep == null ) {
                                ep = selector.select(dstData);
                                StorpoolUtil.spLog("selector.select(srcData) ", ep);
                            }

                            if (ep == null) {
                                err = "No remote endpoint to send command, check if host or ssvm is down?";
                            } else {
                                answer = ep.sendMessage(cmd);
                                StorpoolUtil.spLog("Answer: details=%s, result=%s", answer.getDetails(), answer.getResult());
                            }
                        }

                        final SpApiResponse resp2 = StorpoolUtil.snapshotDelete(tmpSnapName, conn);
                        if (resp2.getError() != null) {
                            final String err2 = String.format("Failed to delete temporary StorPool snapshot %s. Error: %s", tmpSnapName, resp2.getError());
                            log.error(err2);
                            StorpoolUtil.spLog(err2);
                        }
                    } else {
                        err = String.format("Failed to create temporary StorPool snapshot while trying to download volume %s (uuid %s). Error: %s", srcTO.getName(), srcTO.getUuid(), resp.getError());
                    }
                }
            } else {
                err = String.format("Unsupported copy operation from %s (type %s) to %s (type %s)", srcData.getUuid(), srcType, dstData.getUuid(), dstType);
            }
        } catch (Exception e) {
            StorpoolUtil.spLog(String.format("Caught exception: %s", e.toString()));
            err = e.toString();
        }

        if (answer != null && !answer.getResult()) {
            err = answer.getDetails();
        }

        if (err != null) {
            StorpoolUtil.spLog(err);

            log.error(err);
            answer = new Answer(cmd, false, err);
        }

        CopyCommandResult res = new CopyCommandResult(null, answer);
        res.setResult(err);
        callback.complete(res);
    }

    @Override
    public void takeSnapshot(SnapshotInfo snapshot, AsyncCompletionCallback<CreateCmdResult> callback) {
        String snapshotName = snapshot.getUuid();
        VolumeInfo vinfo = snapshot.getBaseVolume();
        String volumeName = StorpoolStorageAdaptor.getVolumeNameFromPath(vinfo.getPath());
        SpConnectionDesc conn = new SpConnectionDesc(vinfo.getDataStore().getUuid());
        Long vmId = vinfo.getInstanceId();
        if (volumeName != null) {
            StorpoolUtil.spLog("StorpoolPrimaryDataStoreDriver.takeSnapshot volumename=%s vmInstance=%s",volumeName, vmId);
        }else {
            throw new UnsupportedOperationException("The path should be: " + StorpoolUtil.SP_DEV_PATH);
        }

        StorpoolUtil.spLog("StorpoolPrimaryDataStoreDriverImpl.takeSnapshot: snapshot: name=%s, uuid=%s, volume: name=%s, uuid=%s", snapshot.getName(), snapshot.getUuid(), vinfo.getName(), vinfo.getUuid());

        CreateObjectAnswer answer = null;
        String err = null;

        SpApiResponse resp = StorpoolUtil.volumeSnapshot(volumeName, snapshotName, conn);

        if (resp.getError() != null) {
            err = String.format("Could not snapshot StorPool volume %s. Error %s", volumeName, resp.getError());
            answer = new CreateObjectAnswer(err);
        } else {
            SnapshotObjectTO snapTo = (SnapshotObjectTO)snapshot.getTO();
            snapTo.setPath(StorpoolUtil.devPath(snapshotName));
            answer = new CreateObjectAnswer(snapTo);
            StorpoolUtil.snapshotUpadateTags(snapshotName, vmId, conn);
        }

        CreateCmdResult res = new CreateCmdResult(null, answer);
        res.setResult(err);
        callback.complete(res);
    }

    @Override
    public void revertSnapshot(final SnapshotInfo snapshot, final SnapshotInfo snapshotOnPrimaryStore, final AsyncCompletionCallback<CommandResult> callback) {
        final String snapshotName = snapshot.getUuid();
        final VolumeInfo vinfo = snapshot.getBaseVolume();
        final String volumeName = StorpoolStorageAdaptor.getVolumeNameFromPath(vinfo.getPath());
        SpConnectionDesc conn = new SpConnectionDesc(vinfo.getDataStore().getUuid());
        final String backupSnapshotName = volumeName + "_to_be_removed";
        final Long size = snapshot.getSize();
        StorpoolUtil.spLog("StorpoolPrimaryDataStoreDriverImpl.revertSnapshot: snapshot: name=%s, uuid=%s, volume: name=%s, uuid=%s", snapshot.getName(), snapshot.getUuid(), vinfo.getName(), vinfo.getUuid());

        // Ignore the error that will almost certainly occur - no such snapshot
        StorpoolUtil.snapshotDelete(backupSnapshotName, conn);
        SpApiResponse resp = StorpoolUtil.volumeSnapshot(volumeName, backupSnapshotName, conn);
        if (resp.getError() != null) {
            final String err = String.format("Could not revert StorPool volume %s to the %s snapshot: could not create a temporary snapshot for the old volume: error %s", vinfo.getName(), snapshot.getName(), resp.getError());
            completeResponse(err, callback);
            return;
        }

        resp = StorpoolUtil.volumeDelete(volumeName, conn);
        if (resp.getError() != null) {
            StorpoolUtil.snapshotDelete(backupSnapshotName, conn);
            final String err = String.format("Could not revert StorPool volume %s to the %s snapshot: could not delete the old volume: error %s", vinfo.getName(), snapshot.getName(), resp.getError());
            completeResponse(err, callback);
            return;
        }

        resp = StorpoolUtil.volumeCreateWithTags(volumeName, snapshotName, size, vinfo.getInstanceId(), conn);
        if (resp.getError() != null) {
            // Mmm, try to restore it first...
            String err = String.format("Could not revert StorPool volume %s to the %s snapshot: could not create the new volume: error %s", vinfo.getName(), snapshot.getName(), resp.getError());
            resp = StorpoolUtil.volumeCreateWithTags(volumeName, backupSnapshotName, size, vinfo.getInstanceId(), conn);
            if (resp.getError() != null)
                err = String.format("%s.  Also, could not even restore the old volume: %s", err, resp.getError());
            else
                StorpoolUtil.snapshotDelete(backupSnapshotName, conn);
            completeResponse(err, callback);
            return;
        }

        StorpoolUtil.snapshotDelete(backupSnapshotName, conn);

        final VolumeObjectTO to = (VolumeObjectTO)vinfo.getTO();
        to.setSize(size);
        to.setPath(StorpoolUtil.devPath(volumeName));
        completeResponse(to, callback);
    }
}
