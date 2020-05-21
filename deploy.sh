#!/bin/bash


read -ra args <<<"$*"

if [[ ${args[0]} == hv ]]; then
	for target in "${args[@]}"; do
		if [[ $target == ${args[0]} ]]; then
			continue
		fi
		scp target/cloud-plugin-storage-volume-storpool-4.*.jar "root@${target}:/usr/share/cloudstack-agent/lib/"
	done
else
	echo "No such option ${args[0]} implemented, supported: hv [target1 target2 ... targetN]"
fi
