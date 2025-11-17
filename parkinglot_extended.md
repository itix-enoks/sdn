### Prompt 1
Why does this create infinite Neighbor Advertisements?
#!/usr/bin/env python3
from mininet.topo import Topo

class ExtendedParkingLotTopo(Topo):
    def __init__(self, n=1):
        Topo.__init__(self)

        switches = []
        for i in range(0, n):
            _id = i + 1

            s = self.addSwitch(f's{_id}')
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
            """
            ^^^This snippet above leads to:
            ```
            mininet> h1_a ping h2_b
            PING 10.0.0.4 (10.0.0.4) 56(84) bytes of data.
            From 10.0.0.1 icmp_seq=1 Destination Host Unreachable
            From 10.0.0.1 icmp_seq=2 Destination Host Unreachable
            From 10.0.0.1 icmp_seq=3 Destination Host Unreachable
            From 10.0.0.1 icmp_seq=4 Destination Host Unreachable
            From 10.0.0.1 icmp_seq=5 Destination Host Unreachable
            From 10.0.0.1 icmp_seq=6 Destination Host Unreachable
            ^C
            --- 10.0.0.4 ping statistics ---
            8 packets transmitted, 0 received, +6 errors, 100% packet loss, time 7133ms
            pipe 4
            ```
            """

        for i in range(0, len(switches) - 1):
            self.addLink(switches[i], switches[i + 1], bw=10, delay='5ms')

topos = {'extendedparkinglottopo': ExtendedParkingLotTopo}

### Answer 1
**Short answer:**
Because the *extra link* you add between the **first** and **last** switch creates a **layer-2 loop**, and Mininet’s default switch (OVS) does **not** run STP unless you explicitly enable it. The loop causes frames (including Neighbor Advertisements, ARP broadcasts, IPv6 NAs/NS) to circulate endlessly, which looks like “infinite Neighbor Advertisements” and breaks connectivity.

---

# Detailed explanation

Your topology without the snippet is a **linear chain**:

```
s1 — s2 — s3 — ... — sn
```

When you add:

```python
self.addLink(first_s, last_s)
```

you turn it into a **ring**:

```
s1 — s2 — s3 — ... — sn
 |_____________________|
```

A ring is *fine* if loop-prevention is active (STP, RSTP, MSTP, etc.).
But in Mininet:

* OVS switches use **`failMode=standalone`**
* `standalone` mode = **no STP**
* No STP = **broadcast, multicast, and unknown unicast loops forever**

IPv6 Neighbor Discovery uses multicast. So:

* Host sends a Neighbor Solicitation (NS) → forwarded to both neighbors
* Comes back around the loop → switch floods it again → indefinitely
* Hosts respond with Neighbor Advertisements (NA) → also loop
* Eventually the host buffers fill and you get *Destination Host Unreachable*

This is classic **L2 broadcast storm** behavior.

---

# Why the ping errors look like that

When you ping from `h1_a` to `h2_b`:

* ARP/ND cannot converge due to looping frames
* Switch forwarding tables never stabilize
* Eventually the host’s IP stack gives up and returns *Destination Host Unreachable*
* But the storm of NA/NS keeps circulating

---

# How to fix it

### **Option 1: Enable STP on all OVS switches**

```python
s = self.addSwitch(f's{_id}', stp=True)
```

or if using the Mininet CLI:

```
ovs-vsctl set bridge s1 stp_enable=true
```

With STP enabled, the ring link will be *blocked*, preventing loops.

---

### **Option 2: Use failMode='secure' and add a controller with STP**

```python
self.addSwitch(f's{_id}', failMode='secure', stp=True)
```

Note: Mininet’s simple controller does **not** implement STP, but OVS implements **bridge STP** internally, so `stp=True` is fine without a controller.

---

### **Option 3: Avoid loops**

If you don’t *need* a ring, remove the extra link.

---

# Example fixed topology snippet

```python
for i in range(n):
    s = self.addSwitch(f's{i+1}', stp=True)
    switches.append(s)
```

Now the ring will no longer create storms, and ping will work.

---

# Summary

You’re seeing infinite Neighbor Advertisements because:

✔ You created a **layer-2 loop**
✔ OVS in Mininet **does not run STP by default**
✔ Loops → infinite flooding → ND/ARP storms → broken ping

Enable STP or remove the loop, and the issue disappears.

---

If you want, I can show you:

* how to visualize the STP port states (blocking/forwarding)
* how to reproduce the storm and confirm with `tcpdump`
* how to convert the topology into a mesh with stable forwarding

Just tell me!

### Prompt 2
Why does the advertisement loop though, if a switch sends it to the correct switch, that receiving switch then doesn't forward it anymore?

### Answer 2:
Great question — this gets to the heart of **why a layer-2 loop loops *even when switches learn MAC addresses***.

The key point is:

# **Switches forward Neighbor Discovery messages *before* they learn where the MAC lives.**

Let’s break down exactly why this happens.

---

# ✅ **1. Neighbor Solicitation / Advertisement uses multicast**

IPv6 ND uses special multicast addresses:

* **Neighbor Solicitation → solicited-node multicast**
* **Neighbor Advertisement → unicast *or* multicast**

Example multicast addresses:

* `ff02::1:ffXX:XXXX` (solicited-node)
* `ff02::1` (all-nodes)

**Switches flood multicast frames**, just like broadcasts.

So the first NS/NA *is ALWAYS FLOODED*.

That means:
Switch A sends NS → floods all ports → goes into the loop → comes back → gets flooded again → etc.

Even if a switch learns MACs later, multicast frames are **never sent to a single port**.

So loops circulate forever.

---

# ✅ **2. Even unicast NA packets can loop before MAC learning stabilizes**

Imagine the loop:

```
s1 -- s2 -- s3
 |           |
 -------------
```

Hosts:

```
h1 on s1
h2 on s3
```

### Step-by-step

1. **h1 sends NS → multicast**
2. **Multicast floods through the loop**
3. Switches try to learn MACs *but frames keep coming from different directions* because of the loop.

Example:

* s1 first sees h1’s MAC via port “host”
* but the loop brings h1’s multicast frame **back into s1 from the ring link**
* s1 now thinks “oh, MAC(h1) is on port towards s3”
* Then another copy comes from the other direction
* s1 changes its mind *again*

This is called **MAC flapping**.

Because the switch keeps relearning the MAC from alternating ports, it **never gets a stable entry**, so even unicast Neighbor Advertisements get flooded again.

This is why ARP/ND completely breaks in loops.

---

# ✅ **3. Why doesn’t the receiving switch drop the duplicate packet?**

Because:

* Switches are **not** routers
* They do NOT look at IPv6-layer contents
* They do NOT know the concept of “already forwarded"
* They only know: *if multicast → flood*

So a multicast Neighbor Solicitation or Advertisement is treated as:

```
send to all ports except where it came from
```

Even if it's a duplicate.

---

# ✅ **4. Why does the loop cause *infinite* ND packets?**

Two reasons:

### ✔ The original packet loops indefinitely (a true L2 storm)

AND

### ✔ Hosts retransmit NS if they do not get a response

Because the loop prevents replies from arriving.

So:

1. NS floods and loops
2. h2’s NA also loops
3. h1 doesn’t see a valid response, so it **retries** (again multicast)
4. It adds *more* packets to the storm
5. Storm gets worse and worse

---

# ✔ **Bottom line**

Even though switches learn MACs eventually, they **cannot learn stable port mapping when a loop exists**, because the same MAC keeps arriving from different directions.

And because ND uses **multicast**, it is *always* flooded, which is enough to create a loop storm.

Hence:

# **Layer-2 loop = infinite multicast → infinite Neighbor Advertisements / NS packets**

This is why STP exists.

---

If you'd like, I can produce a packet-by-packet timeline illustrating exactly how a single NS spirals into a persistent storm.
