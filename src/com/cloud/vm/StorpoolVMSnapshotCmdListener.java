package com.cloud.vm;

import java.util.Map;
import java.util.Map.Entry;

import javax.inject.Inject;

import org.apache.cloudstack.api.BaseAsyncCmd;
import org.apache.cloudstack.api.BaseAsyncCreateCmd;
import org.apache.cloudstack.api.BaseCmd;
import org.apache.cloudstack.api.command.admin.vmsnapshot.RevertToVMSnapshotCmdByAdmin;
import org.apache.cloudstack.api.command.user.vmsnapshot.CreateVMSnapshotCmd;
import org.apache.cloudstack.api.command.user.vmsnapshot.DeleteVMSnapshotCmd;
import org.apache.cloudstack.api.command.user.vmsnapshot.RevertToVMSnapshotCmd;
import org.apache.log4j.Logger;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.springframework.aop.framework.Advised;
import org.springframework.aop.support.AopUtils;

import com.cloud.api.dispatch.DispatchTask;
import com.cloud.utils.exception.CloudRuntimeException;

@Aspect
public class StorpoolVMSnapshotCmdListener {

     private static final Logger log = Logger.getLogger(StorpoolVMSnapshotCmdListener.class);
     @Inject
     StorpoolVMSnapshotManagerImpl storpoolVMSnapshotManagerImpl;

     @Around("execution (* com.cloud.api.dispatch.CommandCreationWorker.handle(..)) ")
     public void aroundHandleForAllocateVMsnapshot(ProceedingJoinPoint joinpoint) {
          try {
               for (int i = 0; i < joinpoint.getArgs().length; i++) {
                    if (joinpoint.getArgs()[i] instanceof DispatchTask) {
                         DispatchTask task = (DispatchTask) joinpoint.getArgs()[i];
                         BaseCmd cmd = task.getCmd();
                         if (cmd instanceof BaseAsyncCreateCmd) {
                              if (cmd instanceof CreateVMSnapshotCmd) {
                                   CreateVMSnapshotCmd command = (CreateVMSnapshotCmd) cmd;
                                   getStorageProvider(command.getVmId(), command);
                              }
                         }
                    }
               }
          } catch (Exception e) {
               throw new CloudRuntimeException("Create VM snapshot failed do to: " + e.getMessage());
          } finally {
               try {
                    joinpoint.proceed();
               } catch (Throwable e) {
                    throw new CloudRuntimeException("Failed to proceed VM snapshot creation:" + e.getMessage());
               }
          }
     }

     @Around("execution (* com.cloud.api.ApiDispatcher.dispatch(..))")
     public void catchDispatch(ProceedingJoinPoint joinpoint) {
          Object[] parameters = joinpoint.getArgs();
          try {
               for (int i = 0; i < parameters.length; i++) {
                    if (parameters[i] instanceof BaseCmd) {
                         Long vmId = null;
                         if (parameters[i] instanceof DeleteVMSnapshotCmd) {
                              DeleteVMSnapshotCmd command = (DeleteVMSnapshotCmd) parameters[i];
                              vmId = findVmUuid(parameters, vmId);
                              getStorageProvider(vmId, command);
                         } else if (parameters[i] instanceof RevertToVMSnapshotCmd) {
                              RevertToVMSnapshotCmd command = (RevertToVMSnapshotCmd) parameters[i];
                              vmId = findVmUuid(parameters, vmId);
                              getStorageProvider(vmId, command);
                         } else if (parameters[i] instanceof RevertToVMSnapshotCmdByAdmin) {
                              RevertToVMSnapshotCmdByAdmin command = (RevertToVMSnapshotCmdByAdmin) parameters[i];
                              vmId = findVmUuid(parameters, vmId);
                              getStorageProvider(vmId, command);
                         }
                    }
               }
          } catch (Exception e) {
               throw new CloudRuntimeException("VM Snapshot reverting/delete failed due to:" + e.getMessage());
          } finally {
               try {
                    joinpoint.proceed();
               } catch (Throwable e) {
                    throw new CloudRuntimeException("Failed to proceed:" + e.getMessage());
               }
          }
     }

     private void getStorageProvider(Long vmId, BaseAsyncCmd command) {
          if (AopUtils.isAopProxy(command._vmSnapshotService) && command._vmSnapshotService instanceof Advised) {
               boolean isStorpoolProvider = storpoolVMSnapshotManagerImpl.getStorageProviderName(vmId);
               if (isStorpoolProvider) {
                    log.debug(String.format("Storpool provider=%s, vmID=%s", isStorpoolProvider, vmId));
                    command._vmSnapshotService = storpoolVMSnapshotManagerImpl;
               }
          }
     }

     private Long findVmUuid(Object[] parameters, Long vmId) {
          for (Object object : parameters) {
               if (object instanceof Map<?, ?>) {
                    Map<?, ?> params = (Map<?, ?>) object;
                    for (Entry<?, ?> param : params.entrySet()) {
                         if (param.getKey().equals("vmsnapshotid")) {
                              vmId = storpoolVMSnapshotManagerImpl.findVMSnapshotByUuid(param.getValue().toString());
                         }
                    }
               }
          }
          return vmId;
     }
}
