#!/bin/bash

# grant-permissions.sh
# Manage user permissions for Netjumper tools

if [ $# -lt 2 ]; then
    echo "Usage: sudo $0 <permission> <username>"
    echo ""
    echo "Available permissions:"
    echo "  docker <username>     - Grant docker access to user"
    echo ""
    echo "Examples:"
    echo "  sudo $0 docker admin-stefan"
    exit 1
fi

PERMISSION="$1"
USERNAME="$2"

case "$PERMISSION" in
    docker)
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
        ;;
    *)
        echo "Unknown permission: $PERMISSION"
        exit 1
        ;;
esac
