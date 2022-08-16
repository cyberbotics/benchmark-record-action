FROM cyberbotics/webots.cloud:R2022b-numpy

RUN apt-get update && \
    apt-get install -y \
        git \
        python3-yaml \
        python3-requests \
        python3-distutils \
        python3-requests

COPY benchmark_record_action /usr/lib/python3/dist-packages/benchmark_record_action
COPY controllers ${WEBOTS_HOME}/resources/projects/controllers
COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
