# TODO Change to ipaddress
from netaddr import IPNetwork


def create_host(instance):
    ip4 = instance.ipam_provider_state['ip_addresses'][0]['address']
    client = instance.platform.identity_management()
    fqdn = '{}.{}'.format(
        instance.name,
        instance.platform.dns_forward_provider_config['domain']
    )
    r = client.host_add(fqdn, o_ip_address=str(
        IPNetwork(ip4).ip), o_random=True)

    instance.identity_management_provider_state['status'] = 'provisioned'
    instance.identity_management_provider_state['fqdn'] = r['result']['fqdn'][0]
    instance.identity_management_provider_state['joinpassword'] = r['result']['randompassword']
    instance.identity_management_provider_state['dn'] = r['result']['dn']
    instance.save()

    # client.hostgroup_add_member(hostgroup, o_host=fqdn)
    return True


def delete_host(instance):
    client = instance.platform.identity_management()
    r = client.host_del(instance.identity_management_provider_state['fqdn'])
    print(r)
    return True
