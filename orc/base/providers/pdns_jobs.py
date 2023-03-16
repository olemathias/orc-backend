from django_rq import job
import re
import ipaddress
# TODO Change to ipaddress
from netaddr import IPNetwork


@job
def update_instance_dns(instance):
    fqdn = "{}.{}.".format(instance.name, instance.platform.config['domain'])
    ip4 = str(IPNetwork(instance.ipam_provider_state['ip_addresses'][0]['address']).ip)
    ip6 = str(IPNetwork(instance.ipam_provider_state['ip_addresses'][1]['address']).ip)
    if 'type' not in instance.dns_provider_state:
        instance.ipam_provider_state = {}
        instance.dns_provider_state['type'] = 'powerdns'
        rrsets = []
        rrsets.append({
            "name": fqdn,
            "changetype": "replace",
            "type": "A",
            "records": [{
                "content": ip4,
                "disabled": False,
                "type": "A"
            }],
            "ttl": 900
        })
        rrsets.append({
            "name": fqdn,
            "changetype": "replace",
            "type": "AAAA",
            "records": [{
                "content": ip6,
                "disabled": False,
                "type": "AAAA"
            }],
            "ttl": 900
        })

        print(instance.platform.dns().set_records(
            instance.platform.dns_forward_provider_config['domain'] + ".", rrsets))
        instance.ipam_provider_state['rrsets'] = {}
        instance.ipam_provider_state['rrsets'][instance.platform.config['domain'] + "."] = rrsets
        instance.save()

        # Hack to support custom in-addr.arpa zones.
        # Example zone 64-127.182.80.185.in-addr.arpa (for a network smaller then /24)
        # Assumes that this will never be used on larger networks than /24
        if 'v4_rdns_zone' in instance.network.dns_reverse_provider_config:
            p = re.compile('(.*)\\.(.*)\\.(.*)\\.(.*)')
            m = p.match(ip4)
            rdns_v4_zone = instance.network.dns_reverse_provider_config['v4_rdns_zone']
            v4_ptr = "{0}.{1}".format(m.group(4), rdns_v4_zone)
        else:
            rdns_v4_zones = instance.platform.dns().search("*.in-addr.arpa", 2000, "zone")
            v4_ptr = ipaddress.IPv4Address(
                instance.config['net']['ipv4']['ip']).reverse_pointer
            rdns_v4_zone = None
            for zone in [sub['name'] for sub in rdns_v4_zones]:
                test = str(v4_ptr).split('.')
                for i in range(len(test) - 2):
                    x = len(test) - i
                    if ".".join(test[-x:]) + '.' in zone:
                        rdns_v4_zone = zone
                        break

        rdns_v6_zones = instance.platform.dns().search("*.ip6.arpa", 2000, "zone")
        v6_ptr = ipaddress.IPv6Address(
            instance.config['net']['ipv6']['ip']).reverse_pointer
        rdns_v6_zone = None
        for zone in [sub['name'] for sub in rdns_v6_zones]:
            test = str(v6_ptr).split('.')
            for i in range(len(test) - 2):
                x = len(test) - i
                if ".".join(test[-x:]) + '.' in zone:
                    rdns_v6_zone = zone
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
                    "type": "PTR"
                }],
                "ttl": 900
            })
            print(rdns_v4_zone)
            print(rrsets)
            print(instance.platform.dns().set_records(rdns_v4_zone, rrsets))
            instance.ipam_provider_state['rrsets'][rdns_v4_zone] = rrsets
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
                    "type": "PTR"
                }],
                "ttl": 900
            })
            print(rdns_v6_zone)
            print(rrsets)
            print(instance.platform.dns().set_records(rdns_v6_zone, rrsets))
            instance.ipam_provider_state['rrsets'][rdns_v6_zone] = rrsets
            instance.save()

        instance.ipam_provider_state['status'] = "provisioned"
