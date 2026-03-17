"""NetBox API client wrapper using pynetbox."""

import urllib3
import pynetbox

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class NetboxClient:
    def __init__(self, url: str, token: str):
        self._nb = pynetbox.api(url=url, token=token)
        self._nb.http_session.verify = False

    # ------------------------------------------------------------------
    # Endpoint properties (avoids leaking _nb into callers)
    # ------------------------------------------------------------------

    @property
    def regions(self):
        return self._nb.dcim.regions

    @property
    def sites(self):
        return self._nb.dcim.sites

    @property
    def device_roles(self):
        return self._nb.dcim.device_roles

    # ------------------------------------------------------------------
    # Priming
    # ------------------------------------------------------------------

    def diff_objects(self, endpoint, names: list[str]) -> list[str]:
        """Return names that do not yet exist in NetBox."""
        return [n for n in names if not endpoint.get(slug=n.lower().replace(' ', '-'))]

    def create_objects(self, endpoint, names: list[str]) -> None:
        """Create objects by name. Caller should pass only names that don't exist yet."""
        for name in names:
            endpoint.create(name=name, slug=name.lower().replace(' ', '-'))
            print(f"  CREATE  {name}")

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def get_device_types(self) -> dict:
        """Return {part_number: id}"""
        return {dt.part_number: dt.id for dt in self._nb.dcim.device_types.all() if dt.part_number}

    def get_roles(self) -> dict:
        """Return {display_name: id}"""
        return {role.display: role.id for role in self._nb.dcim.device_roles.all()}

    def get_sites(self) -> dict:
        """Return {display_name: id}"""
        return {site.display: site.id for site in self._nb.dcim.sites.all()}

    # ------------------------------------------------------------------
    # Devices
    # ------------------------------------------------------------------

    def get_all_devices(self):
        return self._nb.dcim.devices.all()

    def get_device(self, name: str):
        return self._nb.dcim.devices.get(name=name)

    def create_device(self, name: str, device_type_id: int, role_id: int, site_id: int):
        return self._nb.dcim.devices.create(
            name=name,
            device_type=device_type_id,
            role=role_id,
            site=site_id,
        )

    # ------------------------------------------------------------------
    # Interfaces & IPs
    # ------------------------------------------------------------------

    def get_interface(self, device_id: int, iface_name: str):
        return self._nb.dcim.interfaces.get(device_id=device_id, name=iface_name)

    def create_interface(self, device_id: int, iface_name: str):
        return self._nb.dcim.interfaces.create(
            device=device_id,
            name=iface_name,
            type='virtual',
        )

    def get_ip(self, address: str):
        return self._nb.ipam.ip_addresses.get(address=address)

    def create_ip(self, address: str, interface_id: int):
        return self._nb.ipam.ip_addresses.create(
            address=address,
            assigned_object_type='dcim.interface',
            assigned_object_id=interface_id,
        )

    def ensure_mgmt_ip(self, device, ip_with_prefix: str) -> None:
        """Ensure device has a Management interface, the given IP, and it is set as primary_ip4."""
        try:
            current = device.primary_ip4.address if device.primary_ip4 else None
        except AttributeError:
            current = None
        if current == ip_with_prefix:
            return
        iface = self.get_interface(device.id, 'Management') or self.create_interface(device.id, 'Management')
        ip = self.get_ip(ip_with_prefix) or self.create_ip(ip_with_prefix, iface.id)
        device.primary_ip4 = ip.id
        device.save()
