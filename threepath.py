#!/usr/bin/env python3

from mininet.topo import Topo
from mininet.link import TCLink


class ThreePathTopo(Topo):
    """
    h1 -- s_in ------ s_out -- h2
               \----/
               \----/
    All links on the three paths: 10 Mbps, 200 ms.
    Host access links: default Mininet settings.
    """
    def __init__(self):
        Topo.__init__(self)

        # Hosts
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')

        # Switches
        s_in = self.addSwitch('s1')   # ingress
        s_out = self.addSwitch('s2')   # egress

        # Host access links (no shaping)
        self.addLink(h1, s_in)
        self.addLink(s_out, h2)

        # Common link options for the three paths
        path_opts = dict(bw=10, delay='200ms', cls=TCLink)

        # Three paths
        for i in range(3):
            self.addLink(s_in, s_out, **path_opts)


# topo key expected by mn
topos = {'threepath': ThreePathTopo}
