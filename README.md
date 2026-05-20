
# Netjumper

Containerized jump-tool deployment for LibreNMS and ACI operations.

Netjumper runs tools in a Docker/Podman container (image and container name: `python`) so dependencies stay isolated from the host.

## Included Tools

- `slnms`: LibreNMS + NetBox CLI tooling
- `saci`: Cisco ACI operational CLI
- `network_completion.sh`: shell completion helper

## Repository Layout

- `build.sh`: build and run container
- `docker-compose.yml`: compose alternative using the same mounts
- `scripts/`: all Python scripts and modules (LibreNMS, ACI, and helpers)
- `config.yaml.example`: configuration template
- `install/setup.sh`: installs shell wrapper scripts to `/etc/profile.d`

## Container Runtime Model

- Runtime auto-detected: Podman first, then Docker
- Volume mounts:
	- `./scripts:/scripts`
	- `.:/workspace`
	- `~/.aci_token:/root/.aci_token` (token persistence)
- `PYTHONPATH` in container includes `/workspace:/scripts`

## Configuration

Copy and edit config:

```bash
cp config.yaml.example config.yaml
```

`config.yaml` now contains both LibreNMS/NetBox settings and APIC settings.

APIC credentials are optional:
- If `apic.username` and/or `apic.password` are missing, `saci` prompts interactively.

Minimal APIC example:

```yaml
apic:
	url: https://apic.example.com
	verify_ssl: false
	username: admin      # optional
	password: secret     # optional
```

## Install

1. Build and start the container:

```bash
bash build.sh
```

2. Install wrapper scripts:

```bash
sudo bash install/setup.sh
```

3. Open a new shell (or source `/etc/profile`).

## Usage

```bash
slnms inventory
slnms neighbors --tree -p
slnms firmware --tree
slnms nb diff
saci vlan 120
```

## slnms Command Coverage

- `billing`
- `inventory`
- `neighbors` (supports `--tree`)
- `download`
- `firmware` (supports `--tree`)
- `host update|compare`
- `nb load|prime|diff`
- `api`
