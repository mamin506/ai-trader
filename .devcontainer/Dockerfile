FROM ubuntu:24.04

# Avoid warnings by switching to noninteractive
ENV DEBIAN_FRONTEND=noninteractive

# Install essential packages and Python
RUN apt-get update && apt-get install -y \
    python3-full \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    curl \
    wget \
    ca-certificates \
    build-essential \
    sudo \
    bash-completion \
    tree \
    && rm -rf /var/lib/apt/lists/*

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# Configure the ubuntu user (already exists in base image) with passwordless sudo
RUN echo "ubuntu ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ubuntu \
    && chmod 0440 /etc/sudoers.d/ubuntu

# Set up Python symlinks for convenience
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1 \
    && update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

# Create virtual environment for ubuntu user
RUN python3 -m venv /home/ubuntu/.venv \
    && chown -R ubuntu:ubuntu /home/ubuntu/.venv

# Switch to ubuntu user
USER ubuntu

# Activate venv by default in bash
RUN echo 'source /home/ubuntu/.venv/bin/activate' >> /home/ubuntu/.bashrc

# Set environment variables to use venv by default
ENV VIRTUAL_ENV=/home/ubuntu/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Switch back to dialog for any ad-hoc use of apt-get
ENV DEBIAN_FRONTEND=dialog

