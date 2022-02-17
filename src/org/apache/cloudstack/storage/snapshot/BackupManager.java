package org.apache.cloudstack.storage.snapshot;

import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;

import org.apache.cloudstack.framework.config.ConfigKey;
import org.apache.cloudstack.framework.config.Configurable;

import com.cloud.utils.crypt.DBEncryptionUtil;
import com.cloud.utils.crypt.EncryptionSecretKeyChecker;
import com.cloud.utils.db.TransactionLegacy;
import com.cloud.utils.exception.CloudRuntimeException;

public class BackupManager implements Configurable{

    public static final ConfigKey<Boolean> BypassSecondaryStorage = new ConfigKey<Boolean>(Boolean.class, "sp.bypass.secondary.storage", "Advanced", "false",
            "For StorPool Managed storage backup to secondary", true, ConfigKey.Scope.Global, null);
    public static final ConfigKey<String> StorPoolClusterId = new ConfigKey<String>(String.class, "sp.cluster.id", "Advanced", "n/a",
                                    "For StorPool multi cluster authorization", true, ConfigKey.Scope.Cluster, null);
    public static final ConfigKey<Boolean> IsMigrationCompleted = new ConfigKey<Boolean>(Boolean.class, "sp.migration.to.global.ids.completed", "Hidden", "false",
            "For StorPool volumes, snapshots and group snapshots created with names that have to be migrated to StorPool's globalIds", true, ConfigKey.Scope.Global, null);

    public static final ConfigKey<Boolean> AlternativeEndPointEnabled = new ConfigKey<Boolean>(Boolean.class, "sp.enable.alternative.endpoint", "Advanced", "false",
            "Used for StorPool primary storage, definse if there is a need to be used alternative endpoint", true, ConfigKey.Scope.StoragePool, null);

    public static final ConfigKey<String> AlternativeEndpoint = new ConfigKey<String>(String.class, "sp.alternative.endpoint", "Advanced", "",
            "Used for StorPool primary storage for an alternative endpoint. Structure of the endpoint is - SP_API_HTTP=address:port;SP_AUTH_TOKEN=token;SP_TEMPLATE=template_name", true, ConfigKey.Scope.StoragePool, null);

    private static final String SELECT_VALUE = "Select value FROM `cloud`.`configuration` where name=\"sp.migration.to.global.ids.completed\"";
    private static final String UPDATE_CONFIG = "UPDATE `cloud`.`configuration` set category=?, value=? where name=\"sp.migration.to.global.ids.completed\"";

    @Override
    public String getConfigComponentName() {
        return BackupManager.class.getSimpleName();
    }

    @Override
    public ConfigKey<?>[] getConfigKeys() {
        getAndUpdateMigrationConfig();
        return new ConfigKey<?>[] { BypassSecondaryStorage, StorPoolClusterId, IsMigrationCompleted, AlternativeEndPointEnabled, AlternativeEndpoint };
    }

    private void getAndUpdateMigrationConfig() {
        final TransactionLegacy txn = TransactionLegacy.currentTxn();
        PreparedStatement pstmt = null;
        String result = null;
        try {
            pstmt = txn.prepareAutoCloseStatement(SELECT_VALUE);

            final ResultSet rs = pstmt.executeQuery();
            while (rs.next()) {
                result = rs.getString(1);
            }
            if (EncryptionSecretKeyChecker.useEncryption() && result != null && (result.equalsIgnoreCase("true") || result.equalsIgnoreCase("false"))) {
                    pstmt = txn.prepareAutoCloseStatement(UPDATE_CONFIG);
                    pstmt.setString(1, "Hidden");
                    pstmt.setString(2, DBEncryptionUtil.encrypt(result));
                    pstmt.executeUpdate();
            }
        } catch (final SQLException e) {
            throw new CloudRuntimeException("DB Exception on: " + pstmt, e);
        } catch (final Throwable e) {
            throw new CloudRuntimeException("Caught: " + pstmt, e);
        }
    }
}
