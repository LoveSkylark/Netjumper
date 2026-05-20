#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing system dependencies..."
sudo apt update
sudo apt install -y $(cat "${SCRIPT_DIR}/requirements.apt")

if type -P docker >/dev/null 2>&1; then
	CONTAINER_CMD="docker"
else
	echo "Error: docker is not installed."
	exit 1
fi

if ! $CONTAINER_CMD compose version >/dev/null 2>&1; then
	echo "Error: docker compose is not available."
	exit 1
fi

echo "Using container runtime: ${CONTAINER_CMD} compose"

if $CONTAINER_CMD ps -a --format '{{.Names}}' | grep -qx "python"; then
	COMPOSE_PROJECT="$($CONTAINER_CMD inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' python 2>/dev/null || true)"
	if [ -z "${COMPOSE_PROJECT}" ]; then
		echo "Removing legacy standalone container: python"
		$CONTAINER_CMD rm -f python >/dev/null || true
	fi
fi

echo "Building and starting container with Compose..."
cd "${SCRIPT_DIR}"
$CONTAINER_CMD compose down --remove-orphans >/dev/null 2>&1 || true
$CONTAINER_CMD compose up -d --build --force-recreate

echo "Container python is ready."

echo "Installing profile wrappers to /etc/profile.d"
sudo install -m 0644 "${SCRIPT_DIR}/profile.d/saci.sh" /etc/profile.d/saci.sh
sudo install -m 0644 "${SCRIPT_DIR}/profile.d/slnms.sh" /etc/profile.d/slnms.sh
sudo install -m 0644 "${SCRIPT_DIR}/profile.d/network_completion.sh" /etc/profile.d/network_completion.sh

if [ ! -f "${SCRIPT_DIR}/config.yaml" ]; then
	cp "${SCRIPT_DIR}/config.yaml.example" "${SCRIPT_DIR}/config.yaml"
	echo "Created ${SCRIPT_DIR}/config.yaml from config.yaml.example"
fi

echo "Installation complete. Open a new shell (or source /etc/profile) to use commands."

