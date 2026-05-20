saci() {
    if [ $# -eq 0 ]; then
        echo "No arguments provided. Use -h for help."
        return 1
    fi

    if [ -z "$CONTAINER_CMD" ]; then
        if type -P podman >/dev/null 2>&1; then
            export CONTAINER_CMD="podman"
        elif type -P docker >/dev/null 2>&1; then
            export CONTAINER_CMD="docker"
        else
            echo "Error: Neither podman nor docker is installed."
            return 1
        fi
    fi

    if ! $CONTAINER_CMD ps --format '{{.Names}}' | grep -q '^python$'; then
        $CONTAINER_CMD start "python" >/dev/null 2>&1
    fi

    $CONTAINER_CMD exec -it "python" python3 /scripts/saci.py "$@"
}
