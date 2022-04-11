package org.apache.cloudstack.storage.helper;

import java.util.List;
import java.util.Map;

import javax.inject.Inject;

import org.apache.cloudstack.acl.SecurityChecker.AccessType;
import org.apache.cloudstack.api.ACL;
import org.apache.cloudstack.api.APICommand;
import org.apache.cloudstack.api.ApiConstants;
import org.apache.cloudstack.api.BaseAsyncCmd;
import org.apache.cloudstack.api.BaseCmd;
import org.apache.cloudstack.api.Parameter;
import org.apache.cloudstack.api.ResponseObject.ResponseView;
import org.apache.cloudstack.api.ServerApiException;
import org.apache.cloudstack.api.command.user.vm.ScaleVMCmd;
import org.apache.cloudstack.api.response.ServiceOfferingResponse;
import org.apache.cloudstack.api.response.UserVmResponse;
import org.apache.cloudstack.storage.datastore.db.PrimaryDataStoreDao;
import org.apache.cloudstack.storage.datastore.util.StorPoolHelper;
import org.apache.log4j.Logger;

import com.cloud.exception.ConcurrentOperationException;
import com.cloud.exception.InsufficientCapacityException;
import com.cloud.exception.NetworkRuleConflictException;
import com.cloud.exception.ResourceAllocationException;
import com.cloud.exception.ResourceUnavailableException;
import com.cloud.storage.Volume;
import com.cloud.storage.VolumeVO;
import com.cloud.storage.dao.VolumeDao;
import com.cloud.utils.component.ComponentContext;
import com.cloud.vm.VirtualMachine;

@APICommand(name = "scaleVirtualMachine", description = "Scales the virtual machine to a new service offering.", responseObject = UserVmResponse.class, responseView = ResponseView.Restricted, entityType = {VirtualMachine.class},
requestHasSensitiveInfo = false, responseHasSensitiveInfo = false)
public class StorPoolScaleVMCmd extends BaseAsyncCmd {
    public static final Logger s_logger = Logger.getLogger(ScaleVMCmd.class.getName());

    private ScaleVMCmd scaleVMCmd;

    private StorPoolReplaceCommandsHelper.StorPoolReplaceCommandsUtil replaceCommands = StorPoolReplaceCommandsHelper.getStorPoolReplaceCommandsUtil();

    @Inject
    private PrimaryDataStoreDao primaryStorageDao;
    @Inject
    private VolumeDao volumeDao;

    /////////////////////////////////////////////////////
    //////////////// API parameters /////////////////////
    /////////////////////////////////////////////////////
    @ACL(accessType = AccessType.OperateEntry)
    @Parameter(name=ApiConstants.ID, type=CommandType.UUID, entityType=UserVmResponse.class,
            required=true, description="The ID of the virtual machine")
    private Long id;

    @Parameter(name=ApiConstants.SERVICE_OFFERING_ID, type=CommandType.UUID, entityType=ServiceOfferingResponse.class,
            required=true, description="the ID of the service offering for the virtual machine")
    private Long serviceOfferingId;

    @Parameter(name = ApiConstants.DETAILS, type = BaseCmd.CommandType.MAP, description = "name value pairs of custom parameters for cpu,memory and cpunumber. example details[i].name=value")
    private Map<String, String> details;

    public StorPoolScaleVMCmd () {
        super();
        try {
            this.scaleVMCmd = ScaleVMCmd.class.newInstance();
        } catch (InstantiationException | IllegalAccessException e) {
            s_logger.error(e.getMessage());
        }
        this.scaleVMCmd = ComponentContext.inject(this.scaleVMCmd);
    }

    @Override
    public String getEventType() {
        return this.scaleVMCmd.getEventType();
    }

    @Override
    public String getEventDescription() {
        replaceCommands.ensureCmdHasRequiredValues(this.scaleVMCmd, this);
        return this.scaleVMCmd.getEventDescription();
    }

    @Override
    public void execute() throws ResourceUnavailableException, InsufficientCapacityException, ServerApiException,
            ConcurrentOperationException, ResourceAllocationException, NetworkRuleConflictException {
        replaceCommands.ensureCmdHasRequiredValues(this.scaleVMCmd, this);
        this.scaleVMCmd.execute();
        if (serviceOfferingId != null) {
            List<VolumeVO> rootVolumes = volumeDao.findByInstance(id);
            for (VolumeVO volumeVO : rootVolumes) {
                if (Volume.Type.ROOT == volumeVO.getVolumeType()) {
                    if (StorPoolHelper.isStorPoolStorage(primaryStorageDao, volumeDao, volumeVO.getId())) {
                        replaceCommands.updateVolumeTemplate(volumeVO.getId(), serviceOfferingId);
                    }
                }
            }
        }
        this.setResponseObject(this.scaleVMCmd.getResponseObject());
    }

    @Override
    public String getCommandName() {
        return this.scaleVMCmd.getCommandName();
    }

    @Override
    public long getEntityOwnerId() {
        replaceCommands.ensureCmdHasRequiredValues(this.scaleVMCmd, this);
        return this.scaleVMCmd.getEntityOwnerId();
    }

}
