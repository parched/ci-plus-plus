FROM ubuntu:20.04

# Common packaging tools
RUN apt-get update && apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  git \
  unzip \
  xz-utils \
  && rm -rf /var/lib/apt/lists/*

# Make the default match non-root users
ENV TAR_OPTIONS --no-same-owner

# Python
ARG PYTHON_VERSION=3.10
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  software-properties-common \
  && add-apt-repository -y ppa:deadsnakes/ppa \
  && apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  python${PYTHON_VERSION}-full \
  python-is-python3 \
  && rm -rf /var/lib/apt/lists/*
  
# Poetry
ENV PEOTRY_VERSION=1.2.0b1
ENV POETRY_HOME=/opt/poetry
ENV PATH=${PATH}:${POETRY_HOME}/bin
RUN curl -sSL https://install.python-poetry.org | python3 - \
  && poetry completions bash > /etc/bash_completion.d/poetry.bash-completion
