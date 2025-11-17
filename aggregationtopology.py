#!/usr/bin/env python3
from mininet.topo import Topo

class AggTopo(Topo):
    def __init__(self, n=1, k=1):
        Topo.__init__(self)

        # create 'n' switches
        edges = []
        for i in range(0, n):
            _id = i + 1

            e = self.addSwitch(f'e{_id}', stp=True)
            edges.append(e)

        # add 2 hosts to each switch
        for (i, e) in enumerate(edges):
            _id = i + 1

            h = self.addHost(f'h{_id}_a')
            h1 = self.addHost(f'h{_id}_b')

            self.addLink(h, e)
            self.addLink(h1, e)

        # link switches
        for i in range(0, len(edges) - 1):
            self.addLink(edges[i], edges[i + 1], bw=10, delay='5ms')

        # link each 'k' switches to 1 aggregation
        aggregations = []
        for i in range(0, len(edges), k):
            _id = i // k + 1
            a = self.addSwitch(f'a{_id}', stp=True)
            aggregations.append(a)
            for j in range(0, k):
                edx = i + j

                if edx >= len(edges):
                    return

                e = edges[edx]

                self.addLink(a, e, bw=25, delay='5ms')

        # create loop in aggregations
        if len(aggregations) > 2:
            first_a = aggregations[0]
            last_a = aggregations[-1]

            self.addLink(first_a, last_a, bw=100, delay='5ms')

        # link rest of aggregations
        for i in len(aggregations):
            self.addLink(aggregations[i], aggregations[i + 1], bw=100, delay='5ms')

topos = {'aggtopo': AggTopo}
