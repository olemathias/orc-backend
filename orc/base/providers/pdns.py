import re
import ipaddress
# TODO Change to ipaddress
from netaddr import IPNetwork


def create_forward_instance(instance):
    fqdn = "{}.{}.".format(instance.name, instance.platform.dns_forward_provider_config['domain'])
    ipv4 = str(IPNetwork(instance.ipam_provider_state['ip_addresses'][0]['address']).ip)
    ipv6 = str(IPNetwork(instance.ipam_provider_state['ip_addresses'][1]['address']).ip)
    rrsets = []
    rrsets.append({
        "name": fqdn,
        "changetype": "replace",
        "type": "A",
        "records": [{
            "content": ipv4,
            "disabled": False,
        }],
        "ttl": 900
    })
    rrsets.append({
        "name": fqdn,
        "changetype": "replace",
        "type": "AAAA",
        "records": [{
            "content": ipv6,
            "disabled": False,
        }],
        "ttl": 900
    })

    print(instance.platform.dns_forward().set_records(
        instance.platform.dns_forward_provider_config['domain'] + ".", rrsets))
    instance.dns_forward_provider_state['rrsets'] = {}
    instance.dns_forward_provider_state['rrsets'][instance.platform.dns_forward_provider_config['domain'] + "."] = rrsets
    instance.save()

    instance.dns_forward_provider_state['status'] = "provisioned"
    return True


def create_reverse_instance(instance):
    fqdn = "{}.{}.".format(instance.name, instance.platform.dns_forward_provider_config['domain'])
    ipv4 = instance.ipam_provider_state['ip_addresses'][0]['address']
    ipv6 = instance.ipam_provider_state['ip_addresses'][1]['address']
    instance.dns_reverse_provider_state['rrsets'] = {}

    # Hack to support custom in-addr.arpa zones.
    # Example zone 64-127.182.80.185.in-addr.arpa (for a network smaller then /24)
    # Assumes that this will never be used on larger networks than /24
    if instance.network.dns_reverse_provider_config is not None and 'v4_rdns_zone' in instance.network.dns_reverse_provider_config:
        p = re.compile('(.*)\\.(.*)\\.(.*)\\.(.*)')
        m = p.match(str(IPNetwork(ipv4).ip))
        rdns_v4_zone = instance.network.dns_reverse_provider_config['v4_rdns_zone']
        v4_ptr = "{0}.{1}".format(m.group(4), rdns_v4_zone)
    else:
        v4_ptr = ipaddress.IPv4Address(str(IPNetwork(ipv4).ip)).reverse_pointer
        rdns_v4_zones = instance.platform.dns_reverse().search("*{}.in-addr.arpa".format(str(v4_ptr).split('.')[3]), 2000, "zone")
        rdns_v4_zone = None
        rdns_v4_zone_accuracy = 30
        for zone in [sub['name'] for sub in rdns_v4_zones]:
            test = str(v4_ptr).split('.')
            for i in range(len(test) - 3):
                x = len(test) - i
                if '.'.join(test[-x:]) + '.' in zone and rdns_v4_zone_accuracy > i:
                    rdns_v4_zone = zone
                    rdns_v4_zone_accuracy = i
                    break

    v6_ptr = ipaddress.IPv6Address(str(IPNetwork(ipv6).ip)).reverse_pointer
    rdns_v6_zones = instance.platform.dns_reverse().search("*.ip6.arpa", 2000, "zone")
    rdns_v6_zone = None
    rdns_v6_zone_accuracy = 30
    for zone in [sub['name'] for sub in rdns_v6_zones]:
        test = str(v6_ptr).split('.')
        for i in range(len(test) - 3):
            x = len(test) - i
            if ".".join(test[-x:]) + '.' in zone and rdns_v6_zone_accuracy > i:
                rdns_v6_zone = zone
                rdns_v6_zone_accuracy = i
                break

    if rdns_v4_zone is not None:
        rrsets = []
        rrsets.append({
            "name": v4_ptr + '.',
            "changetype": "replace",
            "type": "PTR",
            "records": [{
                "content": fqdn,
                "disabled": False,
            }],
            "ttl": 900
        })
        # Todo check return status
        instance.platform.dns_reverse().set_records(rdns_v4_zone, rrsets)
        instance.dns_reverse_provider_state['rrsets'][rdns_v4_zone] = rrsets
        instance.save()

    if rdns_v6_zone is not None:
        rrsets = []
        rrsets.append({
            "name": v6_ptr + '.',
            "changetype": "replace",
            "type": "PTR",
            "records": [{
                "content": fqdn,
                "disabled": False,
            }],
            "ttl": 900
        })
        # Todo check return status
        instance.platform.dns_reverse().set_records(rdns_v6_zone, rrsets)
        instance.dns_reverse_provider_state['rrsets'][rdns_v6_zone] = rrsets
        instance.save()

    instance.dns_reverse_provider_state['status'] = "provisioned"
    return True


def delete_forward_instance(instance):
    if 'rrsets' not in instance.dns_forward_provider_state:
        return True

    for domain in list(instance.dns_forward_provider_state['rrsets']):
        rrsets = []
        for rrset in instance.dns_forward_provider_state['rrsets'][domain]:
            rrset['changetype'] = "delete"
            rrset['ttl'] = None
            rrset['records'] = []
            rrsets.append(rrset)
        print(instance.platform.dns_forward().set_records(domain, rrsets))
    return True


def delete_reverse_instance(instance):
    if 'rrsets' not in instance.dns_reverse_provider_state:
        return True

    for domain in list(instance.dns_reverse_provider_state['rrsets']):
        rrsets = []
        for rrset in instance.dns_reverse_provider_state['rrsets'][domain]:
            rrset['changetype'] = "delete"
            rrset['ttl'] = None
            rrset['records'] = []
            rrsets.append(rrset)
        print(instance.platform.dns_reverse().set_records(domain, rrsets))
    return True
