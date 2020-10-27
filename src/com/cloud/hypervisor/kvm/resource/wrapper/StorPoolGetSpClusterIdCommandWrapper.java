package com.cloud.hypervisor.kvm.resource.wrapper;

import org.apache.log4j.Logger;

import com.cloud.agent.api.Answer;
import com.cloud.agent.api.storage.StorPoolGetSpClusterIdCommand;
import com.cloud.hypervisor.kvm.resource.LibvirtComputingResource;
import com.cloud.hypervisor.kvm.storage.StorpoolStorageAdaptor;
import com.cloud.resource.CommandWrapper;
import com.cloud.resource.ResourceWrapper;
import com.cloud.utils.script.OutputInterpreter;
import com.cloud.utils.script.Script;

@ResourceWrapper(handles = StorPoolGetSpClusterIdCommand.class)
public class StorPoolGetSpClusterIdCommandWrapper extends CommandWrapper<StorPoolGetSpClusterIdCommand, Answer, LibvirtComputingResource>{

    private static final Logger log = Logger.getLogger(StorPoolGetSpClusterIdCommandWrapper.class);

    @Override
    public Answer execute(StorPoolGetSpClusterIdCommand command, LibvirtComputingResource serverResource) {
        String clusterId = getSpClusterId();
        if (clusterId != null) {
            return new Answer(command, true, clusterId);
        }
        return new Answer(command, false, "");
    }

    private String getSpClusterId() {
        Script sc = new Script("storpool_confget", 0, log);
        OutputInterpreter.AllLinesParser parser = new OutputInterpreter.AllLinesParser();

        String SP_CLUSTER_ID = null;
        final String err = sc.execute(parser);
        if (err != null) {
            final String errMsg = String.format("Could not execute storpool_confget. Error: %s", err);
            log.warn(errMsg);
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
}
