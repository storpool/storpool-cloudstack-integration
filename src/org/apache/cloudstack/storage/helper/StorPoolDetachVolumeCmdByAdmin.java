package org.apache.cloudstack.storage.helper;

import org.apache.cloudstack.api.APICommand;
import org.apache.cloudstack.api.ResponseObject.ResponseView;
import org.apache.cloudstack.api.response.VolumeResponse;

import com.cloud.vm.VirtualMachine;

@APICommand(name = "detachVolume", description = "Detaches a disk volume from a virtual machine.", responseObject = VolumeResponse.class, responseView = ResponseView.Full, entityType = {VirtualMachine.class},
requestHasSensitiveInfo = false, responseHasSensitiveInfo = false)
public class StorPoolDetachVolumeCmdByAdmin extends StorPoolDetachVolumeCmd{
}