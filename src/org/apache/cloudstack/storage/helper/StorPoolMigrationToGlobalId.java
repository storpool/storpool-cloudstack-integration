package org.apache.cloudstack.storage.helper;

import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import javax.inject.Inject;
import javax.naming.ConfigurationException;

import org.apache.cloudstack.engine.subsystem.api.storage.ObjectInDataStoreStateMachine;
import org.apache.cloudstack.framework.config.dao.ConfigurationDao;
import org.apache.cloudstack.managed.context.ManagedContextRunnable;
import org.apache.cloudstack.storage.datastore.db.PrimaryDataStoreDao;
import org.apache.cloudstack.storage.datastore.db.StoragePoolDetailVO;
import org.apache.cloudstack.storage.datastore.db.StoragePoolDetailsDao;
import org.apache.cloudstack.storage.datastore.db.StoragePoolVO;
import org.apache.cloudstack.storage.datastore.db.TemplateDataStoreDao;
import org.apache.cloudstack.storage.datastore.db.TemplateDataStoreVO;
import org.apache.cloudstack.storage.datastore.util.StorPoolHelper;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil.SpConnectionDesc;
import org.apache.cloudstack.storage.snapshot.BackupManager;
import org.apache.cloudstack.storage.to.VolumeObjectTO;
import org.apache.cloudstack.storage.vmsnapshot.VMSnapshotHelper;
import org.apache.log4j.Logger;

import com.cloud.api.ApiServer;
import com.cloud.hypervisor.kvm.storage.StorpoolStorageAdaptor;
import com.cloud.storage.VMTemplateDetailVO;
import com.cloud.storage.VMTemplateStoragePoolVO;
import com.cloud.storage.Volume;
import com.cloud.storage.VolumeDetailVO;
import com.cloud.storage.VolumeVO;
import com.cloud.storage.dao.SnapshotDetailsDao;
import com.cloud.storage.dao.SnapshotDetailsVO;
import com.cloud.storage.dao.VMTemplateDetailsDao;
import com.cloud.storage.dao.VMTemplatePoolDao;
import com.cloud.storage.dao.VolumeDao;
import com.cloud.storage.dao.VolumeDetailsDao;
import com.cloud.utils.component.ComponentContext;
import com.cloud.utils.component.ManagerBase;
import com.cloud.utils.concurrency.NamedThreadFactory;
import com.cloud.utils.crypt.DBEncryptionUtil;
import com.cloud.utils.db.QueryBuilder;
import com.cloud.utils.db.SearchCriteria.Op;
import com.cloud.utils.db.TransactionLegacy;
import com.cloud.utils.exception.CloudRuntimeException;
import com.cloud.vm.snapshot.VMSnapshotDetailsVO;
import com.cloud.vm.snapshot.VMSnapshotVO;
import com.cloud.vm.snapshot.dao.VMSnapshotDao;
import com.cloud.vm.snapshot.dao.VMSnapshotDetailsDao;
import com.google.gson.JsonArray;

public class StorPoolMigrationToGlobalId extends ManagerBase {
    private static Logger log = Logger.getLogger(StorPoolMigrationToGlobalId.class);
    @Inject
    private VolumeDao volumeDao;
    @Inject
    private VMSnapshotDao vmSnapshotDao;
    @Inject
    private PrimaryDataStoreDao storageDao;
    @Inject
    private VMSnapshotHelper vmSnapshotHelper;
    @Inject
    private SnapshotDetailsDao snapshotDetailsDao;
    @Inject
    private VMSnapshotDetailsDao vmSnapshotDetailsDao;
    @Inject
    private VMTemplatePoolDao vmTemplatePoolDao;
    @Inject
    private TemplateDataStoreDao vmTemplateDataStoreDao;
    @Inject
    private VMTemplateDetailsDao vmTemplateDetailsDao;
    @Inject
    private ConfigurationDao configurationDao;
    @Inject
    private VolumeDetailsDao volumeDetailsDao;
    @Inject
    private StoragePoolDetailsDao storagePoolDetailsDao;

    private ExecutorService _executorService;
    private Map<String, ArrayList<String>> storpoolVolumes = new HashMap<>();
    private Map<String, ArrayList<String>> storpoolSnapshots = new HashMap<>();
    private static final String LOG_FILE = "/var/log/cloudstack/management/storpool-migrate-to-globalids";
    private static final String SELECT_READY_SNAPSHOTS_NO_ON_SNAPSHOT_DETAILS = "SELECT S.id, S.uuid \n" +
            "FROM    `cloud`.`snapshots` S\n" +
            "LEFT JOIN \n" +
            "`cloud`.`snapshot_details` D\n" +
            "ON      S.uuid = D.name\n" +
            "WHERE D.name is null and S.status=\"BackedUp\"";

    public StorPoolMigrationToGlobalId() {
        setRunLevel(RUN_LEVEL_FRAMEWORK_BOOTSTRAP);
    }

    @Override
    public boolean configure(String name, Map<String, Object> params) throws ConfigurationException {
        init();
        return true;
    }

    public void init() {
        if (!BackupManager.IsMigrationCompleted.value()) {
            ComponentContext.getComponent(ApiServer.class);
            List<StoragePoolVO> poolList = listStorPoolStorage();

            if (poolList != null && poolList.size() > 0) {
                StorPoolHelper.appendLogger(log, LOG_FILE, "update");
                for (StoragePoolVO storagePoolVO : poolList) {
                    String spTemplate = storagePoolVO.getUuid();
                    SpConnectionDesc conn = null;
                    try {
                        conn = StorpoolUtil.getSpConnection(spTemplate, storagePoolVO.getId(), storagePoolDetailsDao, storageDao);;
                    } catch (Exception e) {
                        throw e;
                    }
                    JsonArray volumesList = StorpoolUtil.volumesList(conn);
                    storpoolVolumes.putAll(getStorPoolNamesAndGlobalIds(volumesList));

                    JsonArray snapshotsList = StorpoolUtil.snapshotsList(conn);
                    storpoolSnapshots.putAll(getStorPoolNamesAndGlobalIds(snapshotsList));
                }
                Map<VMSnapshotVO, List<VolumeVO>> vmSnapshotsVO = getVmSnapshotsOnStorPool(vmSnapshotDao.listAll());
                Map<Long, String> activeSnapshots = listReadySnapshots();
                List<TemplateDataStoreVO> templatesStoreRefs = listStorpoolStoreTemplates();
                List<VMTemplateStoragePoolVO> templatesOnPool = listStorpoolPoolTemplates();
                List<VolumeVO> volumes = listStorpoolVolumes();
                if (vmSnapshotsVO.size() > 0 || templatesStoreRefs.size() > 0
                        || templatesOnPool.size() > 0 || volumes.size() > 0 || activeSnapshots.size() > 0) {
                    _executorService = Executors.newCachedThreadPool(new NamedThreadFactory("StorPoolMigrationToGlobalId"));
                    _executorService.submit(new VolumesUpdater(storpoolVolumes, volumes));
                    _executorService.submit(new VmSnapshotsUpdater(storpoolSnapshots, vmSnapshotsVO, poolList));
                    _executorService.submit(new ActiveSnapshotsUpdater(storpoolSnapshots, activeSnapshots, poolList));
                    _executorService.submit(new TemplatesOnStoreUpdater(storpoolSnapshots, templatesStoreRefs, poolList));
                    _executorService.submit(new TemplatesOnPoolUpdater(storpoolSnapshots, templatesOnPool));
                    _executorService.shutdown();
                }
            }
            configurationDao.update(BackupManager.IsMigrationCompleted.key(), DBEncryptionUtil.encrypt(Boolean.TRUE.toString()));
        }
    }

    private class VmSnapshotsUpdater extends ManagedContextRunnable {
        private Map<String, ArrayList<String>> clone;
        private Map<VMSnapshotVO, List<VolumeVO>> vmSnapshotsVO;
        private List<StoragePoolVO> poolList;
        public VmSnapshotsUpdater(Map<String, ArrayList<String>> realMap, Map<VMSnapshotVO, List<VolumeVO>> vmSnapshotsVO, List<StoragePoolVO> poolList) {
            this.clone = new HashMap<>(realMap);
            this.vmSnapshotsVO = vmSnapshotsVO;
            this.poolList = poolList;
        }

        @Override
        protected void runInContext() {
            log.info(String.format("%s group snapshots has to be updated with their globalIds", vmSnapshotsVO.size()));

            for (Map.Entry<VMSnapshotVO, List<VolumeVO>> element : vmSnapshotsVO.entrySet()) {
                for (VolumeVO volume : element.getValue()) {
                    String snapshotName = element.getKey().getUuid() + "_" + volume.getUuid();
                    ArrayList<String> globalIdAndTemplate = this.clone.get(snapshotName);
                    if (globalIdAndTemplate != null) {
                        String name = globalIdAndTemplate.get(0);
                        for (StoragePoolVO storagePoolVO : poolList) {
                            StoragePoolDetailVO detail = storagePoolDetailsDao.findDetail(storagePoolVO.getId(), StorpoolUtil.SP_TEMPLATE);
                            if (detail != null && detail.getValue().equals(globalIdAndTemplate.get(1))) {
                                VMSnapshotDetailsVO details = new VMSnapshotDetailsVO(element.getKey().getId(),
                                        StorpoolUtil.SP_STORAGE_POOL_ID, String.valueOf(storagePoolVO.getId()), false);
                                vmSnapshotDetailsDao.persist(details);
                                break;
                            }
                        }
                        VMSnapshotDetailsVO details = new VMSnapshotDetailsVO(element.getKey().getId(),
                                volume.getUuid(), StorpoolUtil.devPath(name), false);
                        vmSnapshotDetailsDao.persist(details);
                        log.info(String.format("Group snapshot was updated. Old name was %s and the new name is %s for volume with id=%s", snapshotName, name, volume.getId()));
                    } else {
                        log.info(String.format("Snapshot of a group with name=%s was not found in StorPool", snapshotName));
                    }
                }
            }
            log.info("StorPool's group snapshots were added into DB table \"vm_snapshot_details\" with their globalIds of each attached volume");
        }
    }

    private class ActiveSnapshotsUpdater extends ManagedContextRunnable {
        private Map<String, ArrayList<String>> clone;
        private Map<Long, String> snapshots;
        private List<StoragePoolVO> poolList;

        public ActiveSnapshotsUpdater(Map<String, ArrayList<String>> realMap, Map<Long, String> snapshots, List<StoragePoolVO> poolList) {
            this.clone = new HashMap<>(realMap);
            this.snapshots = snapshots;
            this.poolList = poolList;
        }

        @Override
        protected void runInContext() {

            for (Map.Entry<Long, String> snapshot : snapshots.entrySet()) {
                String oldPath = snapshot.getValue();
                ArrayList<String> globalIdAndTemplate = this.clone.get(oldPath);
                if (globalIdAndTemplate != null) {
                    String path = globalIdAndTemplate.get(0);
                    for (StoragePoolVO storagePoolVO : poolList) {
                        StoragePoolDetailVO detail = storagePoolDetailsDao.findDetail(storagePoolVO.getId(), StorpoolUtil.SP_TEMPLATE);
                        if (detail != null && detail.getValue().equals(globalIdAndTemplate.get(1))) {
                            SnapshotDetailsVO details = new SnapshotDetailsVO(snapshot.getKey(), StorpoolUtil.SP_STORAGE_POOL_ID, String.valueOf(storagePoolVO.getId()), false);
                            snapshotDetailsDao.persist(details);
                            break;
                        }
                    }
                    String newPath = StorpoolUtil.devPath(path);
                    SnapshotDetailsVO details = new SnapshotDetailsVO(snapshot.getKey(), oldPath, newPath, false);
                    snapshotDetailsDao.persist(details);

                    log.info(String.format("StorPool's snapshot was added in \"snapshot_details\" DB table. The old path was %s and the new path is %s",
                            oldPath, newPath));
                }
            }
            log.info("StorPool's snapshots were updated in db table \"snapshot_details\" with path to globalId");
        }
    }

    private class TemplatesOnStoreUpdater extends ManagedContextRunnable {
        private Map<String, ArrayList<String>> clone;
        private List<TemplateDataStoreVO> templatesStoreRefs;
        private List<StoragePoolVO> poolList;

        public TemplatesOnStoreUpdater(Map<String, ArrayList<String>> realMap, List<TemplateDataStoreVO> templatesStoreRefs, List<StoragePoolVO> poolList) {
            this.clone = new HashMap<>(realMap);
            this.templatesStoreRefs = templatesStoreRefs;
            this.poolList = poolList;
        }

        @Override
        protected void runInContext() {
            log.info(String.format("%s templates in DB table \"template_store_ref\" has to be updated with their globalid",
                    templatesStoreRefs.size()));

            for (TemplateDataStoreVO template : templatesStoreRefs) {
                String oldPath = template.getLocalDownloadPath();
                String key = StorpoolStorageAdaptor.getVolumeNameFromPath(oldPath, false);
                ArrayList<String> globalIdAndTemplate = clone.get(key);
                if (globalIdAndTemplate != null) {
                    String newPath = StorpoolUtil.devPath(globalIdAndTemplate.get(0));
                    vmTemplateDataStoreDao.acquireInLockTable(template.getId());
                    template.setLocalDownloadPath(newPath);
                    vmTemplateDataStoreDao.update(template.getId(), template);
                    vmTemplateDataStoreDao.releaseFromLockTable(template.getId());
                    for (StoragePoolVO storagePoolVO : poolList) {
                        StoragePoolDetailVO detail = storagePoolDetailsDao.findDetail(storagePoolVO.getId(), StorpoolUtil.SP_TEMPLATE);
                        if (detail != null && detail.getValue().equals(globalIdAndTemplate.get(1))) {
                        VMTemplateDetailVO templateDetails = new VMTemplateDetailVO(template.getId(), StorpoolUtil.SP_STORAGE_POOL_ID, String.valueOf(storagePoolVO.getId()),
                                false);
                        vmTemplateDetailsDao.persist(templateDetails);
                        }
                    }
                    log.info(String.format("StorPool's snapshot for a template in DB table \"template_store_ref\" was updated. Old path was %s and the new path is %s.", oldPath, newPath));
                } else {
                    log.info(String.format("Store template with id=%s in DB table \"template_store_ref\" was not found as a snapshot in StorPool", template.getId()));
                }
            }
            log.info("StorPool's snapshots of templates were updated in db table \"template_store_ref\" with path to globalId's path");
        }
    }

    private class TemplatesOnPoolUpdater extends ManagedContextRunnable {
        private Map<String, ArrayList<String>> clone;
        private List<VMTemplateStoragePoolVO> templatesOnPool;

        public TemplatesOnPoolUpdater(Map<String, ArrayList<String>> realMap, List<VMTemplateStoragePoolVO> templatesOnPool) {
            this.clone = new HashMap<>(realMap);
            this.templatesOnPool = templatesOnPool;
        }

        @Override
        protected void runInContext() {

            log.info(String.format("%s templates in DB table \"template_spool_ref\" has to be updated with their globalid",
                    templatesOnPool.size()));
            for (VMTemplateStoragePoolVO template : templatesOnPool) {
                String oldPath = template.getLocalDownloadPath();
                String key = StorpoolStorageAdaptor.getVolumeNameFromPath(oldPath, false);
                ArrayList<String> globalIdAndTemplate = clone.get(key);
                if (globalIdAndTemplate != null) {
                    String newPath = StorpoolUtil.devPath(globalIdAndTemplate.get(0));
                    vmTemplatePoolDao.acquireInLockTable(template.getId());
                    template.setLocalDownloadPath(newPath);
                    vmTemplatePoolDao.update(template.getId(), template);
                    vmTemplatePoolDao.releaseFromLockTable(template.getId());
                    log.info(String.format("StorPool's snapshot for a template in DB table \"template_spool_ref\" was updated. Old path was %s and the new path is %s.", oldPath, newPath));
                }else {
                    log.info(String.format("Pool template with id=%s in DB table \"template_spool_ref\" was not found as a snapshot in StorPool", template.getId()));
                }
            }
            log.info("StorPool's snapshots of templates were updated in db table \"template_spool_ref\" with path to globalId's path");
        }
    }

    private class VolumesUpdater extends ManagedContextRunnable {
        private Map<String, ArrayList<String>> clone;
        private List<VolumeVO> volumes;

        public VolumesUpdater(Map<String, ArrayList<String>> realMap, List<VolumeVO> volumes) {
            this.clone = new HashMap<>(realMap);
            this.volumes = volumes;
        }

        @Override
        protected void runInContext() {
            log.info(String.format("%s StorPool volume has to be updated with their globalIds", volumes.size()));

            for (VolumeVO volume : volumes) {
                String oldPath = volume.getPath();
                String key = StorpoolStorageAdaptor.getVolumeNameFromPath(oldPath, false);
                ArrayList<String> listWithGlobaIds = clone.get(key);
                if (listWithGlobaIds != null) {
                    String path = listWithGlobaIds.get(0);
                    volumeDao.acquireInLockTable(volume.getId());
                    volume.setPath(StorpoolUtil.devPath(path));
                    volumeDao.update(volume.getId(), volume);
                    volumeDao.releaseFromLockTable(volume.getId());
                    volumeDetailsDao.persist(new VolumeDetailVO(volume.getId(), StorpoolUtil.SP_PROVIDER_NAME, oldPath, false));
                    log.info(String.format("StorPool's volume was updated with globalId. Old path=%s, new path=%s.", oldPath, volume.getPath()));
                } else {
                    log.info(String.format("Volume with id=%s was not found as a volume in StorPool", volume.getId()));
                }
            }
            log.info("StorPool's volumes were updated in db table \"volumes\" with path to globalIds");
        }
    }

    private List<StoragePoolVO> listStorPoolStorage() {
        return storageDao.findPoolsByProvider(StorpoolUtil.SP_PROVIDER_NAME);
    }

    private Map<String, ArrayList<String>> getStorPoolNamesAndGlobalIds(JsonArray arr) {
        Map<String, ArrayList<String>> map = new HashMap<>();
        for (int i = 0; i < arr.size(); i++) {
            String name = arr.get(i).getAsJsonObject().get("name").getAsString();
            String glid = arr.get(i).getAsJsonObject().get("globalId").getAsString();
            String templateName = arr.get(i).getAsJsonObject().get("templateName").getAsString();
            if ((!name.startsWith("~") || !name.startsWith("*")) && !name.contains("@")) {
                map.put(name, new ArrayList<>(Arrays.asList(glid, templateName)));
            }
        }
        return map;
    }

    private Map<VMSnapshotVO, List<VolumeVO>> getVmSnapshotsOnStorPool(List<VMSnapshotVO> vmSnapshots) {
        Map<VMSnapshotVO, List<VolumeVO>> vmSnapshotsOnStorPool = new HashMap<>();
        for (VMSnapshotVO vmSnapshot : vmSnapshots) {
            List<VolumeObjectTO> volumeTOs = vmSnapshotHelper.getVolumeTOList(vmSnapshot.getVmId());
            List<VolumeVO> volumesOnStorPool = new ArrayList<VolumeVO>();
            for (VolumeObjectTO volumeObjectTO : volumeTOs) {
                VolumeVO volumeVO = volumeDao.findById(volumeObjectTO.getId());
                StoragePoolVO storagePoolVO = storageDao.findById(volumeVO.getPoolId());
                VMSnapshotDetailsVO vmDetail = vmSnapshotDetailsDao.findDetail(vmSnapshot.getId(), volumeVO.getUuid());
                if (storagePoolVO.getStorageProviderName().equals(StorpoolUtil.SP_PROVIDER_NAME) && vmDetail == null) {
                    volumesOnStorPool.add(volumeVO);
                }
            }
            if (!volumesOnStorPool.isEmpty()) {
                vmSnapshotsOnStorPool.put(vmSnapshot, volumesOnStorPool);
            }
        }
        return vmSnapshotsOnStorPool;
    }

    private List<TemplateDataStoreVO> listStorpoolStoreTemplates() {
        QueryBuilder<TemplateDataStoreVO> sc = QueryBuilder.create(TemplateDataStoreVO.class);
        sc.and(sc.entity().getState(), Op.EQ, ObjectInDataStoreStateMachine.State.Ready);
        sc.and(sc.entity().getLocalDownloadPath(), Op.LIKE, StorpoolUtil.SP_OLD_PATH + "%");
        return sc.list();
    }

    private Map<Long, String> listReadySnapshots() {
        final TransactionLegacy txn = TransactionLegacy.currentTxn();
        PreparedStatement pstmt = null;
        Map<Long, String> result = new HashMap<>();
        try {
            pstmt = txn.prepareAutoCloseStatement(SELECT_READY_SNAPSHOTS_NO_ON_SNAPSHOT_DETAILS);

            final ResultSet rs = pstmt.executeQuery();
            while (rs.next()) {
                result.put(rs.getLong("id"), rs.getString("uuid"));
            }
            return result;
        } catch (final SQLException e) {
            throw new CloudRuntimeException("DB Exception on: " + pstmt, e);
        } catch (final Throwable e) {
            throw new CloudRuntimeException("Caught: " + pstmt, e);
        }
//        QueryBuilder<SnapshotVO> sc = QueryBuilder.create(SnapshotVO.class);
//        sc.and(sc.entity().getState(), Op.EQ, Snapshot.State.BackedUp);
//        return sc.list();
    }

    private List<VMTemplateStoragePoolVO> listStorpoolPoolTemplates() {
        QueryBuilder<VMTemplateStoragePoolVO> sc = QueryBuilder.create(VMTemplateStoragePoolVO.class);
        sc.and(sc.entity().getState(), Op.EQ, ObjectInDataStoreStateMachine.State.Ready);
        sc.and(sc.entity().getLocalDownloadPath(), Op.LIKE, StorpoolUtil.SP_OLD_PATH + "%");
        return sc.list();
    }

    private List<VolumeVO> listStorpoolVolumes() {
        QueryBuilder<VolumeVO> sc = QueryBuilder.create(VolumeVO.class);
        sc.and(sc.entity().getState(), Op.EQ, Volume.State.Ready);
        sc.and(sc.entity().getPath(), Op.LIKE, StorpoolUtil.SP_OLD_PATH + "%");
        return sc.list();
    }

    private String getStoragePoolName(String url) {
        String[] urlSplit = url.split(";");
        if (urlSplit.length == 1 && !urlSplit[0].contains("=")) {
            return url;
        } else {
            for (String kv : urlSplit) {
                String[] toks = kv.split("=");
                if (toks.length != 2)
                    continue;
                switch (toks[0]) {
                    case "SP_TEMPLATE":
                        return toks[1];
                }
            }
        }
        return "";
    }
}
