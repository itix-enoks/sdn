# Copyright (C) 2011 Nippon Telegraph and Telephone Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib import hub


class ProactiveProtocolSwitch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(ProactiveProtocolSwitch, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.prev_port_bytes = {}   # (dpid, port_no) -> (tx_bytes, timestamp)
        self.pollers = {}
        self.datapaths = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        self.logger.info("Switch connected: dpid=%s", datapath.id)
        self.datapaths[datapath.id] = datapath
        self.install_protocol_flows(datapath)

        if datapath.id not in self.pollers:
            g = hub.spawn(self._poll_stats, datapath)
            self.pollers[datapath.id] = g

    def install_protocol_flows(self, datapath):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        dpid = datapath.id

        self.logger.info("Installing protocol-based flows for switch %s", dpid)

        # Clear existing flows first
        self.delete_flows(datapath)

        # Fast-failover group for UDP
        udp_group_id = 50

        if dpid == 1:
            buckets = [
                parser.OFPBucket(0, 3, 0, [parser.OFPActionOutput(3)]),
                parser.OFPBucket(0, 2, 0, [parser.OFPActionOutput(2)])
            ]
            req = parser.OFPGroupMod(datapath, ofproto.OFPGC_ADD,
                                     ofproto.OFPGT_FF, udp_group_id, buckets)
            datapath.send_msg(req)

            # ICMP / ARP
            self.add_flow(datapath, 10,
                          parser.OFPMatch(eth_type=0x0800, ip_proto=1, in_port=1),
                          [parser.OFPActionOutput(4)])
            self.add_flow(datapath, 10,
                          parser.OFPMatch(eth_type=0x86DD, ip_proto=58, in_port=1),
                          [parser.OFPActionOutput(4)])
            self.add_flow(datapath, 10,
                          parser.OFPMatch(eth_type=0x0806, in_port=1),
                          [parser.OFPActionOutput(4)])

            # UDP → group
            self.add_flow(datapath, 10,
                          parser.OFPMatch(eth_type=0x0800, ip_proto=17, in_port=1),
                          [parser.OFPActionGroup(udp_group_id)])
            self.add_flow(datapath, 10,
                          parser.OFPMatch(eth_type=0x86DD, ip_proto=17, in_port=1),
                          [parser.OFPActionGroup(udp_group_id)])

            # TCP → port 2
            self.add_flow(datapath, 10,
                          parser.OFPMatch(eth_type=0x0800, ip_proto=6, in_port=1),
                          [parser.OFPActionOutput(2)])
            self.add_flow(datapath, 10,
                          parser.OFPMatch(eth_type=0x86DD, ip_proto=6, in_port=1),
                          [parser.OFPActionOutput(2)])

            # Return traffic → port 1
            for in_port in [2, 3, 4]:
                self.add_flow(datapath, 5,
                              parser.OFPMatch(in_port=in_port),
                              [parser.OFPActionOutput(1)])

        elif dpid == 2:
            buckets = [
                parser.OFPBucket(0, 3, 0, [parser.OFPActionOutput(3)]),
                parser.OFPBucket(0, 2, 0, [parser.OFPActionOutput(2)])
            ]
            req = parser.OFPGroupMod(datapath, ofproto.OFPGC_ADD,
                                     ofproto.OFPGT_FF, udp_group_id, buckets)
            datapath.send_msg(req)

            # ICMP / ARP
            self.add_flow(datapath, 10,
                          parser.OFPMatch(eth_type=0x0800, ip_proto=1, in_port=1),
                          [parser.OFPActionOutput(4)])
            self.add_flow(datapath, 10,
                          parser.OFPMatch(eth_type=0x86DD, ip_proto=58, in_port=1),
                          [parser.OFPActionOutput(4)])
            self.add_flow(datapath, 10,
                          parser.OFPMatch(eth_type=0x0806, in_port=1),
                          [parser.OFPActionOutput(4)])

            # UDP → group
            self.add_flow(datapath, 10,
                          parser.OFPMatch(eth_type=0x0800, ip_proto=17, in_port=1),
                          [parser.OFPActionGroup(udp_group_id)])
            self.add_flow(datapath, 10,
                          parser.OFPMatch(eth_type=0x86DD, ip_proto=17, in_port=1),
                          [parser.OFPActionGroup(udp_group_id)])

            # TCP → port 2
            self.add_flow(datapath, 10,
                          parser.OFPMatch(eth_type=0x0800, ip_proto=6, in_port=1),
                          [parser.OFPActionOutput(2)])
            self.add_flow(datapath, 10,
                          parser.OFPMatch(eth_type=0x86DD, ip_proto=6, in_port=1),
                          [parser.OFPActionOutput(2)])

            # Return traffic → port 1
            for in_port in [2, 3, 4]:
                self.add_flow(datapath, 5,
                              parser.OFPMatch(in_port=in_port),
                              [parser.OFPActionOutput(1)])

        # Default flood
        self.add_flow(datapath, 1,
                      parser.OFPMatch(),
                      [parser.OFPActionOutput(ofproto.OFPP_FLOOD)])

        self.logger.info("Finished installing flows for switch %s", dpid)

    def delete_flows(self, datapath):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        mod = parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY,
            match=match
        )
        datapath.send_msg(mod)
        self.logger.info("Cleared all flows from switch %s", datapath.id)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match, instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats_reply_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        dpid = dp.id

        for stat in msg.body:
            if stat.port_no != 2:
                continue

            key = (dpid, 2)
            tx_bytes = stat.tx_bytes
            timestamp = stat.duration_sec + stat.duration_nsec / 1e9

            prev = self.prev_port_bytes.get(key)
            if prev is None:
                self.prev_port_bytes[key] = (tx_bytes, timestamp)
                continue

            prev_bytes, prev_time = prev
            delta_bytes = tx_bytes - prev_bytes
            delta_time = timestamp - prev_time

            bw_mbps = (delta_bytes * 8) / (delta_time * 1e6) if delta_time > 0 else 0.0

            # Same print format as before
            print(f"bandwidth = {bw_mbps} Mbps")

            self.prev_port_bytes[key] = (tx_bytes, timestamp)

    def _poll_stats(self, datapath):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        self.logger.info("Starting port stats polling thread for switch %s", datapath.id)

        while True:
            try:
                req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
                datapath.send_msg(req)
            except Exception as e:
                self.logger.exception("Exception while sending port stats request: %s", e)
            hub.sleep(1)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        self.logger.info("Packet-in from switch %s port %s - no flow match",
                         datapath.id, in_port)

        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)
