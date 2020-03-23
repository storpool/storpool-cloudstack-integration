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
package org.apache.cloudstack.storage.helper;

import javax.inject.Inject;

import org.apache.cloudstack.api.APICommand;
import org.apache.cloudstack.api.ApiCommandJobType;
import org.apache.cloudstack.api.BaseAsyncCmd;
import org.apache.cloudstack.api.ServerApiException;
import org.apache.cloudstack.api.command.user.template.DeleteTemplateCmd;
import org.apache.cloudstack.api.response.SuccessResponse;
import org.apache.cloudstack.engine.subsystem.api.storage.TemplateDataFactory;
import org.apache.cloudstack.engine.subsystem.api.storage.TemplateInfo;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil.SpApiResponse;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil.SpConnectionDesc;
import org.apache.log4j.Logger;

import com.cloud.utils.component.ComponentContext;

@APICommand(name = "deleteTemplate",
            responseObject = SuccessResponse.class,
            description = "Deletes a template from the system. All virtual machines using the deleted template will not be affected.",
            requestHasSensitiveInfo = false, responseHasSensitiveInfo = false)
public class StorPoolDeleteTemplateCmd extends BaseAsyncCmd {
    public static final Logger log = Logger.getLogger(StorPoolDeleteTemplateCmd.class.getName());
    private DeleteTemplateCmd deleteTemplate;
    private StorPoolReplaceCommandsHelper.StorPoolReplaceCommandsUtil replaceCommands = StorPoolReplaceCommandsHelper.getStorPoolReplaceCommandsUtil();
    @Inject
    private TemplateDataFactory templateDataFactory;

    public StorPoolDeleteTemplateCmd() {
        super();
            try {
                this.deleteTemplate = DeleteTemplateCmd.class.newInstance();
            } catch (InstantiationException | IllegalAccessException e) {
                log.error(e.getMessage());
            }
            this.deleteTemplate = ComponentContext.inject(this.deleteTemplate);
    }

    @Override
    public String getCommandName() {
        return this.deleteTemplate.getCommandName();
    }

    @Override
    public long getEntityOwnerId() {
        replaceCommands.ensureCmdHasRequiredValues(this.deleteTemplate, this);

        return this.deleteTemplate.getEntityOwnerId();
    }

    @Override
    public String getEventType() {
        return this.deleteTemplate.getEventType();
    }

    @Override
    public String getEventDescription() {
        replaceCommands.ensureCmdHasRequiredValues(this.deleteTemplate, this);

        return this.deleteTemplate.getEventDescription();
    }

    @Override
    public ApiCommandJobType getInstanceType() {
        return this.deleteTemplate.getInstanceType();
    }


    @Override
    public void execute() {
        replaceCommands.ensureCmdHasRequiredValues(this.deleteTemplate, this);
        TemplateInfo obj =  templateDataFactory.getReadyTemplateOnImageStore(this.deleteTemplate.getId(), this.deleteTemplate.getZoneId());
        try {
            this.deleteTemplate.execute();
            log.info("DeleteTemplateCmd.execute was successfuly executed");
            this.setResponseObject(this.deleteTemplate.getResponseObject());
            if (obj != null ) {
                SpConnectionDesc conn = new SpConnectionDesc(obj.getDataStore().getUuid());
                if (StorpoolUtil.snapshotExists(obj.getUuid(), conn)) {
                    SpApiResponse resp = StorpoolUtil.snapshotDelete(obj.getUuid(), conn);
                    StorpoolUtil.spLog("Delete template from StorPool. Snapshot name=%s, result=%s", obj.getUuid(), resp.getError());
                }
            }
        }catch (ServerApiException e) {
            throw e;
        }
    }
}
