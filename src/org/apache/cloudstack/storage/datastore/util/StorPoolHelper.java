package org.apache.cloudstack.storage.datastore.util;

import java.sql.PreparedStatement;

import org.apache.cloudstack.storage.datastore.db.SnapshotDataStoreDao;
import org.apache.cloudstack.storage.datastore.db.SnapshotDataStoreVO;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil.SpApiResponse;
import org.apache.cloudstack.storage.to.VolumeObjectTO;

import com.cloud.hypervisor.kvm.storage.StorpoolStorageAdaptor;
import com.cloud.storage.DataStoreRole;
import com.cloud.storage.VolumeVO;
import com.cloud.storage.dao.SnapshotDetailsDao;
import com.cloud.storage.dao.SnapshotDetailsVO;
import com.cloud.storage.dao.VolumeDao;
import com.cloud.utils.db.TransactionLegacy;

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
        SnapshotDetailsVO details = new SnapshotDetailsVO(id, uuid, snapshotName, true);
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
}
