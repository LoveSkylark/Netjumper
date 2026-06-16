#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="python"
CONTAINER_NAME="python"

echo "WARNING: This script will:"
echo "  - Build the ${IMAGE_NAME} script-runner image"
echo "  - Start container ${CONTAINER_NAME} with mounted scripts and project files"

# Skip prompt if called from install.sh
if [ -z "${SKIP_BUILD_PROMPT:-}" ]; then
    read -p "Do you want to continue? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi
fi

# Check if we already detected the container runtime
if [ -z "${CONTAINER_CMD:-}" ]; then
    # First time - detect and cache the result
    if type -P podman >/dev/null 2>&1; then
        export CONTAINER_CMD="podman"
    elif type -P docker >/dev/null 2>&1; then
        export CONTAINER_CMD="docker"
    else
        echo "Error: Neither podman nor docker is installed."
        exit 1
    fi
fi

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
