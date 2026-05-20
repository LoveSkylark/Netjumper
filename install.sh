#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="python"
CONTAINER_NAME="python"

echo "Installing system dependencies..."
sudo apt update
sudo apt install -y $(cat "${SCRIPT_DIR}/requirements.apt")

if type -P podman >/dev/null 2>&1; then
	CONTAINER_CMD="podman"
elif type -P docker >/dev/null 2>&1; then
	CONTAINER_CMD="docker"
else
	echo "Error: Neither podman nor docker is installed."
	exit 1
fi

echo "Using container runtime: ${CONTAINER_CMD}"

echo "Building and starting container..."
$CONTAINER_CMD build --no-cache -t "${IMAGE_NAME}" "${SCRIPT_DIR}"

if $CONTAINER_CMD ps -a --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
	$CONTAINER_CMD rm -f "${CONTAINER_NAME}" >/dev/null
fi

$CONTAINER_CMD run -itd \
	--name "${CONTAINER_NAME}" \
	-v "${SCRIPT_DIR}/scripts:/scripts" \
	-v "${SCRIPT_DIR}:/workspace" \
	-v "${HOME}/.aci_token:/root/.aci_token" \
	"${IMAGE_NAME}" >/dev/null

echo "Container ${CONTAINER_NAME} is ready."

echo "Installing profile wrappers to /etc/profile.d"
sudo install -m 0644 "${SCRIPT_DIR}/profile.d/saci.sh" /etc/profile.d/saci.sh
sudo install -m 0644 "${SCRIPT_DIR}/profile.d/slnms.sh" /etc/profile.d/slnms.sh
sudo install -m 0644 "${SCRIPT_DIR}/profile.d/network_completion.sh" /etc/profile.d/network_completion.sh

if [ ! -f "${SCRIPT_DIR}/config.yaml" ]; then
	cp "${SCRIPT_DIR}/config.yaml.example" "${SCRIPT_DIR}/config.yaml"
	echo "Created ${SCRIPT_DIR}/config.yaml from config.yaml.example"
fi

echo "Installation complete. Open a new shell (or source /etc/profile) to use commands."

