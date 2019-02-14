FROM centos:7

ADD docker.entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /src
VOLUME ["/src"]

RUN yum -y update \
&& yum -y install \
   --setopt=tsflags=nodocs \
   --disableplugin=fastestmirror \
   epel-release \
&& yum -y install git java-1.8.0-openjdk java-1.8.0-openjdk-devel \
   ant gcc python-devel bzip2 maven \
&& yum clean all --enablerepo=* --verbose \
&& rm -vrf /etc/ld.so.cache \
&& mvn --version && git --version \
&& git clone --branch 4.11.2.0 https://github.com/apache/cloudstack /cloudstack.git \
&& ln -sf /cloudstack.git /git \
&& cd /git \
&& mvn -DskipTests -Pdeveloper clean install

ENTRYPOINT ["/entrypoint.sh"]
