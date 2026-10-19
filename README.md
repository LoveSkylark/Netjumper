
# Netjumper

Containerized jump-tool deployment for LibreNMS and ACI operations.

Netjumper runs tools in a Docker/Podman container (image and container name: `python`) so dependencies stay isolated from the host.

## Included Tools

- `slnms`: LibreNMS + NetBox CLI tooling
- `saci`: Cisco ACI operational CLI
- `network_completion.sh`: shell completion helper

## Repository Layout

- `install.sh`: deployment script (builds container + installs shell wrappers)
- `docker-compose.yml`: compose alternative using the same mounts
- `scripts/`: all Python scripts and modules (LibreNMS, ACI, and helpers)
- `config.yaml.example`: configuration template
- `requirements.apt`: system packages for host machine

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

Deploy the container and install all dependencies (system packages + shell wrappers) in one step:

```bash
bash install.sh
```

Then open a new shell (or source `/etc/profile`) to use `slnms` and `saci` commands.

## Usage

```bash
slnms inventory
slnms neighbors --tree -p
slnms firmware --tree
slnms nb diff
saci vlan 120
```

`slnms inventory` uses the device serial when available, otherwise it looks up
chassis serials in LibreNMS hardware inventory. Distinct chassis serials for
stacked devices are separated by semicolons. Fallback values are labeled
`(chassis)` in both terminal output and the CSV file; device serials are not
labeled. If neither source has a serial, the field remains blank.

### ACI Domain Cleanup

```bash
saci clean domain
```

Reports domains without an AAEP, followed by physical domain attachments on EPGs
with no static or dynamic path bindings. Attachments are grouped by tenant,
application profile, and EPG, including domains already assigned to an AAEP.

The EPG check uses configured/deployed path bindings, not cable or link state.
An EPG with any path binding is excluded; it does not identify an unused domain
on an otherwise connected EPG. VMM attachments are excluded from this check.
The command only reports findings and does not remove configuration.

## Tests

Run the SACI and LibreNMS unit tests from the repository root:

```bash
python3 -m unittest discover -s tests -v
```

The SACI suites cover client authentication and caching, cleanup reports, IP/subnet
lookups, command reports, VMM VLAN resolution, and CLI parsing/dispatch. They use
mocked APIC responses and temporary token files; no live fabric or credentials
are required. Following the domain tests, the shared test loader compiles SACI
definitions from the source AST to avoid HTTP dependencies and import-time log
files. This does not test module import side effects or real HTTP integration.

BD cleanup regressions cover same-name BDs in different tenants and explicit
cross-tenant target references.

Run only the LibreNMS suites:

```bash
python3 -m unittest discover -s tests -p 'test_slnms_*.py' -v
```

These cover the LibreNMS client, parsers, billing/inventory/neighbor/firmware
reports, Oxidized downloads, host synchronization, NetBox command workflows,
server selection, and CLI parsing/dispatch. API calls, DNS, hosts-file operations,
configuration changes, and NetBox dependencies are mocked; output files are
written only to temporary directories. The CLI and client definitions are loaded
from the source AST to avoid optional runtime dependencies. Real HTTP, NetBox
normalization/matching, and third-party hosts-file integration are not covered.

## slnms Command Coverage

- `billing`
- `inventory`
- `neighbors` (supports `--tree`)
- `download`
- `firmware` (supports `--tree`)
- `host update|compare`
- `nb load|prime|diff`
- `api`
