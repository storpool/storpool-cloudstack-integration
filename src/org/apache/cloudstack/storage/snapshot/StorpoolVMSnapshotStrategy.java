//
//Licensed to the Apache Software Foundation (ASF) under one
//or more contributor license agreements.  See the NOTICE file
//distributed with this work for additional information
//regarding copyright ownership.  The ASF licenses this file
//to you under the Apache License, Version 2.0 (the
//"License"); you may not use this file except in compliance
//with the License.  You may obtain a copy of the License at
//
//http://www.apache.org/licenses/LICENSE-2.0
//
//Unless required by applicable law or agreed to in writing,
//software distributed under the License is distributed on an
//"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
//KIND, either express or implied.  See the License for the
//specific language governing permissions and limitations
//under the License.
//
package org.apache.cloudstack.storage.snapshot;

import java.security.InvalidParameterException;
import java.util.HashMap;
import java.util.List;

import javax.inject.Inject;

import org.apache.cloudstack.engine.subsystem.api.storage.StrategyPriority;
import org.apache.cloudstack.engine.subsystem.api.storage.VMSnapshotOptions;
import org.apache.cloudstack.framework.config.dao.ConfigurationDao;
import org.apache.cloudstack.storage.datastore.db.PrimaryDataStoreDao;
import org.apache.cloudstack.storage.datastore.db.StoragePoolVO;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil;
import org.apache.cloudstack.storage.to.VolumeObjectTO;
import org.apache.cloudstack.storage.vmsnapshot.DefaultVMSnapshotStrategy;
import org.apache.cloudstack.storage.vmsnapshot.VMSnapshotHelper;
import org.apache.log4j.Logger;
import org.springframework.stereotype.Component;

import com.cloud.agent.AgentManager;
import com.cloud.agent.api.Answer;
import com.cloud.agent.api.VMSnapshotTO;
import com.cloud.agent.api.storage.StorpoolCreateVMSnapshotAnswer;
import com.cloud.agent.api.storage.StorpoolCreateVMSnapshotCommand;
import com.cloud.agent.api.storage.StorpoolDeleteSnapshotVMCommand;
import com.cloud.agent.api.storage.StorpoolDeleteVMSnapshotAnswer;
import com.cloud.agent.api.storage.StorpoolRevertToVMSnapshotAnswer;
import com.cloud.agent.api.storage.StorpoolRevertToVMSnapshotCommand;
import com.cloud.agent.api.to.DataStoreTO;
import com.cloud.event.EventTypes;
import com.cloud.event.UsageEventUtils;
import com.cloud.exception.AgentUnavailableException;
import com.cloud.exception.OperationTimedoutException;
import com.cloud.host.HostVO;
import com.cloud.host.dao.HostDao;
import com.cloud.storage.DiskOfferingVO;
import com.cloud.storage.GuestOSHypervisorVO;
import com.cloud.storage.GuestOSVO;
import com.cloud.storage.Storage;
import com.cloud.storage.VolumeVO;
import com.cloud.storage.dao.DiskOfferingDao;
import com.cloud.storage.dao.GuestOSDao;
import com.cloud.storage.dao.GuestOSHypervisorDao;
import com.cloud.storage.dao.VolumeDao;
import com.cloud.uservm.UserVm;
import com.cloud.utils.db.Transaction;
import com.cloud.utils.db.TransactionCallbackWithExceptionNoReturn;
import com.cloud.utils.db.TransactionStatus;
import com.cloud.utils.exception.CloudRuntimeException;
import com.cloud.utils.fsm.NoTransitionException;
import com.cloud.vm.UserVmVO;
import com.cloud.vm.VirtualMachineManager;
import com.cloud.vm.VirtualMachineProfile;
import com.cloud.vm.dao.UserVmDao;
import com.cloud.vm.dao.VMInstanceDao;
import com.cloud.vm.snapshot.VMSnapshot;
import com.cloud.vm.snapshot.VMSnapshotVO;
import com.cloud.vm.snapshot.dao.VMSnapshotDao;

@Component
public class StorpoolVMSnapshotStrategy extends DefaultVMSnapshotStrategy {
     private static final Logger log = Logger.getLogger(StorpoolVMSnapshotStrategy.class);

     @Inject
     VMSnapshotHelper vmSnapshotHelper;
     @Inject
     GuestOSDao guestOSDao;
     @Inject
     GuestOSHypervisorDao guestOsHypervisorDao;
     @Inject
     UserVmDao userVmDao;
     @Inject
     VMSnapshotDao vmSnapshotDao;
     int _wait;
     @Inject
     ConfigurationDao configurationDao;
     @Inject
     AgentManager agentMgr;
     @Inject
     VolumeDao volumeDao;
     @Inject
     DiskOfferingDao diskOfferingDao;
     @Inject
     HostDao hostDao;

     @Inject
     VMInstanceDao vmInstance;
     @Inject
     PrimaryDataStoreDao storagePool;
     @Inject
     VirtualMachineManager virtManager;

     @Override
     public VMSnapshot takeVMSnapshot(VMSnapshot vmSnapshot) {
          // TODO Auto-generated method stub
          log.info("KVMVMSnapshotStrategy take snapshot");
          Long hostId = vmSnapshotHelper.pickRunningHost(vmSnapshot.getVmId());
          UserVm userVm = userVmDao.findById(vmSnapshot.getVmId());
          VMSnapshotVO vmSnapshotVO = (VMSnapshotVO) vmSnapshot;

          try {
               vmSnapshotHelper.vmSnapshotStateTransitTo(vmSnapshotVO, VMSnapshot.Event.CreateRequested);
          } catch (NoTransitionException e) {
               // TODO: handle exception
               throw new CloudRuntimeException(e.getMessage());
          }

          StorpoolCreateVMSnapshotAnswer answer = null;
          boolean result = false;
          try {
               GuestOSVO guestOS = guestOSDao.findById(userVm.getGuestOSId());

               List<VolumeObjectTO> volumeTOs = vmSnapshotHelper.getVolumeTOList(userVm.getId());

               long prev_chain_size = 0;
               long virtual_size = 0;
               for (VolumeObjectTO volume : volumeTOs) {
                    virtual_size += volume.getSize();
                    VolumeVO volumeVO = volumeDao.findById(volume.getId());
                    prev_chain_size += volumeVO.getVmSnapshotChainSize() == null ? 0
                              : volumeVO.getVmSnapshotChainSize();
                    StoragePoolVO storagePoolVO = storagePool.findById(volumeVO.getPoolId());
                    log.info("Storage pool " + storagePoolVO.getPoolType());
                    if (storagePoolVO.getPoolType().equals(Storage.StoragePoolType.NetworkFilesystem)) {
                         throw new InvalidParameterException("Not supported command");
                    }
               }

               VMSnapshotTO current = null;
               VMSnapshotVO currentSnapshot = vmSnapshotDao.findCurrentSnapshotByVmId(userVm.getId());
               if (currentSnapshot != null) {
                    current = vmSnapshotHelper.getSnapshotWithParents(currentSnapshot);
               }
               VMSnapshotOptions options = ((VMSnapshotVO) vmSnapshot).getOptions();
               boolean quiescevm = true;
               if (options != null) {
                    quiescevm = options.needQuiesceVM();
               }
               VMSnapshotTO target = new VMSnapshotTO(vmSnapshot.getId(), vmSnapshot.getName(), vmSnapshot.getType(),
                         null, vmSnapshot.getDescription(), false, current, quiescevm);
               if (current == null) {
                    vmSnapshotVO.setParent(null);
               } else {
                    vmSnapshotVO.setParent(current.getId());
               }

               HostVO host = hostDao.findById(hostId);
               GuestOSHypervisorVO guestOsMapping = guestOsHypervisorDao.findByOsIdAndHypervisor(guestOS.getId(),
                         host.getHypervisorType().toString(), host.getHypervisorVersion());

               StorpoolCreateVMSnapshotCommand cmd = new StorpoolCreateVMSnapshotCommand(vmSnapshot.getUuid(),
                         vmSnapshotVO.getUuid(), userVm.getId(), target, volumeTOs, guestOS.getDisplayName());
               if (guestOsMapping == null) {
                    cmd.setPlatformEmulator(null);
               } else {
                    cmd.setPlatformEmulator(guestOsMapping.getGuestOsName());
               }
               cmd.setWait(_wait);

               answer = (StorpoolCreateVMSnapshotAnswer) agentMgr.send(hostId, cmd);
               log.info("CreateKVMVMSnapshotAnswer answer" + answer.getDetails());
               if (answer != null && answer.getResult()) {
                    processAnswer(vmSnapshotVO, userVm, answer, hostId);
                    result = true;
                    long new_chain_size = 0;
                    for (VolumeObjectTO volumeObjectTO : answer.getVolumeTOs()) {
                         publishUsageEvent(EventTypes.EVENT_VM_SNAPSHOT_CREATE, vmSnapshot, userVm, volumeObjectTO);
                         new_chain_size += volumeObjectTO.getSize();
                         log.info("EventTypes.EVENT_VM_SNAPSHOT_CREATE publishUsageEvent" + volumeObjectTO);
                    }
                    publishUsageEvent(EventTypes.EVENT_VM_SNAPSHOT_ON_PRIMARY, vmSnapshot, userVm,
                              new_chain_size - prev_chain_size, virtual_size);
               } else {
                    throw new CloudRuntimeException("Could not create vm snapshot:" + answer.getDetails());
               }
               return vmSnapshot;
          } catch (Exception e) {
               log.debug("Could not create VM snapshot:" + e.getMessage());
               throw new CloudRuntimeException("Could not create VM snapshot:" + e.getMessage());
          } finally {
               if (!result) {
                    try {
                         vmSnapshotHelper.vmSnapshotStateTransitTo(vmSnapshot, VMSnapshot.Event.OperationFailed);
                         log.info(String.format("VMSnapshot.Event.OperationFailed vmSnapshot=%s", vmSnapshot));
                    } catch (NoTransitionException e2) {
                         log.error("Cannot set vm state:" + e2.getMessage());
                    }
               }
          }
     }

     @Override
     public StrategyPriority canHandle(VMSnapshot vmSnapshot) {
          UserVm userVm = userVmDao.findById(vmSnapshot.getVmId());
          List<VolumeObjectTO> volumeTOs = vmSnapshotHelper.getVolumeTOList(userVm.getId());
          for (VolumeObjectTO volumeObjectTO : volumeTOs) {
               DataStoreTO dataStrore = volumeObjectTO.getDataStore();
               log.info(String.format("Datastore=%s", dataStrore));
               VolumeVO volumeVO = volumeDao.findById(volumeObjectTO.getId());
               StoragePoolVO storagePoolVO = storagePool.findById(volumeVO.getPoolId());
               if (!storagePoolVO.getStorageProviderName().equals(StorpoolUtil.SP_PROVIDER_NAME)) {
                    return StrategyPriority.CANT_HANDLE;
               }
          }
          log.info("KVMVMSnapshotStrategy canHandle");
          return StrategyPriority.HIGHEST;
     }

     @Override
     public boolean deleteVMSnapshot(VMSnapshot vmSnapshot) {
          log.info("In KVMVMSnapshotStrategy delete vm snapshot");
          UserVmVO userVm = userVmDao.findById(vmSnapshot.getVmId());
          VMSnapshotVO vmSnapshotVO = (VMSnapshotVO) vmSnapshot;
          try {
               vmSnapshotHelper.vmSnapshotStateTransitTo(vmSnapshot, VMSnapshot.Event.ExpungeRequested);
          } catch (NoTransitionException e) {
               log.debug("Failed to change vm snapshot state with event ExpungeRequested");
               throw new CloudRuntimeException(
                         "Failed to change vm snapshot state with event ExpungeRequested: " + e.getMessage());
          }

          try {
               Long hostId = vmSnapshotHelper.pickRunningHost(vmSnapshot.getVmId());

               List<VolumeObjectTO> volumeTOs = vmSnapshotHelper.getVolumeTOList(vmSnapshot.getVmId());

               String vmInstanceName = vmSnapshot.getUuid();
               VMSnapshotTO parent = vmSnapshotHelper.getSnapshotWithParents(vmSnapshotVO).getParent();
               VMSnapshotTO vmSnapshotTO = new VMSnapshotTO(vmSnapshot.getId(), vmSnapshot.getName(),
                         vmSnapshot.getType(), vmSnapshot.getCreated().getTime(), vmSnapshot.getDescription(),
                         vmSnapshot.getCurrent(), parent, true);
               GuestOSVO guestOS = guestOSDao.findById(userVm.getGuestOSId());
               StorpoolDeleteSnapshotVMCommand deleteSnapshotCommand = new StorpoolDeleteSnapshotVMCommand(
                         vmInstanceName, vmSnapshotTO, volumeTOs, guestOS.getDisplayName());

               Answer answer = agentMgr.send(hostId, deleteSnapshotCommand);

               log.debug("Delete vm nsapshot answer" + answer);
               if (answer != null && answer.getResult()) {
                    StorpoolDeleteVMSnapshotAnswer deleteVMSnapshotAnswer = (StorpoolDeleteVMSnapshotAnswer) answer;
                    processAnswer(vmSnapshotVO, userVm, answer, hostId);
                    long full_chain_size = 0;
                    for (VolumeObjectTO volumeTo : deleteVMSnapshotAnswer.getVolumeTOs()) {
                         publishUsageEvent(EventTypes.EVENT_VM_SNAPSHOT_DELETE, vmSnapshot, userVm, volumeTo);
                         full_chain_size += volumeTo.getSize();
                    }
                    publishUsageEvent(EventTypes.EVENT_VM_SNAPSHOT_OFF_PRIMARY, vmSnapshot, userVm, full_chain_size,
                              0L);
                    return true;
               } else {
                    String errMsg = (answer == null) ? null : answer.getDetails();
                    log.error("Delete vm snapshot " + vmSnapshot.getName() + " of vm " + userVm.getInstanceName()
                              + " failed due to " + errMsg);
                    throw new CloudRuntimeException("Delete vm snapshot " + vmSnapshot.getName() + " of vm "
                              + userVm.getInstanceName() + " failed due to " + errMsg);
               }
          } catch (OperationTimedoutException e) {
               throw new CloudRuntimeException("Delete vm snapshot " + vmSnapshot.getName() + " of vm "
                         + userVm.getInstanceName() + " failed due to " + e.getMessage());
          } catch (AgentUnavailableException e) {
               throw new CloudRuntimeException("Delete vm snapshot " + vmSnapshot.getName() + " of vm "
                         + userVm.getInstanceName() + " failed due to " + e.getMessage());
          }
     }

     @Override
     public boolean deleteVMSnapshotFromDB(VMSnapshot vmSnapshot) {
          log.debug("Deleting vm snapshot from db");
          return deleteVMSnapshot(vmSnapshot);
     }

     @Override
     public boolean revertVMSnapshot(VMSnapshot vmSnapshot) {
          log.debug("Revert vm snapshot");
          VMSnapshotVO vmSnapshotVO = (VMSnapshotVO) vmSnapshot;
          UserVmVO userVm = userVmDao.findById(vmSnapshot.getVmId());
          try {
               vmSnapshotHelper.vmSnapshotStateTransitTo(vmSnapshotVO, VMSnapshot.Event.RevertRequested);
          } catch (NoTransitionException e) {
               throw new CloudRuntimeException(e.getMessage());
          }

          boolean result = false;
          try {
               VMSnapshotVO snapshot = vmSnapshotDao.findById(vmSnapshotVO.getId());
               List<VolumeObjectTO> volumeTOs = vmSnapshotHelper.getVolumeTOList(userVm.getId());
               String vmInstanceName = vmSnapshot.getUuid();
               VMSnapshotTO parent = vmSnapshotHelper.getSnapshotWithParents(snapshot).getParent();

               VMSnapshotTO vmSnapshotTO = new VMSnapshotTO(snapshot.getId(), snapshot.getName(), snapshot.getType(),
                         snapshot.getCreated().getTime(), snapshot.getDescription(), snapshot.getCurrent(), parent,
                         true);
               Long hostId = vmSnapshotHelper.pickRunningHost(vmSnapshot.getVmId());
               GuestOSVO guestOS = guestOSDao.findById(userVm.getGuestOSId());
               StorpoolRevertToVMSnapshotCommand revertToSnapshotCommand = new StorpoolRevertToVMSnapshotCommand(
                         vmInstanceName, userVm.getUuid(), vmSnapshotTO, volumeTOs, guestOS.getDisplayName());
               HostVO host = hostDao.findById(hostId);
               GuestOSHypervisorVO guestOsMapping = guestOsHypervisorDao.findByOsIdAndHypervisor(guestOS.getId(),
                         host.getHypervisorType().toString(), host.getHypervisorVersion());
               if (guestOsMapping == null) {
                    revertToSnapshotCommand.setPlatformEmulator(null);
               } else {
                    revertToSnapshotCommand.setPlatformEmulator(guestOsMapping.getGuestOsName());
               }

               StorpoolRevertToVMSnapshotAnswer answer = (StorpoolRevertToVMSnapshotAnswer) agentMgr.send(hostId,
                         revertToSnapshotCommand);
               if (answer != null && answer.getResult()) {
                    processAnswer(vmSnapshotVO, userVm, answer, hostId);
                    result = true;
               } else {
                    String errMsg = "Revert VM: " + userVm.getInstanceName() + " to snapshot: " + vmSnapshotVO.getName()
                              + " failed";
                    if (answer != null && answer.getDetails() != null)
                         errMsg = errMsg + " due to " + answer.getDetails();
                    log.error(errMsg);
                    throw new CloudRuntimeException(errMsg);
               }
          } catch (OperationTimedoutException e) {
               log.debug("Failed to revert vm snapshot", e);
               throw new CloudRuntimeException(e.getMessage());
          } catch (AgentUnavailableException e) {
               log.debug("Failed to revert vm snapshot", e);
               throw new CloudRuntimeException(e.getMessage());
          } finally {
               if (!result) {
                    try {
                         vmSnapshotHelper.vmSnapshotStateTransitTo(vmSnapshot, VMSnapshot.Event.OperationFailed);
                    } catch (NoTransitionException e1) {
                         log.error("Cannot set vm snapshot state due to: " + e1.getMessage());
                    }
               } else {
                    try {
                         virtManager.advanceStart(userVm.getUuid(), new HashMap<VirtualMachineProfile.Param, Object>(),
                                   null);
                    } catch (Exception e) {
                         throw new CloudRuntimeException("Could not start VM:" + e.getMessage());
                    }
               }
          }
          return result;
     }

     @Override
     protected void processAnswer(VMSnapshotVO vmSnapshot, UserVm userVm, Answer as, Long hostId) {
          try {
               Transaction.execute(new TransactionCallbackWithExceptionNoReturn<NoTransitionException>() {
                    @Override
                    public void doInTransactionWithoutResult(TransactionStatus status) throws NoTransitionException {
                         if (as instanceof StorpoolCreateVMSnapshotAnswer) {
                              log.info("Transaction exacute" + as);
                              StorpoolCreateVMSnapshotAnswer answer = (StorpoolCreateVMSnapshotAnswer) as;
                              finalizeCreate(vmSnapshot, answer.getVolumeTOs());
                              vmSnapshotHelper.vmSnapshotStateTransitTo(vmSnapshot,
                                        VMSnapshot.Event.OperationSucceeded);
                         } else if (as instanceof StorpoolDeleteVMSnapshotAnswer) {
                              StorpoolDeleteVMSnapshotAnswer answer = (StorpoolDeleteVMSnapshotAnswer) as;
                              finalizeDelete(vmSnapshot, answer.getVolumeTOs());
                              vmSnapshotHelper.vmSnapshotStateTransitTo(vmSnapshot,
                                        VMSnapshot.Event.OperationSucceeded);
                         } else if (as instanceof StorpoolRevertToVMSnapshotAnswer) {
                              StorpoolRevertToVMSnapshotAnswer answer = (StorpoolRevertToVMSnapshotAnswer) as;
                              finalizeRevert(vmSnapshot, answer.getVolumeTOs());
                              vmSnapshotHelper.vmSnapshotStateTransitTo(vmSnapshot,
                                        VMSnapshot.Event.OperationSucceeded);
                         }
                    }
               });
          } catch (Exception e) {
               String errMsg = "Error while process answer: " + as.getClass() + " due to " + e.getMessage();
               log.error(errMsg, e);
               throw new CloudRuntimeException(errMsg);
          }
     }

     private void publishUsageEvent(String type, VMSnapshot vmSnapshot, UserVm userVm, VolumeObjectTO volumeTo) {
          VolumeVO volume = volumeDao.findById(volumeTo.getId());
          Long diskOfferingId = volume.getDiskOfferingId();
          Long offeringId = null;
          if (diskOfferingId != null) {
               DiskOfferingVO offering = diskOfferingDao.findById(diskOfferingId);
               if (offering != null && (offering.getType() == DiskOfferingVO.Type.Disk)) {
                    offeringId = offering.getId();
               }
          }
          UsageEventUtils.publishUsageEvent(type, vmSnapshot.getAccountId(), userVm.getDataCenterId(), userVm.getId(),
                    vmSnapshot.getName(), offeringId, volume.getId(), // save volume's id into templateId field
                    volumeTo.getSize(), VMSnapshot.class.getName(), vmSnapshot.getUuid());
     }

     private void publishUsageEvent(String type, VMSnapshot vmSnapshot, UserVm userVm, Long vmSnapSize,
               Long virtualSize) {
          try {
               UsageEventUtils.publishUsageEvent(type, vmSnapshot.getAccountId(), userVm.getDataCenterId(),
                         userVm.getId(), vmSnapshot.getName(), 0L, 0L, vmSnapSize, virtualSize,
                         VMSnapshot.class.getName(), vmSnapshot.getUuid());
          } catch (Exception e) {
               log.error("Failed to publis usage event " + type, e);
          }
     }
}