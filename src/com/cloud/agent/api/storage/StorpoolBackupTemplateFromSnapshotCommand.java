package com.cloud.agent.api.storage;

import org.apache.cloudstack.storage.to.SnapshotObjectTO;
import org.apache.cloudstack.storage.to.TemplateObjectTO;

import com.cloud.agent.api.to.DataTO;

public class StorpoolBackupTemplateFromSnapshotCommand extends StorpoolCopyCommand<SnapshotObjectTO, TemplateObjectTO> {
    public StorpoolBackupTemplateFromSnapshotCommand(final DataTO srcTO, final DataTO dstTO, final int timeout, final boolean executeInSequence) {
        super(srcTO, dstTO, timeout, executeInSequence);
    }
}
