"""Unit test for modules/flowalerts/flowalerts.py"""
from ..modules.flowalerts.flowalerts import Module
import configparser
import json
from numpy import arange

# dummy params used for testing
profileid = 'profile_192.168.1.1'
twid = 'timewindow1'
uid = 'CAeDWs37BipkfP21u8'
timestamp = 1635765895.037696
saddr = '192.168.1.1'
daddr = '192.168.1.2'
dst_profileid = f'profile_{daddr}'


def do_nothing(*args):
    """Used to override the print function because using the self.print causes broken pipes"""
    pass


def create_flowalerts_instance(outputQueue):
    """Create an instance of flowalerts.py
    needed by every other test in this file"""
    config = configparser.ConfigParser()
    flowalerts = Module(outputQueue, config, 6380)
    # override the self.print function to avoid broken pipes
    flowalerts.print = do_nothing
    return flowalerts


def test_check_long_connection(database, outputQueue):
    flowalerts = create_flowalerts_instance(outputQueue)
    # less than the threshold
    dur = '1400'  # in seconds
    database.add_flow(
        profileid=profileid,
        twid=twid,
        stime=timestamp,
        dur=dur,
        saddr=profileid.split('_'),
        daddr=daddr,
        uid=uid,
        flow_type='conn',
    )

    flowalerts.check_long_connection(
        dur, daddr, saddr, profileid, twid, uid, timestamp
    )
    module_labels = database.get_module_labels_from_flow(profileid, twid, uid)
    assert 'flowalerts-long-connection' in module_labels
    assert module_labels['flowalerts-long-connection'] == 'normal'

    # more than the threshold
    dur = 1600  # in seconds
    database.add_flow(
        profileid=profileid,
        twid=twid,
        stime=timestamp,
        dur=dur,
        saddr=profileid.split('_'),
        daddr=daddr,
        uid=uid,
        flow_type='conn',
    )

    flowalerts.check_long_connection(
        dur, daddr, saddr, profileid, twid, uid, timestamp
    )
    module_labels = database.get_module_labels_from_flow(profileid, twid, uid)
    assert 'flowalerts-long-connection' in module_labels
    assert module_labels['flowalerts-long-connection'] == 'malicious'


def test_port_belongs_to_an_org(database, outputQueue):
    flowalerts = create_flowalerts_instance(outputQueue)
    # store in the db that both ips have apple as a vendor
    MAC_info = {'MAC': '123', 'Vendor': 'Apple, Inc'}
    database.add_mac_addr_to_profile(profileid, MAC_info)
    database.add_mac_addr_to_profile(dst_profileid, MAC_info)

    # belongs to apple
    portproto = '65509/tcp'
    database.set_organization_of_port('apple', '', portproto)
    assert (
            flowalerts.port_belongs_to_an_org(
                daddr, portproto, profileid
            ) == True
    )
    # doesn't belong to any org
    portproto = '78965/tcp'
    assert (
            flowalerts.port_belongs_to_an_org(
                daddr, portproto, profileid
            ) == False
    )


def test_check_unknown_port(outputQueue, database):
    flowalerts = create_flowalerts_instance(outputQueue)
    database.set_port_info('23/udp', 'telnet')
    # now we have info 23 udp
    assert (
        flowalerts.check_unknown_port(
            '23', 'udp', daddr, profileid, twid, uid, timestamp
        )
        == False
    )


def test_check_if_resolution_was_made_by_different_version(
    outputQueue, database
):
    flowalerts = create_flowalerts_instance(outputQueue)
    ipv6 = '2001:0db8:85a3:0000:0000:8a2e:0370:7334'
    database.set_ipv6_of_profile(profileid, ipv6)
    other_ip = database.get_the_other_ip_version(profileid)
    assert json.loads(other_ip)[0] == ipv6
    database.set_dns_resolution(
        'example.com', [daddr], timestamp, uid, 'AAAA', ipv6
    )
    res = flowalerts.check_if_resolution_was_made_by_different_version(
        profileid, daddr
    )
    assert res == True


def test_check_dns_arpa_scan(outputQueue, database):
    flowalerts = create_flowalerts_instance(outputQueue)
    # make 10 different arpa scans
    for ts in arange(0, 1, 1 / 10):
        is_arpa_scan = flowalerts.check_dns_arpa_scan(
            'example.in-addr.arpa', timestamp + ts, profileid, twid, uid
        )

    assert is_arpa_scan == True


# check_multiple_ssh_clients is tested in test_dataset
def test_detect_DGA(outputQueue, database):
    flowalerts = create_flowalerts_instance(outputQueue)
    rcode_name = 'NXDOMAIN'
    for i in range(10):
        dga_detected = flowalerts.detect_DGA(
            rcode_name, f'example{i}.com', timestamp, profileid, twid, uid
        )
    assert dga_detected == True


def test_detect_young_domains(outputQueue, database):
    flowalerts = create_flowalerts_instance(outputQueue)
    domain = 'example.com'
    # age in days
    age = 50
    database.setInfoForDomains(domain, {'Age': age})
    assert (
        flowalerts.detect_young_domains(
            domain, timestamp, profileid, twid, uid
        )
        == True
    )
