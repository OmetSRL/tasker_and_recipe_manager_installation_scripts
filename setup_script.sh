#!/bin/bash

# Usage: ./je-deployment/setup_script.sh <dockerhub-username> <dockerhub-password>


# Exit on error
set -e

# initial checks
if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root." >&2
    exit 1
fi

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <username> <password>"
  exit 1
fi

# installing all the required packages
echo "=== Installing Docker ==="
if ! command -v docker &> /dev/null; then
    apt-get update
    apt-get install -y \
        ca-certificates \
        curl \
        gnupg \
        lsb-release

    # Create keyring directory if not exists
    mkdir -p /etc/apt/keyrings

    # Add Docker's official GPG key
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

    # Add the Docker APT repository for Debian
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io
fi

echo "=== Logging into Docker Hub ==="

DOCKER_USERNAME="$1"
DOCKER_PASSWORD="$2"

echo "$DOCKER_PASSWORD" | docker login --username "$DOCKER_USERNAME" --password-stdin

if [ $? -eq 0 ]; then
  echo "DockerHub login successful"
else
  echo "DockerHub login failed" >&2
  exit 1
fi

echo "=== Installing Python if necessary ==="
# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed."

    # Attempt to install Python 3 (Debian/Ubuntu)
    if [ -f /etc/debian_version ]; then
        echo "Installing Python 3 using apt..."
        apt update
        apt install -y python3
    else
        echo "Unsupported OS for auto-install. Please install Python 3 manually."
        exit 1
    fi
fi

echo "=== Creating virtual env and installing dependencies ==="

echo "Installing python3-venv and python3-pip if they are missing"

apt update
apt install -y python3-venv python3-pip

# i move inside the folder
cd je-deployment
# Create virtual environment if it doesn't exist, it includes dependencies of both scripts 
if [ ! -d ".venv" ]; then
    python3 -m venv ".venv"
fi
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

# launching the script that prepares all the config folders
python script1.py
echo "=== First Python script executed ==="

# launching the script that prepares the docker compose
python dockercompose_generator.py
echo "=== Second Python script executed ==="

# i move outside the folder again
cd ..

echo "Setup complete! Scripts executed correctly and logged in DockerHub - you can delete the installation folder now"
