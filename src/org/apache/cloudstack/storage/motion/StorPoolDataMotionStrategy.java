package org.apache.cloudstack.storage.motion;

import java.sql.PreparedStatement;
import java.util.Map;

import javax.inject.Inject;

import org.apache.cloudstack.engine.subsystem.api.storage.CopyCommandResult;
import org.apache.cloudstack.engine.subsystem.api.storage.DataMotionStrategy;
import org.apache.cloudstack.engine.subsystem.api.storage.DataObject;
import org.apache.cloudstack.engine.subsystem.api.storage.DataStore;
import org.apache.cloudstack.engine.subsystem.api.storage.DataStoreManager;
import org.apache.cloudstack.engine.subsystem.api.storage.SnapshotDataFactory;
import org.apache.cloudstack.engine.subsystem.api.storage.SnapshotInfo;
import org.apache.cloudstack.engine.subsystem.api.storage.StrategyPriority;
import org.apache.cloudstack.engine.subsystem.api.storage.VolumeInfo;
import org.apache.cloudstack.framework.async.AsyncCompletionCallback;
import org.apache.cloudstack.storage.command.CopyCmdAnswer;
import org.apache.cloudstack.storage.datastore.db.PrimaryDataStoreDao;
import org.apache.cloudstack.storage.datastore.db.StoragePoolVO;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil.SpApiResponse;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil.SpConnectionDesc;
import org.apache.cloudstack.storage.snapshot.BackupManager;
import org.apache.cloudstack.storage.to.SnapshotObjectTO;
import org.apache.cloudstack.storage.to.TemplateObjectTO;
import org.apache.log4j.Logger;
import org.springframework.stereotype.Component;

import com.cloud.agent.api.Answer;
import com.cloud.agent.api.to.DataObjectType;
import com.cloud.agent.api.to.VirtualMachineTO;
import com.cloud.host.Host;
import com.cloud.storage.SnapshotVO;
import com.cloud.storage.VolumeVO;
import com.cloud.storage.dao.SnapshotDao;
import com.cloud.storage.dao.VolumeDao;
import com.cloud.utils.db.TransactionLegacy;

@Component
public class StorPoolDataMotionStrategy implements DataMotionStrategy{
    private static final Logger log = Logger.getLogger(StorPoolDataMotionStrategy.class);

    @Inject
    private PrimaryDataStoreDao _primaryDataStoreDao;
    @Inject
    private SnapshotDao _snapshotDao;
    @Inject
    private VolumeDao _volumeDao;
    @Inject
    private SnapshotDataFactory _snapshotDataFactory;
    @Inject
    private DataStoreManager _dataStore;

    private static final String UPDATE_VM_TEMPLATE = "UPDATE vm_template SET direct_download = 1 WHERE id = ?";

    @Override
    public StrategyPriority canHandle(DataObject srcData, DataObject destData) {
        DataObjectType srcType = srcData.getType();
        DataObjectType dstType = destData.getType();
        if (srcType == DataObjectType.SNAPSHOT && dstType == DataObjectType.TEMPLATE && BackupManager.BypassSecondaryStorage.value()) {
            SnapshotVO snapshot = _snapshotDao.findById(srcData.getTO().getId());
            VolumeVO volume = _volumeDao.findByIdIncludingRemoved(snapshot.getVolumeId());
            StoragePoolVO storage = _primaryDataStoreDao.findById(volume.getPoolId());
            if (storage.getStorageProviderName().equals(StorpoolUtil.SP_PROVIDER_NAME)) {
                return StrategyPriority.HIGHEST;
            }
        }
        return StrategyPriority.CANT_HANDLE;
    }

    @Override
    public StrategyPriority canHandle(Map<VolumeInfo, DataStore> volumeMap, Host srcHost, Host destHost) {
        return StrategyPriority.CANT_HANDLE;
    }

    @Override
    public void copyAsync(DataObject srcData, DataObject destData, Host destHost,
            AsyncCompletionCallback<CopyCommandResult> callback) {
        SnapshotObjectTO snapshot = (SnapshotObjectTO) srcData.getTO();
        TemplateObjectTO template = (TemplateObjectTO) destData.getTO();
        DataStore store = _dataStore.getDataStore(snapshot.getVolume().getDataStore().getUuid(), snapshot.getVolume().getDataStore().getRole());
        SnapshotInfo sInfo = _snapshotDataFactory.getSnapshot(snapshot.getId(), store);

        VolumeInfo vInfo = sInfo.getBaseVolume();
        SpConnectionDesc conn = new SpConnectionDesc(vInfo.getDataStore().getUuid());
        String name = template.getUuid();
        String parentName = srcData.getUuid();

        Long size = (template.getSize() == null || template.getSize() < sInfo.getSize()) ? sInfo.getSize() : template.getSize() ;
        SpApiResponse res = StorpoolUtil.volumeCreate(name, parentName, size, conn);
        Answer answer = null;
        String err = null;
        if (res.getError() != null) {
            log.debug(String.format("Could not create volume from snapshot with ID=%s", snapshot.getId()));
            StorpoolUtil.spLog("Volume create failed with error=%s", res.getError().getDescr());
            err = res.getError().getDescr();
            answer = new CopyCmdAnswer(err);
        }else {
            String path  = StorpoolUtil.devPath(name);
            template.setPath(path);
            template.setSize(size);
            updateVmTemplate(template.getId());
            SpApiResponse resSnapshot = StorpoolUtil.volumeFreeze(name, conn);
            if (resSnapshot.getError() != null) {
                log.debug(String.format("Could not snapshot volume with ID=%s", snapshot.getId()));
                StorpoolUtil.spLog("Volume freeze failed with error=%s", resSnapshot.getError().getDescr());
                err = resSnapshot.getError().getDescr();
                answer = new CopyCmdAnswer(err);
            }else {
                answer = new CopyCmdAnswer(template);
            }
        }
        StorpoolUtil.spLog("StorPoolDataMotionStrategy.copyAsync Creating snapshot=%s for StorPool template=%s", name, conn.getTemplateName());
        final CopyCommandResult cmd = new CopyCommandResult(null, answer);
        cmd.setResult(err);
        callback.complete(cmd);
    }

    @Override
    public void copyAsync(Map<VolumeInfo, DataStore> volumeMap, VirtualMachineTO vmTo, Host srcHost, Host destHost,
            AsyncCompletionCallback<CopyCommandResult> callback) {
        StorpoolUtil.spLog("Unsupport operation to migrate virtual machine=%s from host=%s to host%s", vmTo.getName(), srcHost, destHost );
        throw new UnsupportedOperationException("Unsupport operation to migrate virtual machine with volumes to another host");
    }

    private void updateVmTemplate(Long id) {
        TransactionLegacy txn = TransactionLegacy.currentTxn();
        PreparedStatement pstmt = null;
        String sql = UPDATE_VM_TEMPLATE;
        try {
            pstmt = txn.prepareAutoCloseStatement(sql);
            pstmt.setLong(1, id);
            pstmt.executeUpdate();
        } catch (Exception ex) {
            log.error("error updating vm_template", ex);
        }
    }

}
