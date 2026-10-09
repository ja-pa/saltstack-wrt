FROM ubuntu:24.04
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash build-essential ca-certificates curl file gawk git jq libncurses-dev \
    libssl-dev zlib1g-dev rsync unzip wget zstd cmake ninja-build pkg-config \
    python3 python3-venv qemu-user-static proot xz-utils bzip2 patch \
    && rm -rf /var/lib/apt/lists/*
USER ubuntu
WORKDIR /sdk
