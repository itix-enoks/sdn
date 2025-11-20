# Copyright (C) 2011 Nippon Telegraph and Telephone Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
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
from ryu.lib.packet import ipv4
from ryu.lib.packet import ipv6
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import arp


class ProactiveProtocolSwitch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(ProactiveProtocolSwitch, self).__init__(*args, **kwargs)
        self.mac_to_port = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        self.logger.info("Switch connected: dpid=%s", datapath.id)
        self.install_protocol_flows(datapath)

    def install_protocol_flows(self, datapath):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        dpid = datapath.id

        self.logger.info("Installing protocol-based flows for switch %s", dpid)

        # Clear existing flows first (except table-miss)
        self.delete_flows(datapath)

        if dpid == 1:  # Switch 1
            # Flows from h1 to h2 via different protocols
            # ICMP/ICMPv6/ARP -> port 4
            self.add_flow(datapath, 10,
                         parser.OFPMatch(eth_type=0x0800, ip_proto=1, in_port=1),
                         [parser.OFPActionOutput(4)])  # ICMPv4
            self.add_flow(datapath, 10,
                         parser.OFPMatch(eth_type=0x86DD, ip_proto=58, in_port=1),
                         [parser.OFPActionOutput(4)])  # ICMPv6
            self.add_flow(datapath, 10,
                         parser.OFPMatch(eth_type=0x0806, in_port=1),
                         [parser.OFPActionOutput(4)])  # ARP

            # UDP -> port 3
            self.add_flow(datapath, 10,
                         parser.OFPMatch(eth_type=0x0800, ip_proto=17, in_port=1),
                         [parser.OFPActionOutput(3)])  # UDPv4
            self.add_flow(datapath, 10,
                         parser.OFPMatch(eth_type=0x86DD, ip_proto=17, in_port=1),
                         [parser.OFPActionOutput(3)])  # UDPv6

            # TCP -> port 2
            self.add_flow(datapath, 10,
                         parser.OFPMatch(eth_type=0x0800, ip_proto=6, in_port=1),
                         [parser.OFPActionOutput(2)])  # TCPv4
            self.add_flow(datapath, 10,
                         parser.OFPMatch(eth_type=0x86DD, ip_proto=6, in_port=1),
                         [parser.OFPActionOutput(2)])  # TCPv6

            # Return traffic from switch 2 -> always to h1 (port 1)
            self.add_flow(datapath, 5,
                         parser.OFPMatch(in_port=2),
                         [parser.OFPActionOutput(1)])
            self.add_flow(datapath, 5,
                         parser.OFPMatch(in_port=3),
                         [parser.OFPActionOutput(1)])
            self.add_flow(datapath, 5,
                         parser.OFPMatch(in_port=4),
                         [parser.OFPActionOutput(1)])

        elif dpid == 2:  # Switch 2
            # Flows from h2 to h1 via different protocols
            # ICMP/ICMPv6/ARP -> port 4
            self.add_flow(datapath, 10,
                         parser.OFPMatch(eth_type=0x0800, ip_proto=1, in_port=1),
                         [parser.OFPActionOutput(4)])  # ICMPv4
            self.add_flow(datapath, 10,
                         parser.OFPMatch(eth_type=0x86DD, ip_proto=58, in_port=1),
                         [parser.OFPActionOutput(4)])  # ICMPv6
            self.add_flow(datapath, 10,
                         parser.OFPMatch(eth_type=0x0806, in_port=1),
                         [parser.OFPActionOutput(4)])  # ARP

            # UDP -> port 3
            self.add_flow(datapath, 10,
                         parser.OFPMatch(eth_type=0x0800, ip_proto=17, in_port=1),
                         [parser.OFPActionOutput(3)])  # UDPv4
            self.add_flow(datapath, 10,
                         parser.OFPMatch(eth_type=0x86DD, ip_proto=17, in_port=1),
                         [parser.OFPActionOutput(3)])  # UDPv6

            # TCP -> port 2
            self.add_flow(datapath, 10,
                         parser.OFPMatch(eth_type=0x0800, ip_proto=6, in_port=1),
                         [parser.OFPActionOutput(2)])  # TCPv4
            self.add_flow(datapath, 10,
                         parser.OFPMatch(eth_type=0x86DD, ip_proto=6, in_port=1),
                         [parser.OFPActionOutput(2)])  # TCPv6

            # Return traffic from switch 1 -> always to h2 (port 1)
            self.add_flow(datapath, 5,
                         parser.OFPMatch(in_port=2),
                         [parser.OFPActionOutput(1)])
            self.add_flow(datapath, 5,
                         parser.OFPMatch(in_port=3),
                         [parser.OFPActionOutput(1)])
            self.add_flow(datapath, 5,
                         parser.OFPMatch(in_port=4),
                         [parser.OFPActionOutput(1)])

        # Default flood for unknown traffic (lower priority)
        self.add_flow(datapath, 1,
                     parser.OFPMatch(),
                     [parser.OFPActionOutput(ofproto.OFPP_FLOOD)])

        self.logger.info("Finished installing flows for switch %s", dpid)

    def delete_flows(self, datapath):
        """Remove all flows from the switch"""
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

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        """Handle packets that don't match any flow"""
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

        # Flood the packet (default behavior)
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)
