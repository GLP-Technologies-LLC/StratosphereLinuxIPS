# Must imports
from slips_files.common.abstracts import Module
import multiprocessing
from slips_files.core.database import __database__
from slips_files.common.slips_utils import utils
import sys

# Your imports
import ipaddress
import json

# Port Scan Detector Process
class PortScanProcess(Module, multiprocessing.Process):
    """
    A class process to find port scans
    This should be converted into a module that wakesup alone when a new alert arrives
    """

    name = 'portscandetector-1'
    description = 'Detect Horizonal, Vertical and ICMP scans'
    authors = ['Sebastian Garcia']

    def __init__(self, outputqueue, config, redis_port):
        multiprocessing.Process.__init__(self)
        self.outputqueue = outputqueue
        self.config = config
        # Start the DB
        __database__.start(self.config, redis_port)
        # Set the output queue of our database instance
        __database__.setOutputQueue(self.outputqueue)
        # Get from the database the separator used to separate the IP and the word profile
        self.fieldseparator = __database__.getFieldSeparator()
        # To which channels do you wnat to subscribe? When a message arrives on the channel the module will wakeup
        self.c1 = __database__.subscribe('tw_modified')
        self.c2 = __database__.subscribe('new_notice')

        # We need to know that after a detection, if we receive another flow
        # that does not modify the count for the detection, we are not
        # re-detecting again only because the threshold was overcomed last time.
        self.cache_det_thresholds = {}
        # Retrieve malicious/benigh labels
        self.normal_label = __database__.normal_label
        self.malicious_label = __database__.malicious_label
        self.timeout = 0.0000001
        self.separator = '_'
        # The minimum amount of ips to scan horizontal scan
        self.port_scan_minimum_dips_threshold = 6
        # The minimum amount of ports to scan in vertical scan
        self.port_scan_minimum_dports_threshold = 6

    def shutdown_gracefully(self):
        # Confirm that the module is done processing
        __database__.publish('finished_modules', self.name)

    def print(self, text, verbose=1, debug=0):
        """
        Function to use to print text using the outputqueue of slips.
        Slips then decides how, when and where to print this text by taking all the processes into account
        :param verbose:
            0 - don't print
            1 - basic operation/proof of work
            2 - log I/O operations and filenames
            3 - log database/profile/timewindow changes
        :param debug:
            0 - don't print
            1 - print exceptions
            2 - unsupported and unhandled types (cases that may cause errors)
            3 - red warnings that needs examination - developer warnings
        :param text: text to print. Can include format like 'Test {}'.format('here')
        """

        levels = f'{verbose}{debug}'
        self.outputqueue.put(f'{levels}|{self.name}|{text}')

    def check_horizontal_portscan(self, profileid, twid):

        saddr = profileid.split(self.fieldseparator)[1]
        try:
            saddr_obj = ipaddress.ip_address(saddr)
            if saddr == '255.255.255.255' or saddr_obj.is_multicast:
                # don't report port scans on the broadcast or multicast addresses
                return False
        except ValueError:
            # is an ipv6
            pass

        # Get the list of dports that we connected as client using TCP not established
        direction = 'Dst'
        state = 'NotEstablished'
        role = 'Client'
        type_data = 'Ports'
        for protocol in ('TCP', 'UDP'):
            data = __database__.getDataFromProfileTW(
                profileid, twid, direction, state, protocol, role, type_data
            )
            # For each port, see if the amount is over the threshold
            for dport in data.keys():
                ### PortScan Type 2. Direction OUT
                dstips = data[dport]['dstips']
                # this is the list of dstips that have dns resolution, we will remove them from the dstips later
                dstips_to_discard = []
                # Remove dstips that have DNS resolution already
                for dip in dstips:
                    dns_resolution = __database__.get_dns_resolution(dip)
                    dns_resolution = dns_resolution.get('domains', [])
                    if dns_resolution:
                        dstips_to_discard.append(dip)
                # remove the resolved dstips from dstips dict
                for ip in dstips_to_discard:
                    dstips.pop(ip)

                amount_of_dips = len(dstips)
                # If we contacted more than 3 dst IPs on this port with not established connections.. we have evidence
                # self.print('Horizontal Portscan check. Amount of dips: {}. Threshold=3'.format(amount_of_dips), 3, 0)

                # Type of evidence
                type_evidence = 'PortScanType2'
                # Key
                type_detection = 'srcip'
                srcip = profileid.split(self.fieldseparator)[1]
                source_target_tag = 'Recon'
                detection_info = srcip
                # Threat level
                threat_level = 'medium'
                category = 'Recon.Scanning'
                # Compute the confidence
                pkts_sent = 0
                # We detect a scan every Threshold. So, if threshold is 3, we detect when there are 3, 6, 9, 12, etc. dips per port.
                # The idea is that after X dips we detect a connection. And then we 'reset' the counter until we see again X more.
                key = 'dport' + ':' + dport + ':' + type_evidence
                cache_key = profileid + ':' + twid + ':' + key
                try:
                    prev_amount_dips = self.cache_det_thresholds[cache_key]
                except KeyError:
                    prev_amount_dips = 0
                # self.print('Key: {}. Prev dips: {}, Current: {}'.format(cache_key, prev_amount_dips, amount_of_dips))
                if (
                    amount_of_dips % self.port_scan_minimum_dips_threshold == 0
                    and prev_amount_dips < amount_of_dips
                ):
                    for dip in dstips:
                        # Get the total amount of pkts sent to the same port to all IPs
                        pkts_sent += dstips[dip]['pkts']

                    if pkts_sent > 10:
                        confidence = 1
                    else:
                        # Between threshold and 10 pkts compute a kind of linear grow
                        confidence = pkts_sent / 10.0
                    # Description
                    portproto = f'{dport}/{protocol}'
                    port_info = __database__.get_port_info(portproto)
                    description = (
                        f'horizontal port scan to port {port_info if port_info else ""} {portproto}. '
                        f'From {saddr} to {amount_of_dips} unique dst IPs. '
                        f'Tot pkts: {pkts_sent}. Threat Level: {threat_level}. Confidence: {confidence}'
                    )
                    uid = next(iter(dstips.values()))[
                        'uid'
                    ]   # first uid in the dictionary
                    timestamp = next(iter(dstips.values()))['stime']
                    __database__.setEvidence(
                        type_evidence,
                        type_detection,
                        detection_info,
                        threat_level,
                        confidence,
                        description,
                        timestamp,
                        category,
                        conn_count=pkts_sent,
                        source_target_tag=source_target_tag,
                        port=dport,
                        proto=protocol,
                        profileid=profileid,
                        twid=twid,
                        uid=uid,
                    )
                    # Set 'malicious' label in the detected profile
                    __database__.set_profile_module_label(
                        profileid, type_evidence, self.malicious_label
                    )
                    self.print(description, 3, 0)
                    # Store in our local cache how many dips were there:
                    self.cache_det_thresholds[cache_key] = amount_of_dips

    def check_vertical_portscan(self, profileid, twid):
        # Get the list of dstips that we connected as client using TCP not established, and their ports
        direction = 'Dst'
        state = 'NotEstablished'
        role = 'Client'
        type_data = 'IPs'
        # self.print('Vertical Portscan check. Amount of dports: {}. Threshold=3'.format(amount_of_dports), 3, 0)
        # Type of evidence
        type_detection = 'srcip'
        type_evidence = 'PortScanType1'
        source_target_tag = 'Recon'
        # Threat level
        threat_level = 'medium'
        category = 'Recon.Scanning'
        for protocol in ('TCP', 'UDP'):
            data = __database__.getDataFromProfileTW(
                profileid, twid, direction, state, protocol, role, type_data
            )
            # For each dstip, see if the amount of ports connections is over the threshold
            for dstip in data.keys():
                ### PortScan Type 1. Direction OUT
                # dstports is a dict
                dstports = data[dstip]['dstports']
                amount_of_dports = len(dstports)
                srcip = profileid.split(self.fieldseparator)[1]
                detection_info = srcip
                # Key
                key = 'dstip' + ':' + dstip + ':' + type_evidence
                # We detect a scan every Threshold. So we detect when there is 6, 9, 12, etc. dports per dip.
                # The idea is that after X dips we detect a connection. And then we 'reset' the counter until we see again X more.
                cache_key = f'{profileid}:{twid}:{key}'
                try:
                    prev_amount_dports = self.cache_det_thresholds[cache_key]
                except KeyError:
                    prev_amount_dports = 0
                # self.print('Key: {}, Prev dports: {}, Current: {}'.format(cache_key, prev_amount_dports, amount_of_dports))
                if (
                        amount_of_dports % self.port_scan_minimum_dports_threshold
                        == 0
                        and prev_amount_dports < amount_of_dports
                ):
                    # Get the total amount of pkts sent to the same port to all IPs
                    pkts_sent = sum(dstports[dport] for dport in dstports)
                    if pkts_sent > 10:
                        confidence = 1
                    elif pkts_sent == 0:
                        # if the sum of all pkts sent TO these IPs on these dports
                        # are 0, then this is not a portscan
                        return
                    else:
                        # Between threshold and 10 pkts compute a kind of linear grow
                        confidence = pkts_sent / 10.0
                    # Description
                    description = (
                        f'new vertical port scan to IP {dstip} from {srcip}. '
                        f'Total {amount_of_dports} dst ports of protocol {protocol}. '
                        f'Not Established. Tot pkts sent all ports: {pkts_sent}. '
                        f'Confidence: {confidence}'
                    )
                    uid = data[dstip]['uid']
                    timestamp = data[dstip]['stime']
                    __database__.setEvidence(
                        type_evidence,
                        type_detection,
                        detection_info,
                        threat_level,
                        confidence,
                        description,
                        timestamp,
                        category,
                        conn_count=pkts_sent,
                        source_target_tag=source_target_tag,
                        proto=protocol,
                        profileid=profileid,
                        twid=twid,
                        uid=uid,
                    )
                    # Set 'malicious' label in the detected profile
                    __database__.set_profile_module_label(
                        profileid, type_evidence, self.malicious_label
                    )
                    self.print(description, 3, 0)
                    # Store in our local cache how many dips were there:
                    self.cache_det_thresholds[cache_key] = amount_of_dports

    def check_icmp_sweep(self, msg, note, profileid, uid, twid, timestamp):

        if 'TimestampScan' in note:
            type_evidence = 'ICMP-Timestamp-Scan'
        elif 'ICMPAddressScan' in note:
            type_evidence = 'ICMP-AddressScan'
        elif 'AddressMaskScan' in note:
            type_evidence = 'ICMP-AddressMaskScan'
        else:
            # unsupported notice type
            return False

        hosts_scanned = int(msg.split('on ')[1].split(' hosts')[0])
        # get the confidence from 0 to 1 based on the number of hosts scanned
        confidence = 1 / (255 - 5) * (hosts_scanned - 255) + 1
        threat_level = 'medium'
        category = 'Recon.Scanning'
        # type_detection is set to dstip even though the srcip is the one performing the scan
        # because setEvidence doesn't alert on the same key twice, so we have to send different keys to be able
        # to generate an alert every 5,10,15,.. scans #todo test this
        type_detection = 'srcip'
        # this is the last dip scanned
        detection_info = profileid.split('_')[1]
        source_target_tag = 'Recon'
        description = msg
        __database__.setEvidence(
            type_evidence,
            type_detection,
            detection_info,
            threat_level,
            confidence,
            description,
            timestamp,
            category,
            source_target_tag=source_target_tag,
            conn_count=hosts_scanned,
            profileid=profileid,
            twid=twid,
            uid=uid,
        )

    def check_portscan_type3(self):
        """
        ###
        # PortScan Type 3. Direction OUT
        # Considering all the flows in this TW, for all the Dst IP, get the sum of all the pkts send to each dst port TCP No tEstablished
        totalpkts = int(data[dport]['totalpkt'])
        # If for each port, more than X amount of packets were sent, report an evidence
        if totalpkts > 3:
            # Type of evidence
            type_evidence = 'PortScanType3'
            # Key
            key = 'dport' + ':' + dport + ':' + type_evidence
            # Description
            description = 'Too Many Not Estab TCP to same port {} from IP: {}. Amount: {}'.format(dport, profileid.split('_')[1], totalpkts)
            # Threat level
            threat_level = 50
            # Confidence. By counting how much we are over the threshold.
            if totalpkts >= 10:
                # 10 pkts or more, receive the max confidence
                confidence = 1
            else:
                # Between 3 and 10 pkts compute a kind of linear grow
                confidence = totalpkts / 10.0
            __database__.setEvidence(profileid, twid, type_evidence, threat_level, confidence)
            self.print('Too Many Not Estab TCP to same port {} from IP: {}. Amount: {}'.format(dport, profileid.split('_')[1], totalpkts),6,0)
        """

    def run(self):
        utils.drop_root_privs()
        while True:
            try:
                # Wait for a message from the channel that a TW was modified
                message = self.c1.get_message(timeout=self.timeout)
                # print('Message received from channel {} with data {}'.format(message['channel'], message['data']))
                if message and message['data'] == 'stop_process':
                    self.shutdown_gracefully()
                    return True

                if utils.is_msg_intended_for(message, 'tw_modified'):
                    # Get the profileid and twid
                    profileid = message['data'].split(':')[0]
                    twid = message['data'].split(':')[1]
                    # Start of the port scan detection
                    self.print(
                        f'Running the detection of portscans in profile '
                        f'{profileid} TW {twid}', 3, 0
                    )

                    # For port scan detection, we will measure different things:

                    # 1. Vertical port scan:
                    # (single IP being scanned for multiple ports)
                    # - 1 srcip sends not established flows to > 3 dst ports in the same dst ip. Any number of packets
                    # 2. Horizontal port scan:
                    #  (scan against a group of IPs for a single port)
                    # - 1 srcip sends not established flows to the same dst ports in > 3 dst ip.
                    # 3. Too many connections???:
                    # - 1 srcip sends not established flows to the same dst ports, > 3 pkts, to the same dst ip
                    # 4. Slow port scan. Same as the others but distributed in multiple time windows

                    # Remember that in slips all these port scans can happen for traffic going IN to an IP or going OUT from the IP.

                    self.check_horizontal_portscan(profileid, twid)
                    self.check_vertical_portscan(profileid, twid)

                message = self.c2.get_message(timeout=self.timeout)
                # print('Message received from channel {} with data {}'.format(message['channel'], message['data']))
                if message and message['data'] == 'stop_process':
                    self.shutdown_gracefully()
                    return True

                if utils.is_msg_intended_for(message, 'new_notice'):
                    data = message['data']
                    if type(data) != str:
                        continue
                    # Convert from json to dict
                    data = json.loads(data)
                    profileid = data['profileid']
                    twid = data['twid']
                    # Get flow as a json
                    flow = data['flow']
                    # Convert flow to a dict
                    flow = json.loads(flow)
                    timestamp = flow['stime']
                    uid = data['uid']
                    msg = flow['msg']
                    note = flow['note']
                    self.check_icmp_sweep(
                        msg, note, profileid, uid, twid, timestamp
                    )

            except KeyboardInterrupt:
                self.shutdown_gracefully()
                return True
            except Exception as inst:
                exception_line = sys.exc_info()[2].tb_lineno
                self.print(f'Problem on the run() line {exception_line}', 0, 1)
                self.print(str(type(inst)), 0, 1)
                self.print(str(inst.args), 0, 1)
                self.print(str(inst), 0, 1)
                return True
