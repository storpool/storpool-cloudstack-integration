package org.apache.cloudstack.storage.datastore.util;

import java.sql.PreparedStatement;
import java.io.IOException;
import java.sql.Timestamp;
import java.text.SimpleDateFormat;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.apache.cloudstack.storage.datastore.db.SnapshotDataStoreDao;
import org.apache.cloudstack.storage.datastore.db.SnapshotDataStoreVO;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil.SpApiResponse;
import org.apache.cloudstack.storage.snapshot.BackupManager;
import org.apache.cloudstack.storage.to.VolumeObjectTO;
import org.apache.log4j.Appender;
import org.apache.log4j.Logger;
import org.apache.log4j.PatternLayout;
import org.apache.log4j.RollingFileAppender;

import com.cloud.dc.ClusterDetailsDao;
import com.cloud.dc.ClusterDetailsVO;
import com.cloud.dc.ClusterVO;
import com.cloud.dc.dao.ClusterDao;
import com.cloud.host.HostVO;
import com.cloud.host.dao.HostDao;
import com.cloud.hypervisor.kvm.storage.StorpoolStorageAdaptor;
import com.cloud.server.ResourceTag;
import com.cloud.server.ResourceTag.ResourceObjectType;
import com.cloud.storage.DataStoreRole;
import com.cloud.storage.VolumeVO;
import com.cloud.storage.dao.SnapshotDetailsDao;
import com.cloud.storage.dao.SnapshotDetailsVO;
import com.cloud.storage.dao.VolumeDao;
import com.cloud.utils.db.TransactionLegacy;
import com.cloud.tags.dao.ResourceTagDao;
import com.cloud.utils.exception.CloudRuntimeException;
import com.cloud.vm.VMInstanceVO;
import com.cloud.vm.dao.VMInstanceDao;

public class StorPoolHelper {
    private static final String UPDATE_SNAPSHOT_DETAILS_VALUE = "UPDATE `cloud`.`snapshot_details` SET value=? WHERE id=?";
    private static final String UPDATE_VOLUME_DETAILS_NAME = "UPDATE `cloud`.`volume_details` SET name=? WHERE id=?";

    public static void updateVolumeInfo(VolumeObjectTO volumeObjectTO, Long size, SpApiResponse resp, VolumeDao volumeDao) {
        String volumePath = StorpoolUtil.devPath(StorpoolUtil.getNameFromResponse(resp, false));
        VolumeVO volume = volumeDao.findById(volumeObjectTO.getId());
        if(volume != null) {
            volumeObjectTO.setSize(size);
            volumeObjectTO.setPath(volumePath);
            volume.setSize(size);
            volume.setPath(volumePath);
            volumeDao.update(volumeObjectTO.getId(), volume);
        }
    }

    // If volume is deleted, CloudStack removes records of snapshots created on Primary storage only in database.
    //That's why we keep information in snapshot_details table, about all snapshots created in StorPool and we can operate with them
    public static void addSnapshotDetails(final Long id, final String uuid,final String snapshotName, SnapshotDetailsDao snapshotDetailsDao) {
        SnapshotDetailsVO details = new SnapshotDetailsVO(id, uuid, snapshotName, false);
        snapshotDetailsDao.persist(details);
    }

    public static String getSnapshotName(Long snapshotId, String snapshotUuid, SnapshotDataStoreDao snapshotStoreDao, SnapshotDetailsDao snapshotDetailsDao) {
        SnapshotDataStoreVO snap = snapshotStoreDao.findBySnapshot(snapshotId, DataStoreRole.Primary);

        SnapshotDetailsVO snapshotDetails = snapshotDetailsDao.findDetail(snapshotId, snapshotUuid);
        if (snapshotDetails != null) {
            return StorpoolStorageAdaptor.getVolumeNameFromPath(snapshotDetails.getValue(), true);
        }else if (snap != null) {
            addSnapshotDetails(snapshotId, snapshotUuid, snap.getInstallPath(), snapshotDetailsDao);
            return StorpoolStorageAdaptor.getVolumeNameFromPath(snap.getInstallPath(), true);
        }else{
            return snapshotUuid;
        }
    }

    public static void updateSnapshotDetailsValue(Long id, String valueOrName, String snapshotOrVolume) {
        TransactionLegacy txn = TransactionLegacy.currentTxn();
        PreparedStatement pstmt = null;
        try {
            String sql = null;
            if (snapshotOrVolume.equals("snapshot")) {
                sql = UPDATE_SNAPSHOT_DETAILS_VALUE;
            }else if (snapshotOrVolume.equals("volume")) {
                sql = UPDATE_VOLUME_DETAILS_NAME;
            } else {
                StorpoolUtil.spLog("Could not update snapshot detail with id=%s", id);
            }
            if (sql != null) {
                pstmt = txn.prepareAutoCloseStatement(sql);
                pstmt.setString(1, valueOrName);
                pstmt.setLong(2, id);
                pstmt.executeUpdate();
                txn.commit();
            }
        } catch (Exception e) {
            txn.rollback();
            StorpoolUtil.spLog("Could not update snapshot detail with id=%s", id);
        }
    }

    public static String getVcPolicyTag(Long vmId, ResourceTagDao resourceTagDao) {
        if (vmId != null) {
            ResourceTag tag = resourceTagDao.findByKey(vmId, ResourceObjectType.UserVm, StorpoolUtil.SP_VC_POLICY);
            if (tag != null) {
                return tag.getValue();
            }
        }
        return null;
    }

    public static String getVMInstanceUUID(Long id, VMInstanceDao vmInstanceDao) {
        if (id != null) {
            VMInstanceVO vmInstance = vmInstanceDao.findById(id);
            if (vmInstance != null) {
                return vmInstance.getUuid();
            }
        }
        return null;
    }

    public static Map<String, String> addStorPoolTags(String name, String vmUuid, String csTag, String vcPolicy){
        Map<String, String> tags = new HashMap<>();
        tags.put("uuid", name);
        tags.put("cvm", vmUuid);
        tags.put(StorpoolUtil.SP_VC_POLICY, vcPolicy);
        if (csTag != null) {
            tags.put("cs", csTag);
        }
        return tags;
    }

    //Initialize custom logger for updated volume and snapshots
    public static void appendLogger(Logger log, String filePath, String kindOfLog) {
        Appender appender = null;
        PatternLayout patternLayout = new PatternLayout();
        patternLayout.setConversionPattern("%d{YYYY-MM-dd HH:mm:ss.SSS}  %m%n");
        SimpleDateFormat sdf = new SimpleDateFormat("yyyyMMddHHmmss");
        Timestamp timestamp = new Timestamp(System.currentTimeMillis());
        String path = filePath + "-" + sdf.format(timestamp) + ".log";
        try {
            appender = new RollingFileAppender(patternLayout, path);
            log.setAdditivity(false);
            log.addAppender(appender);
        } catch (IOException e) {
            e.printStackTrace();
        }
        if (kindOfLog.equals("update")) {
            StorpoolUtil.spLog("You can find information about volumes and snapshots, which will be updated in Database with their globalIs in %s log file", path);
        }else if (kindOfLog.equals("abandon")) {
            StorpoolUtil.spLog("You can find information about volumes and snapshots, for which CloudStack doesn't have information in %s log file", path);
        }
    }

    public static void setSpClusterIdIfNeeded(long hostId, String clusterId, ClusterDao clusterDao, HostDao hostDao, ClusterDetailsDao clusterDetails) {
        HostVO host = hostDao.findById(hostId);
        if (host != null && host.getClusterId() != null) {
            ClusterVO cluster = clusterDao.findById(host.getClusterId());
            ClusterDetailsVO clusterDetailsVo = clusterDetails.findDetail(cluster.getId(), BackupManager.StorPoolClusterId.key());
            if (clusterDetailsVo == null) {
                clusterDetails.persist(new ClusterDetailsVO(cluster.getId(), BackupManager.StorPoolClusterId.key(), clusterId));
            } else if (clusterDetailsVo.getValue() == null || !clusterDetailsVo.getValue().equals(clusterId)) {
                clusterDetailsVo.setValue(clusterId);
                clusterDetails.update(clusterDetailsVo.getId(), clusterDetailsVo);
            }
        }
    }

    public static Long findClusterIdByGlobalId(String globalId, ClusterDao clusterDao) {
        List<ClusterVO> clusterVo = clusterDao.listAll();
        if (clusterVo.size() == 1) {
            StorpoolUtil.spLog("There is only one cluster, sending backup to secondary command");
            return null;
        }
        for (ClusterVO clusterVO2 : clusterVo) {
            if (globalId != null && BackupManager.StorPoolClusterId.valueIn(clusterVO2.getId()) != null && globalId.contains(BackupManager.StorPoolClusterId.valueIn(clusterVO2.getId()).toString())) {
                StorpoolUtil.spLog("Found cluster with id=%s for object with globalId=%s", clusterVO2.getId(), globalId);
                return clusterVO2.getId();
            }
        }
        throw new CloudRuntimeException("Could not find the right clusterId. to send command. To use snapshot backup to secondary for each CloudStack cluster in its settings set the value of StorPool's cluster-id in \"sp.cluster.id\".");
    }

    public static HostVO findHostByCluster(Long clusterId, HostDao hostDao) {
        List<HostVO> host = hostDao.findByClusterId(clusterId);
        return host != null ? host.get(0) : null;
    }
}
