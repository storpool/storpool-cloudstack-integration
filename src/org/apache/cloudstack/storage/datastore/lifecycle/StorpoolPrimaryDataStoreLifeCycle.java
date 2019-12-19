/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
package org.apache.cloudstack.storage.datastore.lifecycle;

import java.util.Map;
import javax.inject.Inject;
import org.apache.log4j.Logger;

import com.cloud.agent.api.StoragePoolInfo;
import com.cloud.hypervisor.Hypervisor.HypervisorType;
import com.cloud.storage.Storage.StoragePoolType;
import com.cloud.storage.ScopeType;
import com.cloud.storage.StoragePool;
import com.cloud.storage.StoragePoolAutomation;

import org.apache.cloudstack.engine.subsystem.api.storage.ClusterScope;
import org.apache.cloudstack.engine.subsystem.api.storage.DataStore;
import org.apache.cloudstack.engine.subsystem.api.storage.HostScope;
import org.apache.cloudstack.engine.subsystem.api.storage.PrimaryDataStoreLifeCycle;
import org.apache.cloudstack.engine.subsystem.api.storage.PrimaryDataStoreParameters;
import org.apache.cloudstack.engine.subsystem.api.storage.ZoneScope;
import org.apache.cloudstack.storage.volume.datastore.PrimaryDataStoreHelper;
import org.apache.cloudstack.storage.datastore.db.PrimaryDataStoreDao;
import org.apache.cloudstack.storage.datastore.db.StoragePoolVO;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil;
import org.apache.cloudstack.storage.datastore.util.StorpoolUtil.SpConnectionDesc;



public class StorpoolPrimaryDataStoreLifeCycle implements PrimaryDataStoreLifeCycle {
    private static final Logger log = Logger.getLogger(StorpoolPrimaryDataStoreLifeCycle.class);

    @Inject protected PrimaryDataStoreHelper dataStoreHelper;
    @Inject protected StoragePoolAutomation storagePoolAutmation;
    @Inject private PrimaryDataStoreDao _primaryDataStoreDao;

    @Override
    public DataStore initialize(Map<String, Object> dsInfos) {
        StorpoolUtil.spLog("initialize:");
        for (Map.Entry<String, Object> e: dsInfos.entrySet()) {
            StorpoolUtil.spLog("    %s=%s", e.getKey(), e.getValue());
        }
        StorpoolUtil.spLog("");

        log.debug("initialize");

        String name = (String)dsInfos.get("name");
        String providerName = (String)dsInfos.get("providerName");
        Long zoneId = (Long)dsInfos.get("zoneId");

        String url = (String)dsInfos.get("url");
        SpConnectionDesc conn = new SpConnectionDesc(url);
        if (conn.getHostPort() == null)
            throw new IllegalArgumentException("No SP_API_HTTP");

        if (conn.getAuthToken() == null)
            throw new IllegalArgumentException("No SP_AUTH_TOKEN");

        if (conn.getTemplateName() == null)
            throw new IllegalArgumentException("No SP_TEMPLATE");

        if (!StorpoolUtil.templateExists(conn)) {
            throw new IllegalArgumentException("No such storpool template " + conn.getTemplateName() + " or credentials are invalid");
        }

        for (StoragePoolVO sp : _primaryDataStoreDao.findPoolsByProvider("StorPool")) {
            SpConnectionDesc old = new SpConnectionDesc(sp.getUuid());
            if( old.getHostPort().equals(conn.getHostPort()) && old.getTemplateName().equals(conn.getTemplateName()) )
                throw new IllegalArgumentException("StorPool cluster and template already in use by pool " + sp.getName());
        }

        Long capacityBytes = (Long)dsInfos.get("capacityBytes");
        if (capacityBytes == null) {
            throw new IllegalArgumentException("Capcity bytes is required");
        }

        String tags = (String)dsInfos.get("tags");
        if (tags == null || tags.isEmpty()) {
            tags = name;
        }

        @SuppressWarnings("unchecked")
        Map<String, String> details = (Map<String, String>)dsInfos.get("details");


        PrimaryDataStoreParameters parameters = new PrimaryDataStoreParameters();
        parameters.setName(name);
        parameters.setUuid(url);
        parameters.setZoneId(zoneId);
        parameters.setProviderName(providerName);
        parameters.setType(StoragePoolType.SharedMountPoint);
        parameters.setHypervisorType(HypervisorType.KVM);
        parameters.setManaged(false);
        parameters.setHost("n/a");
        parameters.setPort(0);
        parameters.setPath(StorpoolUtil.SP_DEV_PATH);
        parameters.setUsedBytes(0);
        parameters.setCapacityBytes(capacityBytes);
        parameters.setTags(tags);
        parameters.setDetails(details);

        return dataStoreHelper.createPrimaryDataStore(parameters);
    }

    @Override
    public void updateStoragePool(StoragePool storagePool, Map<String, String> details) {
        StorpoolUtil.spLog("updateStoragePool:");
        for (Map.Entry<String, String> e: details.entrySet()) {
            StorpoolUtil.spLog("    %s=%s", e.getKey(), e.getValue());
        }
        StorpoolUtil.spLog("");

        log.debug("updateStoragePool");
        return;
    }
    @Override
    public boolean attachHost(DataStore store, HostScope scope, StoragePoolInfo existingInfo) {
        log.debug("attachHost");
        return true;
    }

    @Override
    public boolean attachCluster(DataStore store, ClusterScope scope) {
        log.debug("attachCluster");
        if (!scope.getScopeType().equals(ScopeType.ZONE)) {
            throw new UnsupportedOperationException("Only Zone-Wide scope is supported!");
        }
        return true;
    }

    @Override
    public boolean attachZone(DataStore dataStore, ZoneScope scope, HypervisorType hypervisorType) {
        log.debug("attachZone");

        if (hypervisorType != HypervisorType.KVM) {
            throw new UnsupportedOperationException("Only KVM hypervisors supported!");
        }

        dataStoreHelper.attachZone(dataStore, hypervisorType);
        return true;
    }

    @Override
    public boolean maintain(DataStore dataStore) {
        log.debug("maintain");

        storagePoolAutmation.maintain(dataStore);
        dataStoreHelper.maintain(dataStore);
        return true;
    }

    @Override
    public boolean cancelMaintain(DataStore store) {
        log.debug("cancelMaintain");

        dataStoreHelper.cancelMaintain(store);
        storagePoolAutmation.cancelMaintain(store);
        return true;
    }

    @Override
    public boolean deleteDataStore(DataStore store) {
        log.debug("deleteDataStore");
        return dataStoreHelper.deletePrimaryDataStore(store);
    }

    @Override
    public boolean migrateToObjectStore(DataStore store) {
        log.debug("migrateToObjectStore");
        return false;
    }

    @Override
    public void enableStoragePool(DataStore dataStore) {
        log.debug("enableStoragePool");
        dataStoreHelper.enable(dataStore);
    }

    @Override
    public void disableStoragePool(DataStore dataStore) {
        log.debug("disableStoragePool");
        dataStoreHelper.disable(dataStore);
    }
}
