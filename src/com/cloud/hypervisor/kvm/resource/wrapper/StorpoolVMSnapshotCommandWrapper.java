//
// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements.  See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership.  The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License.  You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied.  See the License for the
// specific language governing permissions and limitations
// under the License.
//
package com.cloud.hypervisor.kvm.resource.wrapper;

import java.util.List;

import org.apache.cloudstack.storage.datastore.util.StorpoolUtil;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil.SpApiResponse;
import org.apache.cloudstack.storage.to.VolumeObjectTO;
import org.apache.log4j.Logger;

import com.cloud.agent.api.Answer;
import com.cloud.agent.api.storage.StorpoolCreateVMSnapshotAnswer;
import com.cloud.agent.api.storage.StorpoolCreateVMSnapshotCommand;
import com.cloud.hypervisor.kvm.resource.LibvirtComputingResource;
import com.cloud.resource.CommandWrapper;
import com.cloud.resource.ResourceWrapper;
import com.cloud.utils.exception.CloudRuntimeException;

@ResourceWrapper(handles = StorpoolCreateVMSnapshotCommand.class)
public class StorpoolVMSnapshotCommandWrapper
          extends CommandWrapper<StorpoolCreateVMSnapshotCommand, Answer, LibvirtComputingResource> {
     private static final Logger log = Logger.getLogger(StorpoolCreateVMSnapshotCommand.class);

     @Override
     public Answer execute(StorpoolCreateVMSnapshotCommand command, LibvirtComputingResource serverResource) {
          log.info("StorpoolVMSnapshotCommandWrapper");
          List<VolumeObjectTO> volumeTOs = command.getVolumeTOs();
          Long vmId = command.getVmId();
          SpApiResponse resp = StorpoolUtil.volumesGroupSnapshot(volumeTOs, vmId, command.getVmUuid());
          log.info("StorpoolVMSnapshotCommandWrapper ");
          log.debug(String.format("  SpApiResponse response=%s ", resp));
          String err =null;
          try {
          if (resp.getError() != null) {
              err = String.format("Could not create storpool vm error=%s",resp.getError());
              log.error("Could not create snapshot for vm:" + err);
              return new StorpoolCreateVMSnapshotAnswer(command, false, err);
          }

          return new StorpoolCreateVMSnapshotAnswer(command, command.getTarget(), command.getVolumeTOs());
          }catch (Exception e) {
               // TODO: handle exception
               log.error("CreateKVMVMSnapshotAnswer exception:" + e.getMessage());
               throw new CloudRuntimeException("CreateKVMVMSnapshotAnswer failed:" + e.getMessage());
          }
     }
}
