import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class APIError(Exception):
    pass


class Client:
    """LibreNMS API client covering endpoints used by lnms.py and update_hosts.py."""

    def __init__(self, url: str, token: str, timeout: int = 10):
        self._url = url.rstrip('/')
        self._timeout = timeout
        self._cache: dict = {}
        self._session = requests.Session()
        self._session.verify = False
        self._session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Auth-Token': token,
        })

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, cache: bool = True) -> dict | list:
        if cache and path in self._cache:
            return self._cache[path]
        resp = self._session.get(self._url + path, timeout=self._timeout)
        if not resp.ok:
            raise APIError(f"HTTP {resp.status_code}: {resp.text}")
        data = resp.json()
        if isinstance(data, dict) and data.get('status') == 'error':
            raise APIError(f"API error: {data.get('message', resp.text)}")
        if cache:
            self._cache[path] = data
        return data

    def _post(self, path: str, payload: dict) -> dict:
        resp = self._session.post(self._url + path, json=payload, timeout=self._timeout)
        if not resp.ok:
            raise APIError(f"HTTP {resp.status_code}: {resp.text}")
        return resp.json()

    def _patch(self, path: str, payload: dict) -> dict:
        resp = self._session.patch(self._url + path, json=payload, timeout=self._timeout)
        if not resp.ok:
            raise APIError(f"HTTP {resp.status_code}: {resp.text}")
        return resp.json()

    # ------------------------------------------------------------------
    # API check
    # ------------------------------------------------------------------

    def ping(self) -> dict:
        return self._get('/api/v0/system', cache=False)

    # ------------------------------------------------------------------
    # Billing
    # ------------------------------------------------------------------

    def list_bills(self) -> list[dict]:
        return self._get('/api/v0/bills')['bills']

    def get_bill(self, bill_id: int) -> dict:
        return self._get(f'/api/v0/bills/{bill_id}')['bills'][0]

    def get_bill_history(self, bill_id: int) -> list[dict]:
        return self._get(f'/api/v0/bills/{bill_id}/history')['bill_history']

    # ------------------------------------------------------------------
    # Devices
    # ------------------------------------------------------------------

    def list_devices(self) -> list[dict]:
        return self._get('/api/v0/devices')['devices']

    def get_device(self, hostname: str) -> dict:
        return self._get(f'/api/v0/devices/{hostname}')['devices'][0]

    def add_device(self, payload: dict) -> list[dict]:
        return self._post('/api/v0/devices', payload)['devices']

    def update_device_field(self, hostname: str, payload: dict) -> dict:
        return self._patch(f'/api/v0/devices/{hostname}', payload)

    # ------------------------------------------------------------------
    # Ports & Links
    # ------------------------------------------------------------------

    def get_all_ports(self) -> list[dict]:
        return self._get('/api/v0/ports')['ports']

    def list_links(self) -> list[dict]:
        return self._get('/api/v0/resources/links')['links']

    # ------------------------------------------------------------------
    # Oxidized
    # ------------------------------------------------------------------

    def list_oxidized(self) -> list[dict]:
        """Return the list of devices tracked by Oxidized."""
        resp = self._session.get(self._url + '/api/v0/oxidized/', timeout=self._timeout)
        if not resp.ok:
            return []
        data = resp.json()
        return data if isinstance(data, list) else []

    def get_oxidized_config(self, hostname: str) -> str | None:
        """Return the stored Oxidized config for *hostname*, or None on any error."""
        try:
            resp = self._session.get(self._url + f'/api/v0/oxidized/config/{hostname}', timeout=self._timeout)
            if not resp.ok:
                return None
            data = resp.json()
            if not isinstance(data, dict):
                return None
            config = data.get('config')
            if isinstance(config, list):
                config = '\n'.join(config)
            return config
        except Exception:
            return None
