package com.cloud.vm;

import javax.inject.Inject;

import org.apache.cloudstack.api.BaseAsyncCmd;
import org.apache.cloudstack.api.BaseAsyncCreateCmd;
import org.apache.cloudstack.api.BaseCmd;
import org.apache.cloudstack.api.command.user.vmsnapshot.CreateVMSnapshotCmd;
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
               throw new CloudRuntimeException( e.getMessage());
          } finally {
               try {
                    joinpoint.proceed();
               } catch (Throwable e) {
                    throw new CloudRuntimeException(e.getMessage());
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
}
