#TODO: more information has to be included. Works for now only on 10.2.1.186
Prerequisites:
#TODO: need a script for this
https://cwiki.apache.org/confluence/display/CLOUDSTACK/Marvin+-+Testing+with+Python

setup StorPool primary storage:
create templates - "cloud-test-dev-1" and "cloud-test-dev-2" on StorPool
create two StorPool's primary storages on CloudStack with names "cloud-test-dev-1" and "cloud-test-dev-2" 

 
For the tests is used "system" VM template

command to run tests
nosetests --with-marvin  --marvin-config=/path/to/env.cfg /path/to/test --hypervisor=kvm



