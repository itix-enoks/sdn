# Start the controller with Ryu
`ryu-manager ryu/app/simple_switch_stp_13.py`

# Start the network with Mininet
`sudo mn --custom parkinglot_extended_ryu.py --topo extendedparkinglottopo,4 --controller=remote`

## Verify with `ping`
`h1_a ping h2_b`
