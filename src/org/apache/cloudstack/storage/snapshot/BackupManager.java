package org.apache.cloudstack.storage.snapshot;

import org.apache.cloudstack.framework.config.ConfigKey;
import org.apache.cloudstack.framework.config.Configurable;

public class BackupManager implements Configurable{
    public static final ConfigKey<Boolean> BypassSecondaryStorage = new ConfigKey<Boolean>(Boolean.class, "sp.bypass.secondary.storage", "Advanced", "false",
            "For StorPool Managed storage backup to secodnary", true, ConfigKey.Scope.Global, null);
    public static final ConfigKey<String> StorPoolClusterId = new ConfigKey<String>(String.class, "sp.cluster.id", "Advanced", "n/a",
                                    "For StorPool multi cluster authorization", true, ConfigKey.Scope.Cluster, null);

    @Override
    public String getConfigComponentName() {
        return BackupManager.class.getSimpleName();
    }

    @Override
    public ConfigKey<?>[] getConfigKeys() {
        return new ConfigKey<?>[] { BypassSecondaryStorage, StorPoolClusterId};
    }
}
