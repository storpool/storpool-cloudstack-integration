package org.apache.cloudstack.storage.helper;

import org.apache.cloudstack.api.APICommand;
import org.apache.cloudstack.api.ResponseObject.ResponseView;
import org.apache.cloudstack.api.response.SuccessResponse;

import com.cloud.vm.VirtualMachine;

@APICommand(name = "scaleVirtualMachine", description = "Scales the virtual machine to a new service offering. This command also takes into account the Volume and it may resize the root disk size according to the service offering.", responseObject = SuccessResponse.class, responseView = ResponseView.Full, entityType = {VirtualMachine.class},
requestHasSensitiveInfo = false, responseHasSensitiveInfo = false)
public class StorPoolScaleVMCmdByAdmin extends StorPoolScaleVMCmd {}
