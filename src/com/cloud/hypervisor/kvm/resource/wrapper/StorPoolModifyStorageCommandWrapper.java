package com.cloud.hypervisor.kvm.resource.wrapper;

import java.util.HashMap;
import java.util.Map;
import java.util.Map.Entry;
import java.util.Set;

import org.apache.log4j.Logger;

import com.cloud.agent.api.Answer;
import com.cloud.agent.api.storage.StorPoolModifyStoragePoolAnswer;
import com.cloud.agent.api.storage.StorPoolModifyStoragePoolCommand;
import com.cloud.hypervisor.kvm.resource.LibvirtComputingResource;
import com.cloud.hypervisor.kvm.storage.KVMStoragePool;
import com.cloud.hypervisor.kvm.storage.KVMStoragePoolManager;
import com.cloud.hypervisor.kvm.storage.StorpoolStorageAdaptor;
import com.cloud.resource.CommandWrapper;
import com.cloud.resource.ResourceWrapper;
import com.cloud.storage.template.TemplateProp;
import com.cloud.utils.script.OutputInterpreter;
import com.cloud.utils.script.Script;
import com.google.gson.JsonElement;
import com.google.gson.JsonParser;

@ResourceWrapper(handles =  StorPoolModifyStoragePoolCommand.class)
public final class StorPoolModifyStorageCommandWrapper extends CommandWrapper<StorPoolModifyStoragePoolCommand, Answer, LibvirtComputingResource> {
    private static final Logger log = Logger.getLogger(StorPoolModifyStorageCommandWrapper.class);

    @Override
    public Answer execute(final StorPoolModifyStoragePoolCommand command, final LibvirtComputingResource libvirtComputingResource) {
        String clusterId = getSpClusterId();
        if (clusterId == null) {
            return new Answer(command, false, "spNotFound");
        }
        try {
            String volume = attachOrDetachVolume("attach", "volume", command.getVolume());
            if (volume != null) {
                return new Answer(command, false, volume);
            } else {
                final KVMStoragePoolManager storagePoolMgr = libvirtComputingResource.getStoragePoolMgr();
                final KVMStoragePool storagepool =
                        storagePoolMgr.createStoragePool(command.getPool().getUuid(), command.getPool().getHost(), command.getPool().getPort(), command.getPool().getPath(), command.getPool()
                                .getUserInfo(), command.getPool().getType());
                if (storagepool == null) {
                    return new Answer(command, false, " Failed to create storage pool");
                }

                final Map<String, TemplateProp> tInfo = new HashMap<String, TemplateProp>();
                final StorPoolModifyStoragePoolAnswer answer = new StorPoolModifyStoragePoolAnswer(command, storagepool.getCapacity(), storagepool.getAvailable(), tInfo, clusterId);

                return answer;
            }
        } catch (Exception e) {
            return new Answer(command, false, e.getMessage());
        }
    }

    private String getSpClusterId() {
        Script sc = new Script("storpool_confget", 0, log);
        OutputInterpreter.AllLinesParser parser = new OutputInterpreter.AllLinesParser();

        String SP_CLUSTER_ID = null;
        final String err = sc.execute(parser);
        if (err != null) {
            StorpoolStorageAdaptor.SP_LOG("Could not execute storpool_confget. Error: %s", err);
            return SP_CLUSTER_ID;
        }

        for (String line: parser.getLines().split("\n")) {
            String[] toks = line.split("=");
            if( toks.length != 2 ) {
                continue;
            }
            if (toks[0].equals("SP_CLUSTER_ID")) {
                SP_CLUSTER_ID = toks[1];
                return SP_CLUSTER_ID;
            }
        }
        return SP_CLUSTER_ID;
    }

    public String attachOrDetachVolume(String command, String type, String volumeUuid) {
        final String name = StorpoolStorageAdaptor.getVolumeNameFromPath(volumeUuid, true);
        if (name == null) {
            return null;
        }

        String err = null;
        Script sc = new Script("storpool", 300000, log);
        sc.add("-M");
        sc.add("-j");
        sc.add(command);
        sc.add(type, name);
        sc.add("here");
        sc.add("onRemoteAttached");
        sc.add("export");

        OutputInterpreter.AllLinesParser parser = new OutputInterpreter.AllLinesParser();

        String res = sc.execute(parser);

        if (res != null) {
            if (!res.equals(Script.ERR_TIMEOUT)) {
                try {
                    Set<Entry<String, JsonElement>> obj2 = new JsonParser().parse(res).getAsJsonObject().entrySet();
                    for (Entry<String, JsonElement> entry : obj2) {
                        if (entry.getKey().equals("error")) {
                            res = entry.getValue().getAsJsonObject().get("name").getAsString();
                        }
                    }
                } catch (Exception e) {
                }
            }

            err = String.format("Unable to %s volume %s. Error: %s", command, name, res);
        }

        if (err != null) {
            log.warn(err);
        }
        return res;
    }
}
