package com.cloud.vm;

import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Map;

import javax.inject.Inject;
import javax.naming.ConfigurationException;

import org.apache.cloudstack.context.CallContext;
import org.apache.cloudstack.engine.subsystem.api.storage.SnapshotDataFactory;
import org.apache.cloudstack.engine.subsystem.api.storage.SnapshotService;
import org.apache.cloudstack.engine.subsystem.api.storage.StorageStrategyFactory;
import org.apache.cloudstack.engine.subsystem.api.storage.VolumeDataFactory;
import org.apache.cloudstack.engine.subsystem.api.storage.VolumeInfo;
import org.apache.cloudstack.framework.config.dao.ConfigurationDao;
import org.apache.cloudstack.storage.datastore.db.PrimaryDataStoreDao;
import org.apache.cloudstack.storage.datastore.db.StoragePoolVO;
import org.apache.cloudstack.storage.to.VolumeObjectTO;
import org.apache.log4j.Logger;
import org.springframework.context.annotation.EnableAspectJAutoProxy;
import org.springframework.stereotype.Component;

import com.cloud.exception.InvalidParameterValueException;
import com.cloud.exception.ResourceAllocationException;
import com.cloud.gpu.GPU;
import com.cloud.hypervisor.Hypervisor.HypervisorType;
import com.cloud.hypervisor.dao.HypervisorCapabilitiesDao;
import com.cloud.service.dao.ServiceOfferingDetailsDao;
import com.cloud.storage.Snapshot;
import com.cloud.storage.SnapshotVO;
import com.cloud.storage.Storage.ImageFormat;
import com.cloud.storage.VolumeApiService;
import com.cloud.storage.VolumeVO;
import com.cloud.storage.dao.SnapshotDao;
import com.cloud.storage.dao.SnapshotDetailsDao;
import com.cloud.storage.dao.VolumeDao;
import com.cloud.user.Account;
import com.cloud.user.AccountManager;
import com.cloud.user.dao.AccountDao;
import com.cloud.uservm.UserVm;
import com.cloud.utils.DateUtil;
import com.cloud.utils.NumbersUtil;
import com.cloud.utils.exception.CloudRuntimeException;
import com.cloud.vm.dao.UserVmDao;
import com.cloud.vm.dao.VMInstanceDao;
import com.cloud.vm.snapshot.VMSnapshot;
import com.cloud.vm.snapshot.VMSnapshotManagerImpl;
import com.cloud.vm.snapshot.VMSnapshotVO;
import com.cloud.vm.snapshot.dao.VMSnapshotDao;

@Component
@EnableAspectJAutoProxy(proxyTargetClass = true)
public class StorpoolVMSnapshotManagerImpl extends VMSnapshotManagerImpl {
     private static final Logger s_logger = Logger.getLogger(StorpoolVMSnapshotManagerImpl.class);

     @Inject
     VMInstanceDao _vmInstanceDao;
     @Inject
     ServiceOfferingDetailsDao _serviceOfferingDetailsDao;
     @Inject
     public VMSnapshotDao _vmSnapshotDao;
     @Inject
     public VolumeDao _volumeDao;
     @Inject
     AccountDao _accountDao;
     @Inject
     public UserVmDao _userVMDao;
     @Inject
     AccountManager _accountMgr;
     @Inject
     SnapshotDao _snapshotDao;
     @Inject
     ConfigurationDao _configDao;
     @Inject
     HypervisorCapabilitiesDao _hypervisorCapabilitiesDao;
     @Inject
     StorageStrategyFactory storageStrategyFactory;
     @Inject
     VolumeDataFactory volumeDataFactory;
     @Inject
     SnapshotDataFactory snapshotFactory;
     @Inject
     SnapshotService snapshotService;
     @Inject
     VolumeApiService volumeService;
     @Inject
     SnapshotDetailsDao _snapshotDetailsDao;
     @Inject
     PrimaryDataStoreDao storagePool;

     int _vmSnapshotMax;
     int _wait;

     public StorpoolVMSnapshotManagerImpl() {
     }

     @Override
     public boolean configure(String name, Map<String, Object> params) throws ConfigurationException {
          _name = name;
          if (_configDao == null) {
               throw new ConfigurationException("Unable to get the configuration dao.");
          }

          _vmSnapshotMax = NumbersUtil.parseInt(_configDao.getValue("vmsnapshot.max"), VMSNAPSHOTMAX);

          String value = _configDao.getValue("vmsnapshot.create.wait");
          _wait = NumbersUtil.parseInt(value, 1800);

          return true;
     }

     protected Account getCaller() {
          return CallContext.current().getCallingAccount();
     }

     @Override
     public VMSnapshot allocVMSnapshot(Long vmId, String vsDisplayName, String vsDescription, Boolean snapshotMemory)
               throws ResourceAllocationException {
          s_logger.debug(String.format("StorpoolVMSnapshotManagerImpl.allocVMSnapshot vmId=%s, displayName=%s", vmId,
                    vsDisplayName));
          Account caller = getCaller();
          // check if VM exists
          UserVmVO userVmVo = _userVMDao.findById(vmId);
          if (userVmVo == null) {
               throw new InvalidParameterValueException(
                         "Creating VM snapshot failed due to VM:" + vmId + " is a system VM or does not exist");
          }

          // VM snapshot with memory is not supported for VGPU Vms
          if (snapshotMemory && _serviceOfferingDetailsDao.findDetail(userVmVo.getServiceOfferingId(),
                    GPU.Keys.vgpuType.toString()) != null) {
               throw new InvalidParameterValueException(
                         "VM snapshot with MEMORY is not supported for vGPU enabled VMs.");
          }

          // check hypervisor capabilities
          if (!_hypervisorCapabilitiesDao.isVmSnapshotEnabled(userVmVo.getHypervisorType(), "default"))
               throw new InvalidParameterValueException(
                         "VM snapshot is not enabled for hypervisor type: " + userVmVo.getHypervisorType());

          // parameter length check
          if (vsDisplayName != null && vsDisplayName.length() > 255)
               throw new InvalidParameterValueException(
                         "Creating VM snapshot failed due to length of VM snapshot vsDisplayName should not exceed 255");
          if (vsDescription != null && vsDescription.length() > 255)
               throw new InvalidParameterValueException(
                         "Creating VM snapshot failed due to length of VM snapshot vsDescription should not exceed 255");

          // VM snapshot display name must be unique for a VM
          String timeString = DateUtil.getDateDisplayString(DateUtil.GMT_TIMEZONE, new Date(),
                    DateUtil.YYYYMMDD_FORMAT);
          String vmSnapshotName = userVmVo.getInstanceName() + "_VS_" + timeString;
          if (vsDisplayName == null) {
               vsDisplayName = vmSnapshotName;
          }
          if (_vmSnapshotDao.findByName(vmId, vsDisplayName) != null) {
               throw new InvalidParameterValueException("Creating VM snapshot failed due to VM snapshot with name"
                         + vsDisplayName + "  already exists");
          }

          // check VM state
          if (userVmVo.getState() != VirtualMachine.State.Running
                    && userVmVo.getState() != VirtualMachine.State.Stopped) {
               throw new InvalidParameterValueException(
                         "Creating vm snapshot failed due to VM:" + vmId + " is not in the running or Stopped state");
          }

          if (snapshotMemory && userVmVo.getState() != VirtualMachine.State.Running) {
               throw new InvalidParameterValueException("Can not snapshot memory when VM is not in Running state");
          }

          // check access
          _accountMgr.checkAccess(caller, null, true, userVmVo);

          // check max snapshot limit for per VM
          if (_vmSnapshotDao.findByVm(vmId).size() >= _vmSnapshotMax) {
               throw new CloudRuntimeException("Creating vm snapshot failed due to a VM can just have : "
                         + _vmSnapshotMax + " VM snapshots. Please delete old ones");
          }

          // check if there are active volume snapshots tasks
          List<VolumeVO> listVolumes = _volumeDao.findByInstance(vmId);
          for (VolumeVO volume : listVolumes) {
               List<SnapshotVO> activeSnapshots = _snapshotDao.listByInstanceId(volume.getInstanceId(),
                         Snapshot.State.Creating, Snapshot.State.CreatedOnPrimary, Snapshot.State.BackingUp);
               if (activeSnapshots.size() > 0) {
                    throw new CloudRuntimeException(
                              "There is other active volume snapshot tasks on the instance to which the volume is attached, please try again later.");
               }
               if (userVmVo.getHypervisorType() == HypervisorType.KVM && volume.getFormat() != ImageFormat.QCOW2) {
                    throw new CloudRuntimeException("We only support create vm snapshots from vm with QCOW2 image");
               }
          }

          // check if there are other active VM snapshot tasks
          if (hasActiveVMSnapshotTasks(vmId)) {
               throw new CloudRuntimeException(
                         "There is other active vm snapshot tasks on the instance, please try again later");
          }

          VMSnapshot.Type vmSnapshotType = VMSnapshot.Type.Disk;
          if (snapshotMemory && userVmVo.getState() == VirtualMachine.State.Running)
               vmSnapshotType = VMSnapshot.Type.DiskAndMemory;

          try {
               return createAndPersistVMSnapshot(userVmVo, vsDescription, vmSnapshotName, vsDisplayName,
                         vmSnapshotType);
          } catch (Exception e) {
               String msg = e.getMessage();
               s_logger.error("Create vm snapshot record failed for vm: " + vmId + " due to: " + msg);
          }
          return null;
     }

     private List<VolumeObjectTO> getVolumeTOList(Long vmId) {
          List<VolumeObjectTO> volumeTOs = new ArrayList<VolumeObjectTO>();
          List<VolumeVO> volumeVos = _volumeDao.findByInstance(vmId);
          VolumeInfo volumeInfo = null;
          for (VolumeVO volume : volumeVos) {
               volumeInfo = volumeDataFactory.getVolume(volume.getId());

               volumeTOs.add((VolumeObjectTO) volumeInfo.getTO());
          }
          return volumeTOs;
     }

     public boolean getStorageProviderName(Long vmId) {
          s_logger.info("_userVMDao" + _userVMDao);
          UserVm userVm = _userVMDao.findById(vmId);
          List<VolumeObjectTO> volumeTOs = getVolumeTOList(userVm.getId());
          for (VolumeObjectTO volumeObjectTO : volumeTOs) {
               VolumeVO volumeVO = _volumeDao.findById(volumeObjectTO.getId());
               StoragePoolVO storagePoolVO = storagePool.findById(volumeVO.getPoolId());
               if (!storagePoolVO.getStorageProviderName().equals("StorPool")) {
                    return false;
               }
               s_logger.info("getStorageProviderName " + storagePoolVO);
          }
          s_logger.info("Storage provider is StorPool");
          return true;
     }

     public Long findVMSnapshotById(Long vmSnapShotId) {
          s_logger.debug("Find vm snapshot by id");
          VMSnapshotVO vmSnapshotVo = _vmSnapshotDao.findById(vmSnapShotId);
          return vmSnapshotVo.getVmId();
     }

     public Long findVMSnapshotByUuid(String vmSnapShotId) {
          s_logger.debug("Find vm snapshot by uuid");
          VMSnapshotVO vmSnapshotVo = _vmSnapshotDao.findByUuid(vmSnapShotId);
          return vmSnapshotVo.getVmId();
     }
}
