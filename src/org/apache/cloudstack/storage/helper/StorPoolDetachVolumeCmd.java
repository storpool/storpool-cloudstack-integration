package org.apache.cloudstack.storage.helper;

import org.apache.cloudstack.acl.SecurityChecker.AccessType;
import org.apache.cloudstack.api.ACL;
import org.apache.cloudstack.api.APICommand;
import org.apache.cloudstack.api.ApiConstants;
import org.apache.cloudstack.api.BaseAsyncCmd;
import org.apache.cloudstack.api.Parameter;
import org.apache.cloudstack.api.ResponseObject.ResponseView;
import org.apache.cloudstack.api.command.user.volume.DetachVolumeCmd;
import org.apache.cloudstack.api.response.UserVmResponse;
import org.apache.cloudstack.api.response.VolumeResponse;
import org.apache.log4j.Logger;

import com.cloud.utils.component.ComponentContext;
import com.cloud.vm.VirtualMachine;

@APICommand(name = "detachVolume", description = "Detaches a disk volume from a virtual machine.", responseObject = VolumeResponse.class, responseView = ResponseView.Restricted, entityType = {VirtualMachine.class},
requestHasSensitiveInfo = false, responseHasSensitiveInfo = false)
public class StorPoolDetachVolumeCmd extends BaseAsyncCmd{
    private static final Logger log = Logger.getLogger(StorPoolDetachVolumeCmd.class);

    @Parameter(name=ApiConstants.ID, type=CommandType.UUID, entityType=VolumeResponse.class,
            description="the ID of the disk volume")
    private Long id;

    @Parameter(name = ApiConstants.DEVICE_ID, type = CommandType.LONG, description = "the device ID on the virtual machine where volume is detached from")
    private Long deviceId;

    @ACL(accessType = AccessType.OperateEntry)
    @Parameter(name = ApiConstants.VIRTUAL_MACHINE_ID, type = CommandType.UUID, entityType = UserVmResponse.class, description = "the ID of the virtual machine where the volume is detached from")
    private Long virtualMachineId;

    private StorPoolReplaceCommandsHelper.StorPoolReplaceCommandsUtil replaceCommands = StorPoolReplaceCommandsHelper.getStorPoolReplaceCommandsUtil();
    private DetachVolumeCmd detachVolumeCmd;

    public StorPoolDetachVolumeCmd() {
        super();
            try {
                this.detachVolumeCmd = DetachVolumeCmd.class.newInstance();
            } catch (InstantiationException | IllegalAccessException e) {
                log.error(e.getMessage());
            }
            this.detachVolumeCmd = ComponentContext.inject(this.detachVolumeCmd);
    }

    @Override
    public String getEventType() {
        return this.detachVolumeCmd.getEventType();
    }

    @Override
    public String getEventDescription() {
        replaceCommands.ensureCmdHasRequiredValues(this.detachVolumeCmd, this);
       return this.detachVolumeCmd.getEventDescription();
    }

    @Override
    public void execute() {
        replaceCommands.ensureCmdHasRequiredValues(this.detachVolumeCmd, this);
        this.detachVolumeCmd.execute();
        log.info("DetachVolumeCmd.execute was successfuly executed");
        replaceCommands.updateVolumeTags(detachVolumeCmd.getId(), detachVolumeCmd.getVirtualMachineId());
        //set Response object, because asyncjob is never finished and we did not receive message in the UIthat the volumes is attached
        this.setResponseObject(detachVolumeCmd.getResponseObject());
    }

    @Override
    public String getCommandName() {
        return this.detachVolumeCmd.getCommandName();
    }

    @Override
    public long getEntityOwnerId() {
        replaceCommands.ensureCmdHasRequiredValues(this.detachVolumeCmd, this);
        return this.detachVolumeCmd.getEntityOwnerId();
    }
}
