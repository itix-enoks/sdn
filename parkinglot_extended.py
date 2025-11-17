#!/usr/bin/env python3
from mininet.topo import Topo

class ExtendedParkingLotTopo(Topo):
    def __init__(self, n=1):
        Topo.__init__(self)

        switches = []
        for i in range(0, n):
            _id = i + 1

            s = self.addSwitch(f's{_id}', stp=True)
            switches.append(s)

        for (i, s) in enumerate(switches):
            _id = i + 1

            h = self.addHost(f'h{_id}_a')
            h1 = self.addHost(f'h{_id}_b')

            self.addLink(h, s)
            self.addLink(h1, s)

        if n > 2:
            try:
                (first_s, last_s) = (switches[0], switches[-1])
                self.addLink(first_s, last_s, bw=10, delay='5ms')
            except IndexError:
                return

        for i in range(0, len(switches) - 1):
            self.addLink(switches[i], switches[i + 1], bw=10, delay='5ms')

topos = {'extendedparkinglottopo': ExtendedParkingLotTopo}
