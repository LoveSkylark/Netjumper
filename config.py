import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class Settings:
    url: str
    token: str
    log_dir: str = 'var/log/'
    info_dir: str = 'var/info/'
    config_dir: str = 'var/configs/'
    hosts_dir: str = '/etc/hosts'


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        url=os.environ['LibreNMS_URL'].rstrip('/'),
        token=os.environ['LibreNMS_APIToken'],
        log_dir=os.environ.get('log_dir', 'var/log/'),
        info_dir=os.environ.get('info_dir', 'var/info/'),
        config_dir=os.environ.get('config_dir', 'var/configs/'),
        hosts_dir=os.environ.get('hosts_dir', '/etc/hosts'),
    )
