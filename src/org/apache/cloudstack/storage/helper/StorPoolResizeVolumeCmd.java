package org.apache.cloudstack.storage.helper;

import javax.inject.Inject;

import org.apache.cloudstack.acl.SecurityChecker.AccessType;
import org.apache.cloudstack.api.ACL;
import org.apache.cloudstack.api.APICommand;
import org.apache.cloudstack.api.ApiConstants;
import org.apache.cloudstack.api.BaseAsyncCmd;
import org.apache.cloudstack.api.Parameter;
import org.apache.cloudstack.api.ResponseObject.ResponseView;
import org.apache.cloudstack.api.command.user.volume.ResizeVolumeCmd;
import org.apache.cloudstack.api.response.DiskOfferingResponse;
import org.apache.cloudstack.api.response.VolumeResponse;
import org.apache.cloudstack.storage.datastore.db.PrimaryDataStoreDao;
import org.apache.cloudstack.storage.datastore.util.StorPoolHelper;
import org.apache.log4j.Logger;

import com.cloud.exception.ResourceAllocationException;
import com.cloud.storage.Volume;
import com.cloud.storage.dao.VolumeDao;
import com.cloud.utils.component.ComponentContext;
@APICommand(name = "resizeVolume", description = "Resizes a volume", responseObject = VolumeResponse.class, responseView = ResponseView.Restricted, entityType = {Volume.class},
requestHasSensitiveInfo = false, responseHasSensitiveInfo = false)
public class StorPoolResizeVolumeCmd extends BaseAsyncCmd {
    public static final Logger s_logger = Logger.getLogger(ResizeVolumeCmd.class.getName());

    private ResizeVolumeCmd resizeVolume;

    private StorPoolReplaceCommandsHelper.StorPoolReplaceCommandsUtil replaceCommands = StorPoolReplaceCommandsHelper.getStorPoolReplaceCommandsUtil();

    @Inject
    private PrimaryDataStoreDao primaryStorageDao;
    @Inject
    private VolumeDao volumeDao;

    /////////////////////////////////////////////////////
    //////////////// API parameters /////////////////////
    /////////////////////////////////////////////////////

    @ACL(accessType = AccessType.OperateEntry)
    @Parameter(name = ApiConstants.ID, entityType = VolumeResponse.class, required = true, type = CommandType.UUID, description = "the ID of the disk volume")
    private Long id;

    @Parameter(name = ApiConstants.MIN_IOPS, type = CommandType.LONG, required = false, description = "New minimum number of IOPS")
    private Long minIops;

    @Parameter(name = ApiConstants.MAX_IOPS, type = CommandType.LONG, required = false, description = "New maximum number of IOPS")
    private Long maxIops;

    @Parameter(name = ApiConstants.SIZE, type = CommandType.LONG, required = false, description = "New volume size in GB")
    private Long size;

    @Parameter(name = ApiConstants.SHRINK_OK, type = CommandType.BOOLEAN, required = false, description = "Verify OK to Shrink")
    private boolean shrinkOk;

    @Parameter(name = ApiConstants.DISK_OFFERING_ID,
               entityType = DiskOfferingResponse.class,
               type = CommandType.UUID,
               required = false,
               description = "new disk offering id")
    private Long newDiskOfferingId;

    public StorPoolResizeVolumeCmd () {
        super();
        try {
            this.resizeVolume = ResizeVolumeCmd.class.newInstance();
        } catch (InstantiationException | IllegalAccessException e) {
            s_logger.error(e.getMessage());
        }
        this.resizeVolume = ComponentContext.inject(this.resizeVolume);
    }

    @Override
    public String getEventType() {
        return this.resizeVolume.getEventType();
    }

    @Override
    public String getEventDescription() {
       replaceCommands.ensureCmdHasRequiredValues(this.resizeVolume, this);
       return this.resizeVolume.getEventDescription();
    }

    @Override
    public String getCommandName() {
        return this.resizeVolume.getCommandName();
    }

    @Override
    public long getEntityOwnerId() {
        replaceCommands.ensureCmdHasRequiredValues(this.resizeVolume, this);
        return this.resizeVolume.getEntityOwnerId();
    }

    public void execute() throws ResourceAllocationException {
        replaceCommands.ensureCmdHasRequiredValues(this.resizeVolume, this);
        this.resizeVolume.execute();
        if (StorPoolHelper.isStorPoolStorage(primaryStorageDao, volumeDao, id) && newDiskOfferingId != null) {
            replaceCommands.updateVolumeTemplate(id, newDiskOfferingId);
        }
        this.setResponseObject(this.resizeVolume.getResponseObject());
    }
}
