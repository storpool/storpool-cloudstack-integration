package org.apache.cloudstack.storage.helper;

import org.apache.cloudstack.acl.SecurityChecker.AccessType;
import org.apache.cloudstack.api.ACL;
import org.apache.cloudstack.api.APICommand;
import org.apache.cloudstack.api.ApiConstants;
import org.apache.cloudstack.api.ApiErrorCode;
import org.apache.cloudstack.api.BaseAsyncCreateCmd;
import org.apache.cloudstack.api.Parameter;
import org.apache.cloudstack.api.ServerApiException;
import org.apache.cloudstack.api.command.user.vmsnapshot.CreateVMSnapshotCmd;
import org.apache.cloudstack.api.response.UserVmResponse;
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

    @ACL(accessType = AccessType.OperateEntry)
    @Parameter(name = ApiConstants.VIRTUAL_MACHINE_ID, type = CommandType.UUID, required = true, entityType = UserVmResponse.class, description = "The ID of the vm")
    private Long vmId;

    @Parameter(name = ApiConstants.VM_SNAPSHOT_DESCRIPTION, type = CommandType.STRING, required = false, description = "The description of the snapshot")
    private String description;

    @Parameter(name = ApiConstants.VM_SNAPSHOT_DISPLAYNAME, type = CommandType.STRING, required = false, description = "The display name of the snapshot")
    private String displayName;

    @Parameter(name = ApiConstants.VM_SNAPSHOT_MEMORY, type = CommandType.BOOLEAN, required = false, description = "snapshot memory if true")
    private Boolean snapshotMemory;

    @Parameter(name = ApiConstants.VM_SNAPSHOT_QUIESCEVM, type = CommandType.BOOLEAN, required = false, description = "quiesce vm if true")
    private Boolean quiescevm;

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
        VMSnapshot vmsnapshot = null;
        if (replaceCommand.areAllVolumesOnStorPool(this.createVMSnapshotCmd.getVmId())) {
            vmsnapshot = replaceCommand.allocVMSnapshot(this.createVMSnapshotCmd.getVmId(), this.createVMSnapshotCmd.getDisplayName(),
                    this.createVMSnapshotCmd.getDescription(), this.createVMSnapshotCmd.snapshotMemory());
        } else {
            vmsnapshot = _vmSnapshotService.allocVMSnapshot(this.createVMSnapshotCmd.getVmId(), this.createVMSnapshotCmd.getDisplayName(),
                this.createVMSnapshotCmd.getDescription(), this.createVMSnapshotCmd.snapshotMemory());
        }
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
