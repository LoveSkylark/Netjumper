#!/bin/bash

# grant-docker-permissions.sh
# Grants docker permissions to a user (must be run with sudo)

if [ $# -ne 1 ]; then
    echo "Usage: sudo $0 <username>"
    echo "Example: sudo $0 admin-stefan"
    exit 1
fi

USERNAME="$1"

echo "Granting docker permissions to user: $USERNAME"
usermod -aG docker "$USERNAME"

echo "Docker permissions granted!"
echo ""
echo "For the changes to take effect, the user must either:"
echo "  1. Log out and log back in, OR"
echo "  2. Run: newgrp docker"
echo ""
echo "Then restart the container:"
echo "  docker restart python"
