In Mininet do `h1 iperf -u -s -B 10.0.0.1 &`
In Mininet do `h2 iperf -u -c 10.0.0.1 -b 10M &`

*Watch bandwidth: they're all zero*

In Mininet do `s1 ifconfig s1-eth3 down`

*Watch bandwidth: they're all roughly 10 Mbps: UDP has been rerouted to TCP path on port 2*

In Mininet do `s1 ifconfig s1-eth3 up`
