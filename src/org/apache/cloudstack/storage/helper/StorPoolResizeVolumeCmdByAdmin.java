package org.apache.cloudstack.storage.helper;

import org.apache.cloudstack.api.APICommand;
import org.apache.cloudstack.api.ResponseObject.ResponseView;
import org.apache.cloudstack.api.response.VolumeResponse;

import com.cloud.storage.Volume;

@APICommand(name = "resizeVolume", description = "Resizes a volume", responseObject = VolumeResponse.class, responseView = ResponseView.Full, entityType = {Volume.class},
requestHasSensitiveInfo = false, responseHasSensitiveInfo = false)
public class StorPoolResizeVolumeCmdByAdmin extends StorPoolResizeVolumeCmd {}
