package com.cloud.agent.api.storage;

import java.util.ArrayList;
import java.util.List;

import com.cloud.agent.api.MigrateCommand;
import com.cloud.agent.api.to.VirtualMachineTO;

public class StorPoolMigrateWithVolumesCommand extends MigrateCommand {
    private List<MigrateDiskInfo> migrateDiskInfoList = new ArrayList<>();

    public StorPoolMigrateWithVolumesCommand() {
        super();
    }

    public StorPoolMigrateWithVolumesCommand(String vmName, String destIp, boolean isWindows, VirtualMachineTO vmTO,
            boolean executeInSequence) {
        super(vmName, destIp, isWindows, vmTO, executeInSequence);
    }

    public List<MigrateDiskInfo> getMigrateDiskInfoList() {
        return migrateDiskInfoList;
    }

    public void setMigrateDiskInfoList(List<MigrateDiskInfo> migrateDiskInfoList) {
        this.migrateDiskInfoList = migrateDiskInfoList;
    }

    public boolean isMigrateStorageManaged() {
        return true;
    }

    public boolean isMigrateNonSharedInc() {
        return false;
    }
}
