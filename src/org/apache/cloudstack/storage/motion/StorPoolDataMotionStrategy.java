package org.apache.cloudstack.storage.motion;

import java.util.List;
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
import com.cloud.configuration.Config;
import com.cloud.dc.ClusterVO;
import com.cloud.dc.dao.ClusterDao;
import com.cloud.host.Host;
import com.cloud.host.HostVO;
import com.cloud.host.dao.HostDao;
import com.cloud.storage.DataStoreRole;
import com.cloud.storage.VMTemplateDetailVO;
import com.cloud.storage.dao.SnapshotDetailsDao;
import com.cloud.storage.dao.SnapshotDetailsVO;
import com.cloud.storage.dao.VMTemplateDetailsDao;
import com.cloud.utils.NumbersUtil;
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
    private ConfigurationDao configDao;
    @Inject
    private EndPointSelector selector;
    @Inject
    private TemplateDataStoreDao templStoreDao;
    @Inject
    ClusterDao clusterDao;
    @Inject
    HostDao hostDao;
    @Inject
    SnapshotDetailsDao snapshotDetailsDao;
    @Inject
    SnapshotDataStoreDao snapshotStoreDao;
    @Inject
    VMTemplateDetailsDao vmTemplateDetailsDao;

    @Override
    public StrategyPriority canHandle(DataObject srcData, DataObject destData) {
        DataObjectType srcType = srcData.getType();
        DataObjectType dstType = destData.getType();
        if (srcType == DataObjectType.SNAPSHOT && dstType == DataObjectType.TEMPLATE && BackupManager.BypassSecondaryStorage.value()) {
            SnapshotInfo sinfo = (SnapshotInfo)srcData;
            String snapshotName= StorPoolHelper.getSnapshotName(sinfo.getId(), sinfo.getUuid(), snapshotStoreDao, snapshotDetailsDao);
            StorpoolUtil.spLog("StorPoolDataMotionStrategy.canHandle snapshot name=%s", snapshotName);
            if(snapshotName != null && StorpoolUtil.snapshotExists(snapshotName, new SpConnectionDesc(srcData.getDataStore().getUuid()))){
                return StrategyPriority.HIGHEST;
            }
            SnapshotDetailsVO snapshotDetails = snapshotDetailsDao.findDetail(sinfo.getId(), sinfo.getUuid());
            if (snapshotDetails != null) {
                snapshotDetailsDao.remove(snapshotDetails.getId());
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

        String parentName = StorPoolHelper.getSnapshotName(sInfo.getId(), sInfo.getUuid(), snapshotStoreDao, snapshotDetailsDao);
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
            SnapshotDetailsVO snapshotDetails = snapshotDetailsDao.findDetail(sInfo.getId(), sInfo.getUuid());

            snapshot.setPath(snapshotDetails.getValue());
            String value = configDao.getValue(Config.BackupSnapshotWait.toString());
            Command backupSnapshot = new StorpoolBackupTemplateFromSnapshotCommand(snapshot, template,
                    NumbersUtil.parseInt(value, Integer.parseInt(Config.BackupSnapshotWait.getDefaultValue())), VirtualMachineManager.ExecuteInSequence.value());

            final String snapName = ((SnapshotInfo) srcData).getUuid();
            try {
            //final String snapName = StorpoolStorageAdaptor.getVolumeNameFromPath(((SnapshotInfo) srcData).getPath(), true);
                Long clusterId = findClusterId(parentName);
                EndPoint ep2 = clusterId != null ? RemoteHostEndPoint.getHypervisorHostEndPoint(findHostByCluster(clusterId)) : selector.select(srcData, destData);
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

    private Long findClusterId(String globalId) {
        List<ClusterVO> clusterVo = clusterDao.listAll();
        if (clusterVo.size() == 1) {
            StorpoolUtil.spLog("There is only one cluster, sending backup to secondary command");
            return null;
        }
        for (ClusterVO clusterVO2 : clusterVo) {
            if (globalId != null && BackupManager.StorPoolClusterId.valueIn(clusterVO2.getId()) != null && globalId.contains(BackupManager.StorPoolClusterId.valueIn(clusterVO2.getId()).toString())) {
                StorpoolUtil.spLog("StorPool globalId=%s cluster id=%s, cluster value=%s", globalId, BackupManager.StorPoolClusterId.valueIn(clusterVO2.getId()), globalId.equals(BackupManager.StorPoolClusterId.valueIn(clusterVO2.getId()).toString()));
                return clusterVO2.getId();
            }
        }
        throw new CloudRuntimeException("Could not find the right clusterId. To use snapshot backup to secondary for each CloudStack cluster in its settings set the value of StorPool's cluster-id in \"sp.cluster.id\".");
    }

    private HostVO findHostByCluster(Long clusterId) {
        List<HostVO> host = hostDao.findByClusterId(clusterId);
        return host != null ? host.get(0) : null;
    }

    private void updateVmStoreTemplate(Long id, DataStoreRole role, String path) {
        TemplateDataStoreVO templ = templStoreDao.findByTemplate(id, role);
        templ.setLocalDownloadPath(path);
        templStoreDao.persist(templ);
    }
}
