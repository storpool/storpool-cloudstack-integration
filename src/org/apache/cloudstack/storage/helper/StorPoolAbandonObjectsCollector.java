package org.apache.cloudstack.storage.helper;

import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

import javax.inject.Inject;

import org.apache.cloudstack.framework.config.ConfigKey;
import org.apache.cloudstack.framework.config.Configurable;
import org.apache.cloudstack.managed.context.ManagedContextRunnable;
import org.apache.cloudstack.storage.datastore.db.PrimaryDataStoreDao;
import org.apache.cloudstack.storage.datastore.db.StoragePoolVO;
import org.apache.cloudstack.storage.datastore.util.StorPoolHelper;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil.SpConnectionDesc;
import org.apache.log4j.Logger;

import com.cloud.utils.component.ManagerBase;
import com.cloud.utils.concurrency.NamedThreadFactory;
import com.cloud.utils.db.DB;
import com.cloud.utils.db.Transaction;
import com.cloud.utils.db.TransactionCallbackNoReturn;
import com.cloud.utils.db.TransactionLegacy;
import com.cloud.utils.db.TransactionStatus;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

public class StorPoolAbandonObjectsCollector extends ManagerBase implements Configurable {
    private static Logger log = Logger.getLogger(StorPoolAbandonObjectsCollector.class);
    @Inject
    private PrimaryDataStoreDao storagePoolDao;

    private ScheduledExecutorService _volumeTagsUpdateExecutor;
    private static final String ABANDON_LOG = "/var/log/cloudstack/management/storpool-abandoned-objects";


    static final ConfigKey<Integer> volumeCheckupTagsInterval = new ConfigKey<Integer>("Advanced", Integer.class,
            "storpool.volume.tags.checkup", "86400",
            "Minimal interval (in seconds) to check and report if StorPool volume exists in CloudStack volumes database",
            false);
    static final ConfigKey<Integer> snapshotCheckupTagsInterval = new ConfigKey<Integer>("Advanced", Integer.class,
            "storpool.snapshot.tags.checkup", "86400",
            "Minimal interval (in seconds) to check and report if StorPool snapshot exists in CloudStack snapshots database",
            false);

    @Override
    public String getConfigComponentName() {
        return StorPoolAbandonObjectsCollector.class.getSimpleName();
    }

    @Override
    public ConfigKey<?>[] getConfigKeys() {
        return new ConfigKey<?>[] { volumeCheckupTagsInterval, snapshotCheckupTagsInterval };
    }

    @Override
    public boolean start() {
        init();
        return true;
    }

    private void init() {
        _volumeTagsUpdateExecutor = Executors.newScheduledThreadPool(2,
                new NamedThreadFactory("StorPoolAbandonObjectsCollector"));
        StorPoolHelper.appendLogger(log, ABANDON_LOG, "abandon");
        if (volumeCheckupTagsInterval.value() > 0) {
            _volumeTagsUpdateExecutor.scheduleAtFixedRate(new StorPoolVolumesTagsUpdate(),
                    volumeCheckupTagsInterval.value(), volumeCheckupTagsInterval.value(), TimeUnit.SECONDS);
        }
        if (snapshotCheckupTagsInterval.value() > 0) {
            _volumeTagsUpdateExecutor.scheduleAtFixedRate(new StorPoolSnapshotsTagsUpdate(),
                    snapshotCheckupTagsInterval.value(), snapshotCheckupTagsInterval.value(), TimeUnit.SECONDS);
        }
    }

    class StorPoolVolumesTagsUpdate extends ManagedContextRunnable {

        @Override
        @DB
        protected void runInContext() {
            List<StoragePoolVO> spPools = storagePoolDao.findPoolsByProvider(StorpoolUtil.SP_PROVIDER_NAME);
            if (spPools != null && spPools.size() > 0) {
                JsonArray arr = StorpoolUtil.volumesList(new SpConnectionDesc(spPools.get(0).getUuid()));
                Transaction.execute(new TransactionCallbackNoReturn() {
                    @Override
                    public void doInTransactionWithoutResult(TransactionStatus status) {
                        TransactionLegacy txn = TransactionLegacy.open(TransactionLegacy.CLOUD_DB);

                        try (PreparedStatement pstmt = txn.prepareAutoCloseStatement(
                                "CREATE TEMPORARY TABLE `cloud`.`volumes1`(`id` bigint unsigned NOT NULL auto_increment, `name` varchar(255) NOT NULL,`tag` varchar(255) NOT NULL, PRIMARY KEY (`id`))")) {
                            pstmt.executeUpdate();
                        } catch (SQLException e) {
                            log.info(String.format("[ignored] SQL failed to delete vm work job: %s ",
                                    e.getLocalizedMessage()));
                        } catch (Throwable e) {
                            log.info(String.format("[ignored] caught an error during delete vm work job: %s",
                                    e.getLocalizedMessage()));
                        }

                        try (PreparedStatement pstmt = txn
                                .prepareStatement("INSERT INTO `cloud`.`volumes1` (name, tag) VALUES (?, ?)")) {
                            for (int i = 0; i < arr.size(); i++) {
                                JsonObject tags = arr.get(i).getAsJsonObject().get("tags").getAsJsonObject();
                                if (tags.getAsJsonPrimitive("cs") != null && !arr.get(i).getAsJsonObject().get("name").getAsString().startsWith("*")) {
                                    addRecordToDb(arr, pstmt, i, tags, true);
                                }
                            }
                            pstmt.executeBatch();
                            String sql = "SELECT f.* FROM `cloud`.`volumes1` f LEFT JOIN `cloud`.`volumes` v ON f.name=v.path where v.path is NULL OR NOT state=?";
                            findMissingRecordsInCS(txn, sql, "volume");
                        } catch (SQLException e) {
                            log.info(String.format("[ignored] SQL failed to delete vm work job: %s ",
                                    e.getLocalizedMessage()));
                        } catch (Throwable e) {
                            log.info(String.format("[ignored] caught an error during delete vm work job: %s",
                                    e.getLocalizedMessage()));
                        } finally {
                            try (PreparedStatement pstmt = txn.prepareStatement("DROP TABLE `cloud`.`volumes1`")) {
                                pstmt.executeUpdate();
                            } catch (SQLException e) {
                                txn.close();
                                log.info(String.format("createTemporaryVolumeTable %s", e.getMessage()));
                            }
                            txn.close();
                        }
                    }
                });
            }
        }
    }

    class StorPoolSnapshotsTagsUpdate extends ManagedContextRunnable {

        @Override
        @DB
        protected void runInContext() {
            List<StoragePoolVO> spPools = storagePoolDao.findPoolsByProvider(StorpoolUtil.SP_PROVIDER_NAME);
            if (spPools != null && spPools.size() > 0) {
                JsonArray arr = StorpoolUtil.snapshotsList(new SpConnectionDesc(spPools.get(0).getUuid()));
                Transaction.execute(new TransactionCallbackNoReturn() {
                    @Override
                    public void doInTransactionWithoutResult(TransactionStatus status) {
                        TransactionLegacy txn = TransactionLegacy.open(TransactionLegacy.CLOUD_DB);

                        try{
                            PreparedStatement pstmt = txn.prepareAutoCloseStatement(
                                    "CREATE TEMPORARY TABLE `cloud`.`snapshots1`(`id` bigint unsigned NOT NULL auto_increment, `name` varchar(255) NOT NULL,`tag` varchar(255) NOT NULL, PRIMARY KEY (`id`))");
                            pstmt.executeUpdate();

                            pstmt = txn.prepareAutoCloseStatement(
                                    "CREATE TEMPORARY TABLE `cloud`.`vm_snapshots1`(`id` bigint unsigned NOT NULL auto_increment, `name` varchar(255) NOT NULL,`tag` varchar(255) NOT NULL, PRIMARY KEY (`id`))");
                            pstmt.executeUpdate();

                            pstmt = txn.prepareAutoCloseStatement(
                                    "CREATE TEMPORARY TABLE `cloud`.`vm_templates1`(`id` bigint unsigned NOT NULL auto_increment, `name` varchar(255) NOT NULL,`tag` varchar(255) NOT NULL, PRIMARY KEY (`id`))");
                            pstmt.executeUpdate();
                        } catch (SQLException e) {
                            log.info(String.format("[ignored] SQL failed to delete vm work job: %s ",
                                    e.getLocalizedMessage()));
                        } catch (Throwable e) {
                            log.info(String.format("[ignored] caught an error during delete vm work job: %s",
                                    e.getLocalizedMessage()));
                        }

                        try {
                            PreparedStatement snapshotsPstmt = txn.prepareStatement("INSERT INTO `cloud`.`snapshots1` (name, tag) VALUES (?, ?)");
                            PreparedStatement groupSnapshotsPstmt = txn.prepareStatement("INSERT INTO `cloud`.`vm_snapshots1` (name, tag) VALUES (?, ?)");
                            PreparedStatement templatePstmt = txn.prepareStatement("INSERT INTO `cloud`.`vm_templates1` (name, tag) VALUES (?, ?)");
                            for (int i = 0; i < arr.size(); i++) {
                                JsonObject tags = arr.get(i).getAsJsonObject().get("tags").getAsJsonObject();
                                if (tags.getAsJsonPrimitive("cs") != null
                                        && !tags.getAsJsonPrimitive("cs").getAsString().equals("group")
                                        && !tags.getAsJsonPrimitive("cs").getAsString().equals("template")
                                        && !arr.get(i).getAsJsonObject().get("deleted").getAsBoolean()) {
                                    addRecordToDb(arr, snapshotsPstmt, i, tags, true);
                                } else if (tags.getAsJsonPrimitive("cs") != null
                                        && tags.getAsJsonPrimitive("cs").getAsString().equals("group") && !arr.get(i).getAsJsonObject().get("deleted").getAsBoolean()) {
                                    addRecordToDb(arr, groupSnapshotsPstmt, i, tags, true);
                                } else if (tags.getAsJsonPrimitive("cs") != null
                                        && tags.getAsJsonPrimitive("cs").getAsString().equals("template") && !arr.get(i).getAsJsonObject().get("deleted").getAsBoolean()) {
                                    addRecordToDb(arr, templatePstmt, i, tags, true);
                                }
                            }
                            snapshotsPstmt.executeBatch();
                            groupSnapshotsPstmt.executeBatch();
                            templatePstmt.executeBatch();

                            String sqlSnapshots = "SELECT f.* FROM `cloud`.`snapshots1` f LEFT JOIN `cloud`.`snapshot_details` v ON f.name=v.value where v.value is NULL";
                            findMissingRecordsInCS(txn, sqlSnapshots, "snapshot");

                            String sqlVmSnapshots = "SELECT f.* FROM `cloud`.`vm_snapshots1` f LEFT JOIN `cloud`.`vm_snapshot_details` v ON f.name=v.value where v.value is NULL";
                            findMissingRecordsInCS(txn, sqlVmSnapshots, "snapshot");

                            String sqlTemplates = "SELECT temp.*"
                                    + " FROM `cloud`.`vm_templates1` temp"
                                    + " LEFT JOIN `cloud`.`template_store_ref` store"
                                    + " ON temp.name=store.local_path"
                                    + " LEFT JOIN `cloud`.`template_spool_ref` spool"
                                    + " ON temp.name=spool.local_path"
                                    + " where store.local_path is NULL"
                                    + " and spool.local_path is NULL";
                            findMissingRecordsInCS(txn, sqlTemplates, "snapshot");
                        } catch (SQLException e) {
                            log.info(String.format("[ignored] SQL failed to delete vm work job: %s ",
                                    e.getLocalizedMessage()));
                        } catch (Throwable e) {
                            log.info(String.format("[ignored] caught an error during delete vm work job: %s",
                                    e.getLocalizedMessage()));
                        } finally {
                            try {
                                PreparedStatement pstmt = txn.prepareStatement("DROP TABLE `cloud`.`snapshots1`");
                                pstmt.executeUpdate();
                                pstmt = txn.prepareStatement("DROP TABLE `cloud`.`vm_snapshots1`");
                                pstmt.executeUpdate();
                                pstmt = txn.prepareStatement("DROP TABLE `cloud`.`vm_templates1`");
                                pstmt.executeUpdate();
                            } catch (SQLException e) {
                                txn.close();
                                log.info(String.format("createTemporaryVolumeTable %s", e.getMessage()));
                            }
                            txn.close();
                        }
                    }
                });
            }
        }
    }

    private void addRecordToDb(JsonArray arr, PreparedStatement pstmt, int i, JsonObject tags, boolean pathNeeded)
            throws SQLException {
        String name = arr.get(i).getAsJsonObject().get("name").getAsString();
        name = name.startsWith("~") ? name.split("~")[1] : name;
        pstmt.setString(1, pathNeeded ? StorpoolUtil.devPath(name) : name);
        pstmt.setString(2, tags.getAsJsonPrimitive("cs").getAsString());
        pstmt.addBatch();
    }

    private void findMissingRecordsInCS(TransactionLegacy txn, String sql, String object) throws SQLException {
        ResultSet rs;
        PreparedStatement pstmt2 = txn.prepareStatement(sql);
        if (object.equals("volume")) {
            pstmt2.setString(1, "Ready");
        }
        rs = pstmt2.executeQuery();
        String name = null;
        while (rs.next()) {
            name = rs.getString(2);
            log.info(String.format(
                    "CloudStack does not know about StorPool %s %s, it had to be a %s", object, name, rs.getString(3)));
        }
    }
}
