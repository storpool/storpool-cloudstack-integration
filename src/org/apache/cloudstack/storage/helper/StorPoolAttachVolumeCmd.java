package org.apache.cloudstack.storage.helper;

import org.apache.cloudstack.api.APICommand;
import org.apache.cloudstack.api.BaseAsyncCmd;
import org.apache.cloudstack.api.ResponseObject.ResponseView;
import org.apache.cloudstack.api.command.user.volume.AttachVolumeCmd;
import org.apache.cloudstack.api.response.VolumeResponse;
import org.apache.log4j.Logger;

import com.cloud.utils.component.ComponentContext;
import com.cloud.vm.VirtualMachine;

@APICommand(name = "attachVolume", description = "Attaches a disk volume to a virtual machine.", responseObject = VolumeResponse.class, responseView = ResponseView.Restricted, entityType = {
        VirtualMachine.class }, requestHasSensitiveInfo = false, responseHasSensitiveInfo = false)
public class StorPoolAttachVolumeCmd extends BaseAsyncCmd {
    private static final Logger log = Logger.getLogger(StorPoolAttachVolumeCmd.class);
    private AttachVolumeCmd attachVolumeCmd;
    private StorPoolReplaceCommandsHelper.StorPoolReplaceCommandsUtil replaceCommands = StorPoolReplaceCommandsHelper.getStorPoolReplaceCommandsUtil();

    public StorPoolAttachVolumeCmd() {
        super();
            try {
                this.attachVolumeCmd = AttachVolumeCmd.class.newInstance();
            } catch (InstantiationException | IllegalAccessException e) {
                log.error(e.getMessage());
            }
            this.attachVolumeCmd = ComponentContext.inject(this.attachVolumeCmd);
    }

    @Override
    public String getEventType() {
        return this.attachVolumeCmd.getEventType();
    }

    @Override
    public String getEventDescription() {
        replaceCommands.ensureCmdHasRequiredValues(this.attachVolumeCmd, this);
        return this.attachVolumeCmd.getEventDescription();
    }

    @Override
    public void execute() {
        replaceCommands.ensureCmdHasRequiredValues(this.attachVolumeCmd, this);
        this.attachVolumeCmd.execute();
        log.info("AttachVolumeCmd.execute was successfuly executed");
        replaceCommands.updateVolumeTags(this.attachVolumeCmd.getId(), this.attachVolumeCmd.getVirtualMachineId());
        // set Response object, because asyncjob is never finished and we did not
        // receive message in the UIthat the volumes is attached
        this.setResponseObject(attachVolumeCmd.getResponseObject());
    }

    @Override
    public String getCommandName() {
        return this.attachVolumeCmd.getCommandName();
    }

    @Override
    public long getEntityOwnerId() {
        replaceCommands.ensureCmdHasRequiredValues(this.attachVolumeCmd, this);
        return this.attachVolumeCmd.getEntityOwnerId();
    }
}
