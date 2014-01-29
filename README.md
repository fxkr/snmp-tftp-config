Download configs from Cisco devices via SNMP and TFTP

Author: Felix Kaiser <felix.kaiser@fxkr.net>
License: revised BSD (see LICENSE)
Dependencies:
- pyyaml (for configuration)
- gevent (for the tftp server)
- pysnmp (to start transfers)

### Why?
Why not?

### Caveats
- Only partially protocol compliant. It works(TM).
- You need to be able to bind to port 69. Again, blame Cisco.
- An attacker that can sniff traffic can intercept the SNMP credentials.
  Mitigation: use SNMPv3 with AUTH/PRIV
- A man in the middle can read/modify the config sent to the script.
  Mitigation: none, sorry. Blame Cisco. ;-)

### Future plans
I'll never get to these.
- support SNMPv3
- Full TFTP protocol compliance. Standards are important.
- Become better than Rancid.

