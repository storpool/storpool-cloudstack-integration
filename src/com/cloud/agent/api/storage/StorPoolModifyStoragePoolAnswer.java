package com.cloud.agent.api.storage;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import com.cloud.agent.api.Answer;
import com.cloud.agent.api.ModifyStoragePoolAnswer;
import com.cloud.agent.api.StoragePoolInfo;
import com.cloud.storage.template.TemplateProp;

public class StorPoolModifyStoragePoolAnswer extends Answer{
    private StoragePoolInfo poolInfo;
    private Map<String, TemplateProp> templateInfo;
    private String localDatastoreName;
    private String poolType;
    private List<ModifyStoragePoolAnswer> datastoreClusterChildren = new ArrayList<>();
    private String clusterId;

    public StorPoolModifyStoragePoolAnswer(StorPoolModifyStoragePoolCommand cmd, long capacityBytes, long availableBytes, Map<String, TemplateProp> tInfo, String clusterId) {
        super(cmd);
        result = true;
        poolInfo = new StoragePoolInfo(null, cmd.getPool().getHost(), cmd.getPool().getPath(), cmd.getLocalPath(), cmd.getPool().getType(), capacityBytes, availableBytes);
        templateInfo = tInfo;
        this.clusterId = clusterId;
    }

    public StorPoolModifyStoragePoolAnswer(String errMsg) {
        super(null, false, errMsg);
    }

    public void setPoolInfo(StoragePoolInfo poolInfo) {
        this.poolInfo = poolInfo;
    }

    public StoragePoolInfo getPoolInfo() {
        return poolInfo;
    }

    public void setTemplateInfo(Map<String, TemplateProp> templateInfo) {
        this.templateInfo = templateInfo;
    }

    public Map<String, TemplateProp> getTemplateInfo() {
        return templateInfo;
    }

    public void setLocalDatastoreName(String localDatastoreName) {
        this.localDatastoreName = localDatastoreName;
    }

    public String getLocalDatastoreName() {
        return localDatastoreName;
    }

    public String getPoolType() {
        return poolType;
    }

    public void setPoolType(String poolType) {
        this.poolType = poolType;
    }

    public List<ModifyStoragePoolAnswer> getDatastoreClusterChildren() {
        return datastoreClusterChildren;
    }

    public void setDatastoreClusterChildren(List<ModifyStoragePoolAnswer> datastoreClusterChildren) {
        this.datastoreClusterChildren = datastoreClusterChildren;
    }

    public String getClusterId() {
        return clusterId;
    }
}
