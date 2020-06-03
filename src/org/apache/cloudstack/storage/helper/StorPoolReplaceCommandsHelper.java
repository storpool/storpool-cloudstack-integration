package org.apache.cloudstack.storage.helper;

import java.lang.annotation.Annotation;
import java.lang.reflect.Field;
import java.lang.reflect.Proxy;
import java.lang.reflect.Type;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.List;
import java.util.Map;

import javax.inject.Inject;

import org.apache.cloudstack.acl.Role;
import org.apache.cloudstack.acl.RoleType;
import org.apache.cloudstack.acl.RoleVO;
import org.apache.cloudstack.acl.dao.RoleDao;
import org.apache.cloudstack.api.APICommand;
import org.apache.cloudstack.api.BaseAsyncCmd;
import org.apache.cloudstack.api.BaseAsyncCreateCmd;
import org.apache.cloudstack.api.command.admin.volume.AttachVolumeCmdByAdmin;
import org.apache.cloudstack.api.command.admin.volume.DetachVolumeCmdByAdmin;
import org.apache.cloudstack.api.command.user.tag.CreateTagsCmd;
import org.apache.cloudstack.api.command.user.tag.DeleteTagsCmd;
import org.apache.cloudstack.api.command.user.template.DeleteTemplateCmd;
import org.apache.cloudstack.api.command.user.vmsnapshot.CreateVMSnapshotCmd;
import org.apache.cloudstack.api.command.user.volume.AttachVolumeCmd;
import org.apache.cloudstack.api.command.user.volume.DetachVolumeCmd;
import org.apache.cloudstack.context.CallContext;
import org.apache.cloudstack.engine.subsystem.api.storage.VolumeDataFactory;
import org.apache.cloudstack.engine.subsystem.api.storage.VolumeInfo;
import org.apache.cloudstack.framework.jobs.AsyncJob;
import org.apache.cloudstack.storage.datastore.db.PrimaryDataStoreDao;
import org.apache.cloudstack.storage.datastore.db.StoragePoolVO;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil.SpConnectionDesc;
import org.apache.cloudstack.storage.to.VolumeObjectTO;
import org.apache.log4j.Logger;

import com.cloud.api.ApiGsonHelper;
import com.cloud.api.ApiServer;
import com.cloud.api.dispatch.DispatchChainFactory;
import com.cloud.api.dispatch.DispatchTask;
import com.cloud.exception.InvalidParameterValueException;
import com.cloud.exception.PermissionDeniedException;
import com.cloud.exception.ResourceAllocationException;
import com.cloud.gpu.GPU;
import com.cloud.hypervisor.Hypervisor.HypervisorType;
import com.cloud.hypervisor.dao.HypervisorCapabilitiesDao;
import com.cloud.hypervisor.kvm.storage.StorpoolStorageAdaptor;
import com.cloud.service.dao.ServiceOfferingDetailsDao;
import com.cloud.storage.Snapshot;
import com.cloud.storage.SnapshotVO;
import com.cloud.storage.Storage.ImageFormat;
import com.cloud.storage.StoragePool;
import com.cloud.storage.VolumeVO;
import com.cloud.storage.dao.SnapshotDao;
import com.cloud.storage.dao.VolumeDao;
import com.cloud.user.Account;
import com.cloud.user.AccountManager;
import com.cloud.uservm.UserVm;
import com.cloud.utils.DateUtil;
import com.cloud.utils.component.ComponentContext;
import com.cloud.utils.component.PluggableService;
import com.cloud.utils.exception.CloudRuntimeException;
import com.cloud.vm.UserVmVO;
import com.cloud.vm.VMInstanceVO;
import com.cloud.vm.VirtualMachine;
import com.cloud.vm.dao.UserVmDao;
import com.cloud.vm.dao.VMInstanceDao;
import com.cloud.vm.snapshot.VMSnapshot;
import com.cloud.vm.snapshot.VMSnapshotManager;
import com.cloud.vm.snapshot.VMSnapshotManagerImpl;
import com.cloud.vm.snapshot.VMSnapshotVO;
import com.cloud.vm.snapshot.dao.VMSnapshotDao;
import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;

public class StorPoolReplaceCommandsHelper implements PluggableService{
    private static final Logger log = Logger.getLogger(StorPoolReplaceCommandsHelper.class);

    private static StorPoolReplaceCommandsUtil replaceCommandsUtil;
    private ApiServer apiServer;

    public static StorPoolReplaceCommandsUtil getStorPoolReplaceCommandsUtil () {
        if (replaceCommandsUtil == null) {
            replaceCommandsUtil = ComponentContext.inject(StorPoolReplaceCommandsUtil.class);
        }
        return replaceCommandsUtil;
    }

    public void init() {
        this.apiServer = ComponentContext.getComponent(ApiServer.class);
        try {
           // addCommandsBeforeRealInit();
            changeAnnotations();
        } catch (Exception e) {
            log.info(e.getMessage());
        }
    }

    public void addCommandsBeforeRealInit() {
        try {
            Class<ApiServer> cls = ApiServer.class;
            Field field = cls.getDeclaredField("s_apiNameCmdClassMap");
            field.setAccessible(true);
            Object value = field.get(cls);
            Map<String, List<Class<?>>> commandsMap = (Map<String, List<Class<?>>>) value;
            List<Class<?>> set = new ArrayList<>(
                    Arrays.asList(
                            StorPoolAttachVolumeCmdByAdmin.class,
                            StorPoolAttachVolumeCmd.class,
                            StorPoolDetachVolumeCmd.class,
                            StorPoolDetachVolumeCmdByAdmin.class,
                            StorPoolCreateVMSnapshotCmd.class,
                            StorPoolCreateTagsCmd.class,
                            StorPoolDeleteTagsCmd.class,
                            StorPoolDeleteTemplateCmd.class));
            for (Class<?> clazz : set) {
                final APICommand at = clazz.getAnnotation(APICommand.class);
                String name = at.name();
                List<Class<?>> cmdList = commandsMap.get(name);
                if (cmdList == null) {
                    cmdList = new ArrayList<>();
                    commandsMap.put(name, cmdList);
                }
                cmdList.add(clazz);
            }
        } catch (NoSuchFieldException | IllegalAccessException e) {
            log.error(e.getMessage());
        }
    }

    //Removing real CloudStack commands' names with "". This will help to initialize and work with StorPool's commands
    private static void changeAnnotations() {
        List<Annotation> annotations = new ArrayList<>(Arrays.asList(
                AttachVolumeCmd.class.getAnnotation(APICommand.class),
                AttachVolumeCmdByAdmin.class.getAnnotation(APICommand.class),
                DetachVolumeCmd.class.getAnnotation(APICommand.class),
                DetachVolumeCmdByAdmin.class.getAnnotation(APICommand.class),
                CreateTagsCmd.class.getAnnotation(APICommand.class),
                DeleteTagsCmd.class.getAnnotation(APICommand.class),
                CreateVMSnapshotCmd.class.getAnnotation(APICommand.class),
                DeleteTemplateCmd.class.getAnnotation(APICommand.class)
                ));
        changeAnnotationValue(annotations, "name", "");
    }

    public static void changeAnnotationValue(List<Annotation> annotations, String key, Object newValue){
        for (Annotation annotation : annotations) {
            Object handler = Proxy.getInvocationHandler(annotation);
            Field field;
            try {
                field = handler.getClass().getDeclaredField("memberValues");
            } catch (NoSuchFieldException | SecurityException e) {
                throw new IllegalStateException(e);
            }
            field.setAccessible(true);
            Map<String, Object> memberValues;
            try {
                memberValues = (Map<String, Object>) field.get(handler);
            } catch (IllegalArgumentException | IllegalAccessException e) {
                throw new IllegalStateException(e);
            }
            Object oldValue = memberValues.get(key);
            if (oldValue == null || oldValue.getClass() != newValue.getClass()) {
                throw new IllegalArgumentException();
            }
            memberValues.put(key,newValue);
            StorpoolUtil.spLog("CloudStack command old value=%s, replaced with new value=%s", oldValue, newValue);
        }
    }

    @Override
    public List<Class<?>> getCommands() {
        final List<Class<?>> cmdList = new ArrayList<Class<?>>(
                Arrays.asList(
                        StorPoolAttachVolumeCmdByAdmin.class,
                        StorPoolAttachVolumeCmd.class,
                        StorPoolDetachVolumeCmd.class,
                        StorPoolDetachVolumeCmdByAdmin.class,
                        StorPoolCreateVMSnapshotCmd.class,
                        StorPoolCreateTagsCmd.class,
                        StorPoolDeleteTagsCmd.class,
                        StorPoolDeleteTemplateCmd.class));
        return cmdList;
    }

    public static class StorPoolReplaceCommandsUtil extends VMSnapshotManagerImpl{
        @Inject
        private DispatchChainFactory dispatchChainFactory;
        @Inject
        private VolumeDao volumeDao;
        @Inject
        private VolumeDataFactory volumeDataFactory;
        @Inject
        private ServiceOfferingDetailsDao _serviceOfferingDetailsDao;
        @Inject
        private VMSnapshotDao _vmSnapshotDao;
        @Inject
        private VolumeDao _volumeDao;
        @Inject
        private  UserVmDao _userVMDao;
        @Inject
        private AccountManager _accountMgr;
        @Inject
        private SnapshotDao _snapshotDao;
        @Inject
        private HypervisorCapabilitiesDao _hypervisorCapabilitiesDao;
        @Inject
        private PrimaryDataStoreDao storagePool;
        @Inject
        private VMInstanceDao _vmInstanceDao;
        @Inject
        private RoleDao roleDao;
        @Inject
        private AccountManager accountManager;

        private int _vmSnapshotMax = VMSnapshotManager.VMSNAPSHOTMAX;

        void ensureCmdHasRequiredValues(BaseAsyncCmd targetCmd, BaseAsyncCmd fakeCmd ) {
            if (fakeCmd.getFullUrlParams() != null && targetCmd.getFullUrlParams() == null) {
                dispatchChainFactory.getStandardDispatchChain().dispatch(new DispatchTask(targetCmd, fakeCmd.getFullUrlParams()));
            }
            if (fakeCmd.getHttpMethod() != null && targetCmd.getHttpMethod() == null) {
                targetCmd.setHttpMethod(fakeCmd.getHttpMethod().toString());
            }
            if (fakeCmd.getResponseType() != null) {
                targetCmd.setResponseType(fakeCmd.getResponseType());
            }
            if (fakeCmd.getFullUrlParams() == null && targetCmd.getFullUrlParams() == null) {
                Type mapType = new TypeToken<Map<String, String>>() {
                }.getType();
                AsyncJob job = (AsyncJob) fakeCmd.getJob();
                targetCmd.setJob(job);
                Gson gson = ApiGsonHelper.getBuilder().create();
                Map<String, String> params = gson.fromJson(job.getCmdInfo(), mapType);
                dispatchChainFactory.getStandardDispatchChain().dispatch(new DispatchTask(targetCmd, params));

                if (targetCmd instanceof BaseAsyncCreateCmd) {
                    BaseAsyncCreateCmd create = (BaseAsyncCreateCmd)targetCmd;
                    create.setEntityId(Long.parseLong(params.get("id")));
                    create.setEntityUuid(params.get("uuid"));
                }
            }
        }

        void updateVolumeTags(Long volumeID, Long vmId, String ... value) {
            VolumeVO volume = volumeDao.findById(volumeID);
            VolumeInfo volumeObjectTO = volumeDataFactory.getVolume(volumeID);
            log.info(String.format("Volume id=%s, name=%s, instanceId=%s, path=%s", volume.getId(), volume.getName(),
                    volume.getInstanceId(), volume.getPath()));
            StoragePool pool = (StoragePool) volumeObjectTO.getDataStore();
            String name = StorpoolStorageAdaptor.getVolumeNameFromPath(volume.getPath(), true);
            if (name != null && pool.getStorageProviderName().equals(StorpoolUtil.SP_PROVIDER_NAME)) {
                SpConnectionDesc conn = new SpConnectionDesc(volumeObjectTO.getDataStore().getUuid());
                    log.debug(String.format("Updating StorPool's volume=%s tags", name));
                    VMInstanceVO vm = _vmInstanceDao.findById(vmId);
                    StorpoolUtil.volumeUpadateTags(name, vm != null ? vm.getUuid() : "", conn, value.length > 0 ? value[0] : "");
            }
        }

        public VMSnapshot allocVMSnapshot(Long vmId, String vsDisplayName, String vsDescription, Boolean snapshotMemory)
                throws ResourceAllocationException {
           log.debug(String.format("StorpoolVMSnapshotManagerImpl.allocVMSnapshot vmId=%s, displayName=%s", vmId,
                     vsDisplayName));
           Account caller = CallContext.current().getCallingAccount();
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
           if (snapshotMemory && userVmVo.getState() == VirtualMachine.State.Running) {
                throw new CloudRuntimeException("VM snapshot with memory is not supported operation");
           }

           try {
                return createAndPersistVMSnapshot(userVmVo, vsDescription, vmSnapshotName, vsDisplayName,
                          vmSnapshotType);
           } catch (Exception e) {
                String msg = e.getMessage();
                log.error("Create vm snapshot record failed for vm: " + vmId + " due to: " + msg);
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
            log.info("_userVMDao" + _userVMDao);
            UserVm userVm = _userVMDao.findById(vmId);
            List<VolumeObjectTO> volumeTOs = getVolumeTOList(userVm.getId());
            for (VolumeObjectTO volumeObjectTO : volumeTOs) {
                 VolumeVO volumeVO = _volumeDao.findById(volumeObjectTO.getId());
                 StoragePoolVO storagePoolVO = storagePool.findById(volumeVO.getPoolId());
                 if (!storagePoolVO.getStorageProviderName().equals("StorPool")) {
                      return false;
                 }
                 log.info("getStorageProviderName " + storagePoolVO);
            }
            log.info("Storage provider is StorPool");
            return true;
       }

       public Long findVMSnapshotById(Long vmSnapShotId) {
            log.debug("Find vm snapshot by id");
            VMSnapshotVO vmSnapshotVo = _vmSnapshotDao.findById(vmSnapShotId);
            return vmSnapshotVo.getVmId();
       }

       public Long findVMSnapshotByUuid(String vmSnapShotId) {
            log.debug("Find vm snapshot by uuid");
            VMSnapshotVO vmSnapshotVo = _vmSnapshotDao.findByUuid(vmSnapShotId);
            return vmSnapshotVo.getVmId();
       }

        public boolean hasRights(String value) {
            if (value != null) {
                Account caller = getCurrentAccount();
                if (caller == null || caller.getRoleId() == null) {
                    throw new PermissionDeniedException("Restricted API called by an invalid user account");
                }
                Role callerRole = findRole(caller.getRoleId());
                if (callerRole == null || callerRole.getRoleType() != RoleType.Admin) {
                    throw new PermissionDeniedException(
                            "Restricted API called by an user account of non-Admin role type");
                }
            }
            return true;
        }

        private Role findRole(Long id) {
            if (id == null || id < 1L) {
                log.trace(String.format("Role ID is invalid [%s]", id));
                return null;
            }
            RoleVO role = roleDao.findById(id);
            if (role == null) {
                log.trace(String.format("Role not found [id=%s]", id));
                return null;
            }
            Account account = getCurrentAccount();
            if (!accountManager.isRootAdmin(account.getId()) && RoleType.Admin == role.getRoleType()) {
                log.debug(
                        String.format("Role [id=%s, name=%s] is of 'Admin' type and is only visible to 'Root admins'.",
                                id, role.getName()));
                return null;
            }
            return role;
        }

        private Account getCurrentAccount() {
            return CallContext.current().getCallingAccount();
        }
    }
}
