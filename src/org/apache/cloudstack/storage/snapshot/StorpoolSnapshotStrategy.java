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
package org.apache.cloudstack.storage.snapshot;

import javax.inject.Inject;

import org.apache.cloudstack.engine.subsystem.api.storage.SnapshotInfo;
import org.apache.cloudstack.engine.subsystem.api.storage.StrategyPriority;
import org.apache.cloudstack.storage.datastore.db.PrimaryDataStoreDao;
import org.apache.cloudstack.storage.datastore.db.SnapshotDataStoreDao;
import org.apache.cloudstack.storage.datastore.db.StoragePoolVO;
import org.apache.cloudstack.storage.datastore.util.StorPoolHelper;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil.SpApiResponse;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil.SpConnectionDesc;
import org.apache.log4j.Logger;
import org.springframework.stereotype.Component;

import com.cloud.storage.Snapshot;
import com.cloud.storage.SnapshotVO;
import com.cloud.storage.VolumeVO;
import com.cloud.storage.dao.SnapshotDao;
import com.cloud.storage.dao.SnapshotDetailsDao;
import com.cloud.storage.dao.SnapshotDetailsVO;
import com.cloud.storage.dao.VolumeDao;
import com.cloud.utils.fsm.NoTransitionException;


@Component
public class StorpoolSnapshotStrategy extends XenserverSnapshotStrategy {
    private static final Logger log = Logger.getLogger(StorpoolSnapshotStrategy.class);

    @Inject
    private SnapshotDao _snapshotDao;
    @Inject
    private PrimaryDataStoreDao _primaryDataStoreDao;
    @Inject
    private VolumeDao _volumeDao;
    @Inject
    private SnapshotDataStoreDao _snapshotStoreDao;
    @Inject
    private SnapshotDetailsDao _snapshotDetailsDao;

    @Override
    public SnapshotInfo backupSnapshot(SnapshotInfo snapshotInfo) {
        SnapshotObject snapshotObj = (SnapshotObject) snapshotInfo;
        try {
            snapshotObj.processEvent(Snapshot.Event.BackupToSecondary);
            snapshotObj.processEvent(Snapshot.Event.OperationSucceeded);
        } catch (NoTransitionException ex) {
            StorpoolUtil.spLog("Failed to change state: " + ex.toString());
            try {
                snapshotObj.processEvent(Snapshot.Event.OperationFailed);
            } catch (NoTransitionException ex2) {
                StorpoolUtil.spLog("Failed to change state: " + ex2.toString());
            }
        }
        return snapshotInfo;
    }

    @Override
    public boolean deleteSnapshot(Long snapshotId) {

        final SnapshotVO snapshotVO = _snapshotDao.findById(snapshotId);
        VolumeVO volume = _volumeDao.findByIdIncludingRemoved(snapshotVO.getVolumeId());
        String name = StorPoolHelper.getSnapshotName(snapshotId, snapshotVO.getUuid(), _snapshotStoreDao, _snapshotDetailsDao);
        boolean res = false;
        // clean-up snapshot from Storpool storage pools
        StoragePoolVO storage = _primaryDataStoreDao.findById(volume.getPoolId());
        if (storage.getStorageProviderName().equals(StorpoolUtil.SP_PROVIDER_NAME)) {
            SpConnectionDesc conn = new SpConnectionDesc(storage.getUuid());
            SpApiResponse resp = StorpoolUtil.snapshotDelete(name, conn);
            if (resp.getError() != null) {
                 final String err = String.format("Failed to clean-up Storpool snapshot %s. Error: %s", name, resp.getError());
                 log.error(err);
                 StorpoolUtil.spLog(err);
            }else {
                SnapshotDetailsVO snapshotDetails = _snapshotDetailsDao.findDetail(snapshotId, snapshotVO.getUuid());
                if (snapshotDetails != null) {
                    _snapshotDetailsDao.removeDetails(snapshotId);
                }
                 res = super.deleteSnapshot(snapshotId);
                 StorpoolUtil.spLog("StorpoolSnapshotStrategy.deleteSnapshot: executed successfuly=%s, snapshot uuid=%s, name=%s", res, snapshotVO.getUuid(), name);
            }
        }

        return res;
    }

    @Override
    public StrategyPriority canHandle(Snapshot snapshot, SnapshotOperation op) {
        StorpoolUtil.spLog("StorpoolSnapshotStrategy.canHandle: snapshot=%s, uuid=%s, op=%s", snapshot.getName(), snapshot.getUuid(), op);

        if (op != SnapshotOperation.DELETE) {
            return StrategyPriority.CANT_HANDLE;
        }

        VolumeVO volume = _volumeDao.findByIdIncludingRemoved(snapshot.getVolumeId());
        StoragePoolVO storage = _primaryDataStoreDao.findById(volume.getPoolId());
        String name = StorPoolHelper.getSnapshotName(snapshot.getId(), snapshot.getUuid(), _snapshotStoreDao, _snapshotDetailsDao);
        if (storage.getStorageProviderName().equals(StorpoolUtil.SP_PROVIDER_NAME)) {
            SpConnectionDesc conn = new SpConnectionDesc(storage.getUuid());
            if (StorpoolUtil.snapshotExists(name, conn)) {
                StorpoolUtil.spLog("StorpoolSnapshotStrategy.canHandle: globalId=%s", name);

                return StrategyPriority.HIGHEST;
            }
        }
        SnapshotDetailsVO snapshotDetails = _snapshotDetailsDao.findDetail(snapshot.getId(), snapshot.getUuid());
        if (snapshotDetails != null) {
            _snapshotDetailsDao.remove(snapshotDetails.getId());
        }
        return StrategyPriority.CANT_HANDLE;
    }

}
