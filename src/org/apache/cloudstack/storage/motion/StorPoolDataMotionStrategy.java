package org.apache.cloudstack.storage.motion;

import java.util.Map;

import javax.inject.Inject;

import org.apache.cloudstack.engine.subsystem.api.storage.CopyCommandResult;
import org.apache.cloudstack.engine.subsystem.api.storage.DataMotionStrategy;
import org.apache.cloudstack.engine.subsystem.api.storage.DataObject;
import org.apache.cloudstack.engine.subsystem.api.storage.DataStore;
import org.apache.cloudstack.engine.subsystem.api.storage.DataStoreManager;
import org.apache.cloudstack.engine.subsystem.api.storage.EndPoint;
import org.apache.cloudstack.engine.subsystem.api.storage.EndPointSelector;
import org.apache.cloudstack.engine.subsystem.api.storage.SnapshotDataFactory;
import org.apache.cloudstack.engine.subsystem.api.storage.SnapshotInfo;
import org.apache.cloudstack.engine.subsystem.api.storage.StrategyPriority;
import org.apache.cloudstack.engine.subsystem.api.storage.VolumeInfo;
import org.apache.cloudstack.framework.async.AsyncCompletionCallback;
import org.apache.cloudstack.framework.config.dao.ConfigurationDao;
import org.apache.cloudstack.storage.RemoteHostEndPoint;
import org.apache.cloudstack.storage.command.CopyCmdAnswer;
import org.apache.cloudstack.storage.datastore.db.SnapshotDataStoreDao;
import org.apache.cloudstack.storage.datastore.db.TemplateDataStoreDao;
import org.apache.cloudstack.storage.datastore.db.TemplateDataStoreVO;
import org.apache.cloudstack.storage.datastore.util.StorPoolHelper;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil.SpApiResponse;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil.SpConnectionDesc;
import org.apache.cloudstack.storage.snapshot.BackupManager;
import org.apache.cloudstack.storage.to.SnapshotObjectTO;
import org.apache.cloudstack.storage.to.TemplateObjectTO;
import org.apache.log4j.Logger;
import org.springframework.stereotype.Component;

import com.cloud.agent.api.Command;
import com.cloud.agent.api.storage.StorpoolBackupTemplateFromSnapshotCommand;
import com.cloud.agent.api.to.DataObjectType;
import com.cloud.agent.api.to.VirtualMachineTO;
import com.cloud.dc.dao.ClusterDao;
import com.cloud.host.Host;
import com.cloud.host.dao.HostDao;
import com.cloud.storage.DataStoreRole;
import com.cloud.storage.VMTemplateDetailVO;
import com.cloud.storage.dao.SnapshotDetailsDao;
import com.cloud.storage.dao.SnapshotDetailsVO;
import com.cloud.storage.dao.VMTemplateDetailsDao;
import com.cloud.utils.exception.CloudRuntimeException;
import com.cloud.vm.VirtualMachineManager;

@Component
public class StorPoolDataMotionStrategy implements DataMotionStrategy{
    private static final Logger log = Logger.getLogger(StorPoolDataMotionStrategy.class);

    @Inject
    private SnapshotDataFactory _snapshotDataFactory;
    @Inject
    private DataStoreManager _dataStore;
    @Inject
    private ConfigurationDao _configDao;
    @Inject
    private EndPointSelector _selector;
    @Inject
    private TemplateDataStoreDao _templStoreDao;
    @Inject
    private ClusterDao _clusterDao;
    @Inject
    private HostDao _hostDao;
    @Inject
    private SnapshotDetailsDao _snapshotDetailsDao;
    @Inject
    private VMTemplateDetailsDao vmTemplateDetailsDao;
    @Inject
    private SnapshotDataStoreDao _snapshotStoreDao;

    @Override
    public StrategyPriority canHandle(DataObject srcData, DataObject destData) {
        DataObjectType srcType = srcData.getType();
        DataObjectType dstType = destData.getType();
        if (srcType == DataObjectType.SNAPSHOT && dstType == DataObjectType.TEMPLATE && BackupManager.BypassSecondaryStorage.value()) {
            SnapshotInfo sinfo = (SnapshotInfo)srcData;
            String snapshotName= StorPoolHelper.getSnapshotName(sinfo.getId(), sinfo.getUuid(), _snapshotStoreDao, _snapshotDetailsDao);
            StorpoolUtil.spLog("StorPoolDataMotionStrategy.canHandle snapshot name=%s", snapshotName);
            if(snapshotName != null && StorpoolUtil.snapshotExists(snapshotName, new SpConnectionDesc(srcData.getDataStore().getUuid()))){
                return StrategyPriority.HIGHEST;
            }
            SnapshotDetailsVO snapshotDetails = _snapshotDetailsDao.findDetail(sinfo.getId(), sinfo.getUuid());
            if (snapshotDetails != null) {
                _snapshotDetailsDao.remove(snapshotDetails.getId());
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
        String volumeName = "";

        String parentName = StorPoolHelper.getSnapshotName(sInfo.getId(), sInfo.getUuid(), _snapshotStoreDao, _snapshotDetailsDao);
        //TODO volume tags cs - template
        SpApiResponse res = StorpoolUtil.volumeCreate(name, parentName, sInfo.getSize(), null, "no", "template", null, conn);
        CopyCmdAnswer answer = null;
        String err = null;
        if (res.getError() != null) {
            log.debug(String.format("Could not create volume from snapshot with ID=%s", snapshot.getId()));
            StorpoolUtil.spLog("Volume create failed with error=%s", res.getError().getDescr());
            err = res.getError().getDescr();
        } else {
            volumeName = StorpoolUtil.getNameFromResponse(res, true);
            SnapshotDetailsVO snapshotDetails = _snapshotDetailsDao.findDetail(sInfo.getId(), sInfo.getUuid());

            snapshot.setPath(snapshotDetails.getValue());
            Command backupSnapshot = new StorpoolBackupTemplateFromSnapshotCommand(snapshot, template,
                    StorPoolHelper.getTimeout(StorPoolHelper.BackupSnapshotWait, _configDao), VirtualMachineManager.ExecuteInSequence.value());

            try {
            //final String snapName = StorpoolStorageAdaptor.getVolumeNameFromPath(((SnapshotInfo) srcData).getPath(), true);
                Long clusterId = StorPoolHelper.findClusterIdByGlobalId(parentName, _clusterDao);
                EndPoint ep2 = clusterId != null ? RemoteHostEndPoint.getHypervisorHostEndPoint(StorPoolHelper.findHostByCluster(clusterId, _hostDao)) : _selector.select(srcData, destData);
                if (ep2 == null) {
                    err = "No remote endpoint to send command, check if host or ssvm is down?";
                } else {
                    answer = (CopyCmdAnswer) ep2.sendMessage(backupSnapshot);
                    if (answer != null && answer.getResult()) {
                        SpApiResponse resSnapshot = StorpoolUtil.volumeFreeze(volumeName, conn);
                        if (resSnapshot.getError() != null) {
                            log.debug(String.format("Could not snapshot volume with ID=%s", snapshot.getId()));
                            StorpoolUtil.spLog("Volume freeze failed with error=%s", resSnapshot.getError().getDescr());
                            err = resSnapshot.getError().getDescr();
                            StorpoolUtil.volumeDelete(volumeName, conn);
                        }
                        else {
                            updateVmStoreTemplate(template.getId(), template.getDataStore().getRole(), StorpoolUtil.devPath(StorpoolUtil.getNameFromResponse(res, false)));
                        }
                    }else {
                        err = "Could not copy template to secondary " + answer.getResult();
                        StorpoolUtil.volumeDelete(StorpoolUtil.getNameFromResponse(res, true), conn);
                    }
                }
            }catch (CloudRuntimeException e) {
                err = e.getMessage();
            }
        }
        vmTemplateDetailsDao.persist(new VMTemplateDetailVO(template.getId(), StorpoolUtil.SP_STORAGE_POOL_ID, String.valueOf(vInfo.getDataStore().getId()), false));
        StorpoolUtil.spLog("StorPoolDataMotionStrategy.copyAsync Creating snapshot=%s for StorPool template=%s", volumeName, conn.getTemplateName());
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

    private void updateVmStoreTemplate(Long id, DataStoreRole role, String path) {
        TemplateDataStoreVO templ = _templStoreDao.findByTemplate(id, role);
        templ.setLocalDownloadPath(path);
        _templStoreDao.persist(templ);
    }
}
