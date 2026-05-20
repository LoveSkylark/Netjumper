#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if type -P podman >/dev/null 2>&1; then
	CONTAINER_CMD="podman"
elif type -P docker >/dev/null 2>&1; then
	CONTAINER_CMD="docker"
else
	echo "Error: Neither podman nor docker is installed."
	exit 1
fi

echo "Using container runtime: ${CONTAINER_CMD}"
bash "${REPO_ROOT}/build.sh"

echo "Installing profile wrappers to /etc/profile.d"
sudo install -m 0644 "${REPO_ROOT}/profile.d/saci.sh" /etc/profile.d/saci.sh
sudo install -m 0644 "${REPO_ROOT}/profile.d/slnms.sh" /etc/profile.d/slnms.sh
sudo install -m 0644 "${REPO_ROOT}/profile.d/network_completion.sh" /etc/profile.d/network_completion.sh

if [ ! -f "${REPO_ROOT}/config.yaml" ]; then
	cp "${REPO_ROOT}/config.yaml.example" "${REPO_ROOT}/config.yaml"
	echo "Created ${REPO_ROOT}/config.yaml from config.yaml.example"
fi

echo "Installation complete. Open a new shell (or source /etc/profile) to use commands."
