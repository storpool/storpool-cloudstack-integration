package org.apache.cloudstack.storage.helper;

import java.util.List;

import javax.inject.Inject;

import org.apache.cloudstack.api.APICommand;
import org.apache.cloudstack.api.BaseAsyncCmd;
import org.apache.cloudstack.api.ServerApiException;
import org.apache.cloudstack.api.command.user.tag.CreateTagsCmd;
import org.apache.cloudstack.api.response.SuccessResponse;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil;
import org.apache.log4j.Logger;

import com.cloud.exception.ConcurrentOperationException;
import com.cloud.exception.InsufficientCapacityException;
import com.cloud.exception.NetworkRuleConflictException;
import com.cloud.exception.ResourceAllocationException;
import com.cloud.exception.ResourceUnavailableException;
import com.cloud.server.ResourceTag;
import com.cloud.server.ResourceTag.ResourceObjectType;
import com.cloud.storage.VolumeVO;
import com.cloud.storage.dao.VolumeDao;
import com.cloud.utils.component.ComponentContext;
import com.cloud.utils.exception.CloudRuntimeException;
import com.cloud.vm.VMInstanceVO;
import com.cloud.vm.dao.VMInstanceDao;

@APICommand(name = "createTags", description = "Creates resource tag(s)", responseObject = SuccessResponse.class, since = "4.0.0", entityType = {ResourceTag.class},
requestHasSensitiveInfo = false, responseHasSensitiveInfo = false)
public class StorPoolCreateTagsCmd extends BaseAsyncCmd{
    private static final Logger log = Logger.getLogger(StorPoolCreateTagsCmd.class);
    private CreateTagsCmd createTagsCmd;
    private StorPoolReplaceCommandsHelper.StorPoolReplaceCommandsUtil replaceCommands = StorPoolReplaceCommandsHelper.getStorPoolReplaceCommandsUtil();
    @Inject
    private VMInstanceDao vmInstanceDao;
    @Inject
    private VolumeDao volumeDao;

    public StorPoolCreateTagsCmd() {
        super();
        try {
            this.createTagsCmd = CreateTagsCmd.class.newInstance();
        } catch (InstantiationException | IllegalAccessException e) {
            log.error(e.getMessage());
        }
        this.createTagsCmd = ComponentContext.inject(this.createTagsCmd);
    }

    @Override
    public String getEventType() {
        return createTagsCmd.getEventType();
    }

    @Override
    public String getEventDescription() {
        return createTagsCmd.getEventDescription();
    }

    @Override
    public void execute() throws ResourceUnavailableException, InsufficientCapacityException,
                                    ServerApiException, ConcurrentOperationException,
                                    ResourceAllocationException, NetworkRuleConflictException {
        replaceCommands.ensureCmdHasRequiredValues(createTagsCmd, this);
        try {
            createTagsCmd.execute();
        }
        catch (CloudRuntimeException e) {
            throw e;
        }
        String value = createTagsCmd.getTags().get(StorpoolUtil.SP_VC_POLICY);

        if (createTagsCmd.getResourceType() == ResourceObjectType.UserVm && value != null) {
            for (String resourceId : createTagsCmd.getResourceIds()) {
                VMInstanceVO vm = vmInstanceDao.findByUuid(resourceId);
                List<VolumeVO> volumes =volumeDao.findByInstance(vm.getId());
                for (VolumeVO volumeVO : volumes) {
                    replaceCommands.updateVolumeTags(volumeVO.getId(), vm.getId(), value);
                }
            }
        }
        this.setResponseObject(createTagsCmd.getResponseObject());
    }

    @Override
    public String getCommandName() {
        return createTagsCmd.getCommandName();
    }

    @Override
    public long getEntityOwnerId() {
        return createTagsCmd.getEntityOwnerId();
    }
}
