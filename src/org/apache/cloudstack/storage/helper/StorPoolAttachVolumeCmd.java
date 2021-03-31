package org.apache.cloudstack.storage.helper;

import javax.inject.Inject;

import org.apache.cloudstack.acl.SecurityChecker.AccessType;
import org.apache.cloudstack.api.ACL;
import org.apache.cloudstack.api.APICommand;
import org.apache.cloudstack.api.ApiConstants;
import org.apache.cloudstack.api.BaseAsyncCmd;
import org.apache.cloudstack.api.Parameter;
import org.apache.cloudstack.api.ResponseObject.ResponseView;
import org.apache.cloudstack.api.command.user.volume.AttachVolumeCmd;
import org.apache.cloudstack.api.response.UserVmResponse;
import org.apache.cloudstack.api.response.VolumeResponse;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil;
import org.apache.log4j.Logger;

import com.cloud.server.ResourceTag;
import com.cloud.server.ResourceTag.ResourceObjectType;
import com.cloud.tags.dao.ResourceTagDao;
import com.cloud.utils.component.ComponentContext;
import com.cloud.vm.VirtualMachine;

@APICommand(name = "attachVolume", description = "Attaches a disk volume to a virtual machine.", responseObject = VolumeResponse.class, responseView = ResponseView.Restricted, entityType = {
        VirtualMachine.class }, requestHasSensitiveInfo = false, responseHasSensitiveInfo = false)
public class StorPoolAttachVolumeCmd extends BaseAsyncCmd {
    private static final Logger log = Logger.getLogger(StorPoolAttachVolumeCmd.class);

    @Parameter(name = ApiConstants.DEVICE_ID, type = CommandType.LONG, description = "the ID of the device to map the volume to within the guest OS. "
            + "If no deviceId is passed in, the next available deviceId will be chosen. " + "Possible values for a Linux OS are:" + "* 0 - /dev/xvda" + "* 1 - /dev/xvdb" + "* 2 - /dev/xvdc"
        + "* 4 - /dev/xvde" + "* 5 - /dev/xvdf" + "* 6 - /dev/xvdg" + "* 7 - /dev/xvdh" + "* 8 - /dev/xvdi" + "* 9 - /dev/xvdj")
    private Long deviceId;

    @Parameter(name = ApiConstants.ID, type = CommandType.UUID, entityType = VolumeResponse.class, required = true, description = "the ID of the disk volume")
    private Long id;

    @ACL(accessType = AccessType.OperateEntry)
    @Parameter(name=ApiConstants.VIRTUAL_MACHINE_ID, type=CommandType.UUID, entityType=UserVmResponse.class, required=true, description="the ID of the virtual machine")
    private Long virtualMachineId;

    private AttachVolumeCmd attachVolumeCmd;
    private StorPoolReplaceCommandsHelper.StorPoolReplaceCommandsUtil replaceCommands = StorPoolReplaceCommandsHelper.getStorPoolReplaceCommandsUtil();
    @Inject
    private ResourceTagDao _resourceTagDao;

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
        ResourceTag resourceTag = _resourceTagDao.findByKey(this.attachVolumeCmd.getVirtualMachineId(), ResourceObjectType.UserVm, StorpoolUtil.SP_VC_POLICY);
        replaceCommands.updateVolumeTags(this.attachVolumeCmd.getId(), this.attachVolumeCmd.getVirtualMachineId(), resourceTag !=null ? resourceTag.getValue() : "");
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
