# Docker container for compiling storpool-cloudstack-integration

## Helper scripts
### docker.build

Script to build a Docker image based on CentOS and built cloudstack from source.

### docker.compile

Script to compile storpool-cloudstack-integration located in the parent directory.

### docker.cleanup

Script to remove the Docker image. The script is intentionally left as non-executable.

## Workflow

./docker.build   # to build a docker image
./docker.compile # to compile the integration

On successful compilation the resulting JAR file should be located in ../target/ directory.
