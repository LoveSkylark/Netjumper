#!/bin/bash

# grant-permissions.sh
# Grant docker permissions to a user for Netjumper

if [ $# -ne 1 ]; then
    echo "Usage: sudo $0 <username>"
    echo "Example: sudo $0 admin-stefan"
    exit 1
fi

USERNAME="$1"

echo "Granting permissions to user: $USERNAME"
usermod -aG docker "$USERNAME"

echo "Permissions granted!"
echo ""
echo "For the changes to take effect, the user must either:"
echo "  1. Log out and log back in, OR"
echo "  2. Run: newgrp docker"
echo ""
echo "Then restart the container:"
echo "  docker restart python"
