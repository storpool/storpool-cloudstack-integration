package com.cloud.agent.api.to;

import com.cloud.vm.VirtualMachine;

public class StorPoolVirtualMachineTO extends VirtualMachineTO{
    private VirtualMachine.State state;

    public VirtualMachine.State getState() {
        return state;
    }

    public void setState(VirtualMachine.State state) {
        this.state = state;
    }
}
