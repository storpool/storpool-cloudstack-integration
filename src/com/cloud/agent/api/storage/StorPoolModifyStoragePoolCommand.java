package com.cloud.agent.api.storage;

import com.cloud.agent.api.ModifyStoragePoolCommand;
import com.cloud.storage.StoragePool;

public class StorPoolModifyStoragePoolCommand extends ModifyStoragePoolCommand {
    private String volName;

    public StorPoolModifyStoragePoolCommand(boolean add, StoragePool pool, String volumeName) {
        super(add, pool);
        this.volName = volumeName;
    }

    public String getVolume() {
        return volName;
    }
}
