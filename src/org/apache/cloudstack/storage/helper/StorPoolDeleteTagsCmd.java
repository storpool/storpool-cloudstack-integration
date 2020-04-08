package org.apache.cloudstack.storage.helper;

import java.util.List;

import javax.inject.Inject;

import org.apache.cloudstack.api.APICommand;
import org.apache.cloudstack.api.BaseAsyncCmd;
import org.apache.cloudstack.api.ServerApiException;
import org.apache.cloudstack.api.command.user.tag.DeleteTagsCmd;
import org.apache.cloudstack.api.response.SuccessResponse;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil;
import org.apache.log4j.Logger;

import com.cloud.exception.ConcurrentOperationException;
import com.cloud.exception.InsufficientCapacityException;
import com.cloud.exception.InvalidParameterValueException;
import com.cloud.exception.NetworkRuleConflictException;
import com.cloud.exception.PermissionDeniedException;
import com.cloud.exception.ResourceAllocationException;
import com.cloud.exception.ResourceUnavailableException;
import com.cloud.server.ResourceTag;
import com.cloud.server.ResourceTag.ResourceObjectType;
import com.cloud.storage.VolumeVO;
import com.cloud.storage.dao.VolumeDao;
import com.cloud.utils.component.ComponentContext;
import com.cloud.vm.VMInstanceVO;
import com.cloud.vm.dao.VMInstanceDao;

@APICommand(name = "deleteTags", description = "Deleting resource tag(s)", responseObject = SuccessResponse.class, since = "4.0.0", entityType = {ResourceTag.class},
requestHasSensitiveInfo = false, responseHasSensitiveInfo = false)
public class StorPoolDeleteTagsCmd extends BaseAsyncCmd{
    private static final Logger log = Logger.getLogger(StorPoolDeleteTagsCmd.class);
    private DeleteTagsCmd deleteTagsCmd;
    private StorPoolReplaceCommandsHelper.StorPoolReplaceCommandsUtil replaceCommands = StorPoolReplaceCommandsHelper.getStorPoolReplaceCommandsUtil();
    @Inject
    private VMInstanceDao vmInstanceDao;
    @Inject
    private VolumeDao volumeDao;

    public StorPoolDeleteTagsCmd (){
        super();
        try {
            this.deleteTagsCmd = DeleteTagsCmd.class.newInstance();
        } catch (InstantiationException | IllegalAccessException e) {
            log.error(e.getMessage());
        }
        this.deleteTagsCmd = ComponentContext.inject(this.deleteTagsCmd);
    }

    @Override
    public String getEventType() {
        return deleteTagsCmd.getEventType();
    }

    @Override
    public String getEventDescription() {
        return deleteTagsCmd.getEventDescription();
    }

    @Override
    public void execute() throws ResourceUnavailableException, InsufficientCapacityException,
                                    ServerApiException, ConcurrentOperationException,
                                    ResourceAllocationException, NetworkRuleConflictException, PermissionDeniedException {
        replaceCommands.ensureCmdHasRequiredValues(deleteTagsCmd, this);
        String value = deleteTagsCmd.getTags().get(StorpoolUtil.SP_VC_POLICY);
        replaceCommands.hasRights(value);
        try {
            deleteTagsCmd.execute();
        }
        catch (InvalidParameterValueException e) {
            throw e;
        }

        if (value != null && deleteTagsCmd.getResourceType() == ResourceObjectType.UserVm) {
            for (String resourceId : deleteTagsCmd.getResourceIds()) {
                VMInstanceVO vm = vmInstanceDao.findByUuid(resourceId);
                List<VolumeVO> volumes = volumeDao.findByInstance(vm.getId());
                for (VolumeVO volumeVO : volumes) {
                    replaceCommands.updateVolumeTags(volumeVO.getId(), vm.getId(), "");
                }
            }
        }
        this.setResponseObject(deleteTagsCmd.getResponseObject());
    }

    @Override
    public String getCommandName() {
        return deleteTagsCmd.getCommandName();
    }

    @Override
    public long getEntityOwnerId() {
        return deleteTagsCmd.getEntityOwnerId();
    }
}
