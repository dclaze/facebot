"""Explicit trusted-home-LAN transport; never wildcard or public cleartext."""
import ipaddress

PRIVATE_NETWORKS = tuple(ipaddress.ip_network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))


def validate_bind(host, cert=None, key=None, allow_private_lan=False):
    if bool(cert) != bool(key):
        raise ValueError('TLS requires both certificate and key')
    if host in ('127.0.0.1', '::1', 'localhost') or (cert and key):
        return
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise ValueError('Use an explicit private IPv4 address or TLS') from None
    if allow_private_lan and any(address in network for network in PRIVATE_NETWORKS):
        return
    raise ValueError('LAN listening requires TLS, or explicit --allow-private-lan on a trusted private IPv4 network')
