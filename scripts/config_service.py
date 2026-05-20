import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml


# Inside container: mounted at /workspace/config.yaml
# Outside container: at repo root/config.yaml
_WORKSPACE_CONFIG = Path('/workspace/config.yaml')
_LOCAL_CONFIG = Path(__file__).resolve().parent.parent / 'config.yaml'
CONFIG_FILE = _WORKSPACE_CONFIG if _WORKSPACE_CONFIG.exists() else _LOCAL_CONFIG
HOSTS_FILE = '/host_etc_hosts'


@dataclass
class Settings:
    # LibreNMS
    url: str
    token: str
    # Paths
    log_dir: str = 'var/log/'
    info_dir: str = 'var/info/'
    config_dir: str = 'var/configs/'
    hosts_dir: str = HOSTS_FILE
    # NetBox
    nb_url: str = ''
    nb_token: str = ''
    nb_regions: list = field(default_factory=list)
    nb_site_mapping: dict = field(default_factory=dict)


@dataclass
class APICSettings:
    url: str
    verify_ssl: bool = False
    username: str = ''
    password: str = ''



def _find_librenms_servers(cfg: dict) -> dict:
    """Return a dict of all librenmsN servers and legacy 'librenms' in config."""
    servers = {k: v for k, v in cfg.items() if k.startswith('librenms') and k[8:].isdigit() and isinstance(v, dict)}
    # Also include legacy 'librenms' if present and is a dict
    if 'librenms' in cfg and isinstance(cfg['librenms'], dict):
        servers['librenms'] = cfg['librenms']
    return servers

def load_settings(path: Path = CONFIG_FILE, force_server: str = None) -> Settings:
    if not path.exists():
        raise SystemExit(f"Config file not found: {path}\nCopy config.yaml.example to config.yaml and fill in your values.")

    with open(path) as f:
        cfg = yaml.safe_load(f)

    # Multi-server support
    servers = _find_librenms_servers(cfg)
    active_key = force_server or cfg.get('librenms_active')
    if not servers:
        # Fallback: support legacy single-server config
        lnms = cfg.get('librenms', {})
        if not lnms:
            raise SystemExit("No LibreNMS servers found in config. Add at least 'librenms1' or 'librenms'.")
        url = lnms.get('url')
        token = lnms.get('token')
        if not url or not token:
            raise SystemExit("Missing required config value(s): librenms.url, librenms.token")
    else:
        if not active_key or active_key not in servers:
            raise SystemExit(f"librenms_active not set or invalid. Available: {', '.join(servers.keys())}")
        lnms = servers[active_key]
        url = lnms.get('url')
        token = lnms.get('token')
        if not url or not token:
            raise SystemExit(f"Missing required config value(s) for {active_key}: url, token")

    nb   = cfg.get('netbox', {})
    paths = cfg.get('paths', {})

    return Settings(
        url=url.rstrip('/'),
        token=token,
        log_dir=paths.get('log_dir', 'var/log/'),
        info_dir=paths.get('info_dir', 'var/info/'),
        config_dir=paths.get('config_dir', 'var/configs/'),
        hosts_dir=HOSTS_FILE,
        nb_url=nb.get('url', '').rstrip('/'),
        nb_token=nb.get('token', ''),
        nb_regions=nb.get('regions', []),
        nb_site_mapping=nb.get('site_mapping', {}),
    )

def list_librenms_servers(path: Path | None = None) -> dict:
    """Return dict of all LibreNMS servers in config."""
    path = path or CONFIG_FILE
    if not path.exists():
        raise SystemExit(f"Config file not found: {path}\nCopy config.yaml.example to config.yaml and fill in your values.")
    with open(path) as f:
        cfg = yaml.safe_load(f)
    return _find_librenms_servers(cfg), cfg.get('librenms_active')

def set_librenms_active(server_key: str, path: Path | None = None):
    """Set the active LibreNMS server in config file."""
    path = path or CONFIG_FILE
    if not path.exists():
        raise SystemExit(f"Config file not found: {path}\nCopy config.yaml.example to config.yaml and fill in your values.")
    with open(path) as f:
        cfg = yaml.safe_load(f)
    servers = _find_librenms_servers(cfg)
    if server_key not in servers:
        raise SystemExit(f"Server '{server_key}' not found in config. Available: {', '.join(servers.keys())}")
    cfg['librenms_active'] = server_key
    with open(path, 'w') as f:
        yaml.safe_dump(cfg, f, default_flow_style=False)


def load_apic_settings(path: Path = CONFIG_FILE) -> APICSettings:
    if not path.exists():
        raise SystemExit(f"Config file not found: {path}\nCopy config.yaml.example to config.yaml and fill in your values.")

    with open(path) as f:
        cfg = yaml.safe_load(f)

    apic = cfg.get('apic', {})
    verify_ssl_raw = apic.get('verify_ssl', False)
    verify_ssl = verify_ssl_raw if isinstance(verify_ssl_raw, bool) else str(verify_ssl_raw).strip().lower() in ('true', 'yes', '1')
    url = str(apic.get('url', '')).strip().rstrip('/')

    return APICSettings(
        url=url,
        verify_ssl=verify_ssl,
        username=str(apic.get('username', '')).strip(),
        password=str(apic.get('password', '')).strip(),
    )
