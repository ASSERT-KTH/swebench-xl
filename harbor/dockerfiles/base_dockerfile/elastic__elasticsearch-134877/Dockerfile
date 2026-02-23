# Base image for Elasticsearch benchmark instances
# Contains: JDK 21, Gradle, system deps, elasticsearch repo (single-branch clone)

FROM eclipse-temurin:21-jdk-jammy

ENV DEBIAN_FRONTEND=noninteractive

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    python3 \
    python3-pip \
    curl \
    wget \
    unzip \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Clone elasticsearch with --single-branch to limit initial history exposure
RUN mkdir /app && \
    git clone -o origin --single-branch https://github.com/elastic/elasticsearch.git /app

WORKDIR /app

ENTRYPOINT ["/bin/bash"]
