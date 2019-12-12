package org.apache.cloudstack.storage.helper;

import org.apache.cloudstack.api.APICommand;
import org.apache.cloudstack.api.ApiErrorCode;
import org.apache.cloudstack.api.BaseAsyncCreateCmd;
import org.apache.cloudstack.api.ServerApiException;
import org.apache.cloudstack.api.command.user.vmsnapshot.CreateVMSnapshotCmd;
import org.apache.cloudstack.api.response.VMSnapshotResponse;
import org.apache.log4j.Logger;

import com.cloud.exception.ConcurrentOperationException;
import com.cloud.exception.InsufficientCapacityException;
import com.cloud.exception.NetworkRuleConflictException;
import com.cloud.exception.ResourceAllocationException;
import com.cloud.exception.ResourceUnavailableException;
import com.cloud.utils.component.ComponentContext;
import com.cloud.vm.snapshot.VMSnapshot;

@APICommand(name = "createVMSnapshot", description = "Creates snapshot for a vm.", responseObject = VMSnapshotResponse.class, since = "4.2.0", entityType = {VMSnapshot.class},
requestHasSensitiveInfo = false, responseHasSensitiveInfo = false)
public class StorPoolCreateVMSnapshotCmd extends BaseAsyncCreateCmd{
    private static final Logger log = Logger.getLogger(StorPoolCreateVMSnapshotCmd.class);

    private CreateVMSnapshotCmd createVMSnapshotCmd;
    private StorPoolReplaceCommandsHelper.StorPoolReplaceCommandsUtil replaceCommand = StorPoolReplaceCommandsHelper.getStorPoolReplaceCommandsUtil();

    public StorPoolCreateVMSnapshotCmd() {
        super();
        try {
            this.createVMSnapshotCmd = CreateVMSnapshotCmd.class.newInstance();
        } catch (InstantiationException | IllegalAccessException e) {
            log.error(e.getMessage());
        }
        this.createVMSnapshotCmd = ComponentContext.inject(this.createVMSnapshotCmd);
    }

    @Override
    public void create() throws ResourceAllocationException {
        replaceCommand.ensureCmdHasRequiredValues(this.createVMSnapshotCmd, this);
        VMSnapshot vmsnapshot = replaceCommand.allocVMSnapshot(this.createVMSnapshotCmd.getVmId(), this.createVMSnapshotCmd.getDisplayName(),
                this.createVMSnapshotCmd.getDescription(), this.createVMSnapshotCmd.snapshotMemory());
        if (vmsnapshot != null) {
            setEntityId(vmsnapshot.getId());
            this.createVMSnapshotCmd.setEntityId(vmsnapshot.getId());
        } else {
            throw new ServerApiException(ApiErrorCode.INTERNAL_ERROR, "Failed to create vm snapshot");
        }
    }

    @Override
    public String getEventType() {
        return this.createVMSnapshotCmd.getEventType();
    }

    @Override
    public String getEventDescription() {
        replaceCommand.ensureCmdHasRequiredValues(this.createVMSnapshotCmd, this);
        return this.createVMSnapshotCmd.getEventDescription();
    }

    @Override
    public void execute() throws ResourceUnavailableException, InsufficientCapacityException, ServerApiException,
            ConcurrentOperationException, ResourceAllocationException, NetworkRuleConflictException {
        replaceCommand.ensureCmdHasRequiredValues(this.createVMSnapshotCmd, this);
        this.createVMSnapshotCmd.execute();
        log.info("StorPoolCreateVMSnapshotCmd.execute");
        this.setResponseObject(this.createVMSnapshotCmd.getResponseObject());
    }

    @Override
    public String getCommandName() {
        return this.createVMSnapshotCmd.getCommandName();
    }

    @Override
    public long getEntityOwnerId() {
        replaceCommand.ensureCmdHasRequiredValues(this.createVMSnapshotCmd, this);
        return this.createVMSnapshotCmd.getEntityOwnerId();
    }

}
