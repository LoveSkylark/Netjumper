import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml


CONFIG_FILE = Path(__file__).parent / 'config.yaml'


@dataclass
class Settings:
    # LibreNMS
    url: str
    token: str
    # Paths
    log_dir: str = 'var/log/'
    info_dir: str = 'var/info/'
    config_dir: str = 'var/configs/'
    hosts_dir: str = '/etc/hosts'
    # NetBox
    nb_url: str = ''
    nb_token: str = ''
    nb_regions: list = field(default_factory=list)
    nb_site_mapping: dict = field(default_factory=dict)


def load_settings(path: Path = CONFIG_FILE) -> Settings:
    if not path.exists():
        raise SystemExit(f"Config file not found: {path}\nCopy config.yaml.example to config.yaml and fill in your values.")

    with open(path) as f:
        cfg = yaml.safe_load(f)

    lnms = cfg.get('librenms', {})
    nb   = cfg.get('netbox', {})
    paths = cfg.get('paths', {})

    missing = [k for k, v in {'librenms.url': lnms.get('url'), 'librenms.token': lnms.get('token')}.items() if not v]
    if missing:
        raise SystemExit(f"Missing required config value(s): {', '.join(missing)}")

    return Settings(
        url=lnms['url'].rstrip('/'),
        token=lnms['token'],
        log_dir=paths.get('log_dir', 'var/log/'),
        info_dir=paths.get('info_dir', 'var/info/'),
        config_dir=paths.get('config_dir', 'var/configs/'),
        hosts_dir=paths.get('hosts_dir', '/etc/hosts'),
        nb_url=nb.get('url', '').rstrip('/'),
        nb_token=nb.get('token', ''),
        nb_regions=nb.get('regions', []),
        nb_site_mapping=nb.get('site_mapping', {}),
    )
