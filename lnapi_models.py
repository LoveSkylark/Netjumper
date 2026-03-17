"""
TypedDict models for the LibreNMS API.

Each class maps to a single object returned by the API.
Fields marked Optional may be null or absent depending on device/config.
"""

from typing import Optional
from typing_extensions import TypedDict


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------

class Device(TypedDict):
    device_id: int
    hostname: str
    sysName: str
    sysDescr: Optional[str]
    sysObjectID: Optional[str]
    sysContact: Optional[str]
    version: Optional[str]
    hardware: Optional[str]
    features: Optional[str]
    location_id: Optional[int]
    os: Optional[str]
    status: int                 # 1 = up, 0 = down
    status_reason: Optional[str]
    ignore: int
    disabled: int
    uptime: Optional[int]
    last_polled: Optional[str]
    last_discovered: Optional[str]
    last_ping: Optional[str]
    purpose: Optional[str]
    type: Optional[str]
    serial: Optional[str]
    icon: Optional[str]
    poller_group: int
    bgpLocalAs: Optional[int]
    lat: Optional[float]
    lng: Optional[float]
    notes: Optional[str]
    snmp_disable: int


class DeviceGroup(TypedDict):
    id: int
    name: str
    desc: Optional[str]
    type: str                   # 'static' | 'dynamic'


class Component(TypedDict):
    type: str
    label: str
    status: int
    disabled: int
    ignore: int
    error: str


# ---------------------------------------------------------------------------
# Ports & Links
# ---------------------------------------------------------------------------

class Port(TypedDict):
    port_id: int
    device_id: int
    port_index: Optional[int]
    ifName: str
    ifDescr: Optional[str]
    ifAlias: Optional[str]
    ifSpeed: Optional[int]
    ifHighSpeed: Optional[int]
    ifOperStatus: str           # 'up' | 'down' | 'testing' | ...
    ifAdminStatus: str
    ifType: Optional[str]
    ifMtu: Optional[int]
    ifPhysAddress: Optional[str]
    ifInOctets: Optional[int]
    ifOutOctets: Optional[int]
    ifInErrors: Optional[int]
    ifOutErrors: Optional[int]


class PortStack(TypedDict):
    device_id: int
    port_id_high: int
    port_id_low: int
    ifStackStatus: str


class PortGroup(TypedDict):
    id: int
    name: str
    desc: Optional[str]


class FDBEntry(TypedDict):
    ports_fdb_id: int
    port_id: int
    device_id: int
    mac_address: str
    vlan_id: int
    timestamp: str


class Link(TypedDict):
    id: int
    local_port_id: int
    local_device_id: int
    remote_port_id: Optional[int]
    remote_hostname: str
    remote_device_id: Optional[int]
    remote_port: Optional[str]
    type: Optional[str]
    active: int


# ---------------------------------------------------------------------------
# Billing
# ---------------------------------------------------------------------------

class Bill(TypedDict):
    bill_id: int
    bill_name: str
    bill_type: str              # 'quota' | 'cdr'
    bill_quota: Optional[float]
    rate_95th_in: float
    rate_95th_out: float
    rate_95th: float
    dir_95th: str
    total_data: float
    total_data_in: float
    total_data_out: float
    overuse: str                # '-' when within allowance, else bytes
    rate_avg: float
    bill_today: float
    bill_allowed: float


class BillHistory(TypedDict):
    bill_hist_id: int
    bill_id: int
    bill_dateto: str
    bill_datefrom: str
    bill_type: str
    traf_total: float
    traf_in: float
    traf_out: float
    rate_95th_in: float
    rate_95th_out: float
    rate_95th: float
    dir_95th: str
    bill_overuse: float
    last_calc: str


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

class Alert(TypedDict):
    id: int
    device_id: int
    rule_id: int
    state: int                  # 0=ok, 1=alert, 2=ack
    alerted: int
    open: int
    timestamp: str
    note: Optional[str]
    info: Optional[str]
    severity: str
    rule: Optional[str]
    hostname: Optional[str]
    sysName: Optional[str]


class AlertRule(TypedDict):
    id: int
    name: str
    rule: str
    severity: str               # 'critical' | 'warning' | 'ok'
    extra: Optional[str]
    disabled: int
    count: int
    delay: Optional[str]
    interval: Optional[str]
    mute: int
    notes: Optional[str]
    max_alerts: int
    query: Optional[str]


# ---------------------------------------------------------------------------
# Networking — ARP / IP / FDB
# ---------------------------------------------------------------------------

class ARPEntry(TypedDict):
    port_id: int
    mac_address: str
    ipv4_address: str
    context_name: Optional[str]


class IPAddress(TypedDict):
    ipv4_address_id: int
    ipv4_address: str
    ipv4_prefixlen: int
    ipv4_network_id: int
    port_id: int
    context_name: Optional[str]


class IPv6Address(TypedDict):
    ipv6_address_id: int
    ipv6_address: str
    ipv6_prefixlen: int
    ipv6_network_id: int
    port_id: int
    context_name: Optional[str]


class IPNetwork(TypedDict):
    ipv4_network_id: int
    ipv4_network: str


# ---------------------------------------------------------------------------
# Routing — BGP / OSPF / VRF / MPLS / IPsec
# ---------------------------------------------------------------------------

class BGPSession(TypedDict):
    bgpPeer_id: int
    device_id: int
    bgpPeerIdentifier: str
    bgpPeerRemoteAs: int
    bgpPeerState: str
    bgpPeerAdminStatus: str
    bgpPeerInUpdates: int
    bgpPeerOutUpdates: int
    bgpPeerInTotalMessages: int
    bgpPeerOutTotalMessages: int
    bgpPeerFsmEstablishedTime: int
    bgpPeerInPrefixes: int
    bgpLocalAs: int
    context_name: Optional[str]


class CBGPCounter(TypedDict):
    device_id: int
    bgpPeerIdentifier: str
    afi: str
    safi: str
    AcceptedPrefixes: int
    DeniedPrefixes: int
    PrefixAdminLimit: int
    AdvertisedPrefixes: int
    SuppressedPrefixes: int
    WithdrawnPrefixes: int
    context_name: Optional[str]


class OSPFNeighbor(TypedDict):
    ospf_nbr_id: int
    device_id: int
    ospfNbrIpAddr: str
    ospfNbrRtrId: str
    ospfNbrPriority: int
    ospfNbrState: str
    ospfNbrEvents: int
    context_name: Optional[str]


class OSPFPort(TypedDict):
    ospf_port_id: int
    device_id: int
    port_id: int
    ospfIfIpAddress: str
    ospfIfAreaId: str
    ospfIfType: str
    ospfIfAdminStat: str
    ospfIfState: str
    ospfIfHelloInterval: int
    ospfIfRtrDeadInterval: int
    context_name: Optional[str]


class VRF(TypedDict):
    vrf_id: int
    device_id: int
    mplsVpnVrfName: str
    mplsVpnVrfRouteDistinguisher: Optional[str]
    mplsVpnVrfDescription: Optional[str]
    bgpVpnId: Optional[int]
    vrf_oid: Optional[str]


class MPLSService(TypedDict):
    svc_id: int
    device_id: int
    svcType: str
    svcCustId: Optional[int]
    svcAdminStatus: str
    svcOperStatus: str
    svcDescription: Optional[str]
    svcMtu: Optional[int]
    svcNumSaps: int
    svcName: Optional[str]


class MPLSSAP(TypedDict):
    sap_id: int
    svc_id: int
    device_id: int
    sapType: str
    sapAdminStatus: str
    sapOperStatus: str
    sapDescription: Optional[str]
    ifName: Optional[str]
    sapEncapValue: Optional[str]


class IPSecTunnel(TypedDict):
    tunnel_id: int
    device_id: int
    peer_addr: str
    local_addr: str
    status: str
    tunnel_name: Optional[str]


# ---------------------------------------------------------------------------
# Services & Sensors
# ---------------------------------------------------------------------------

class Service(TypedDict):
    service_id: int
    device_id: int
    service_ip: Optional[str]
    service_type: str
    service_desc: Optional[str]
    service_param: Optional[str]
    service_ignore: int
    service_status: int
    service_message: Optional[str]
    service_disabled: int


class Sensor(TypedDict):
    sensor_id: int
    sensor_class: str
    device_id: int
    sensor_oid: str
    sensor_index: str
    sensor_type: str
    sensor_descr: str
    sensor_divisor: float
    sensor_multiplier: float
    sensor_current: Optional[float]
    sensor_limit: Optional[float]
    sensor_limit_low: Optional[float]
    sensor_alert: int
    lastupdate: str
    group: Optional[str]


# ---------------------------------------------------------------------------
# VLANs / Inventory / Location
# ---------------------------------------------------------------------------

class VLAN(TypedDict):
    vlan_id: int
    device_id: int
    vlan_vlan: int
    vlan_domain: Optional[int]
    vlan_name: Optional[str]
    vlan_type: Optional[str]
    vlan_mtu: Optional[int]


class Inventory(TypedDict):
    entPhysical_id: int
    device_id: int
    entPhysicalIndex: int
    entPhysicalDescr: Optional[str]
    entPhysicalClass: Optional[str]
    entPhysicalName: Optional[str]
    entPhysicalModelName: Optional[str]
    entPhysicalSerialNum: Optional[str]
    entPhysicalMfgName: Optional[str]
    entPhysicalHardwareRev: Optional[str]
    entPhysicalFirmwareRev: Optional[str]
    entPhysicalSoftwareRev: Optional[str]
    entPhysicalIsFRU: Optional[int]


class Location(TypedDict):
    id: int
    location: str
    lat: Optional[float]
    lng: Optional[float]
    timestamp: Optional[str]
    fixed_coordinates: int


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------

class EventLog(TypedDict):
    event_id: int
    device_id: int
    hostname: Optional[str]
    sysName: Optional[str]
    datetime: str
    message: str
    type: Optional[str]
    reference: Optional[str]
    username: Optional[str]
    severity: int


class SysLog(TypedDict):
    syslog_id: int
    device_id: int
    facility: str
    level: str
    tag: Optional[str]
    timestamp: str
    program: Optional[str]
    msg: str


class AlertLog(TypedDict):
    id: int
    rule_id: int
    device_id: int
    state: int
    timestamp: str
    details: Optional[str]


class AuthLog(TypedDict):
    id: int
    datetime: str
    user: str
    address: str
    action: str
    result: str


# ---------------------------------------------------------------------------
# Oxidized
# ---------------------------------------------------------------------------

class OxidizedDevice(TypedDict):
    hostname: str
    ip: Optional[str]
    group: Optional[str]
    model: Optional[str]
    status: Optional[str]
    time: Optional[str]


class OxidizedSearchResult(TypedDict):
    hostname: str
    ip: Optional[str]
    group: Optional[str]
    model: Optional[str]


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

class SystemInfo(TypedDict):
    hostname: str
    db_schema: str
    local_ver: str
    db_ver: str
    php_ver: str
    python_ver: str
    netsnmp_ver: str
    rrdtool_ver: str
    mysql_ver: str


# ---------------------------------------------------------------------------
# Poller
# ---------------------------------------------------------------------------

class PollerGroup(TypedDict):
    id: int
    group_name: str
    descr: Optional[str]
