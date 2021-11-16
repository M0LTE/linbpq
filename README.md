# Description
Linbpq doesn't seem to live in source control, so I've gone and found all the
source packages I can and committed them in order.

I also wanted to build it on Linux, and there were case mismatches. Changes to the
source made by me are recorded below, otherwise everything is from John Wiseman.

# Changes
- resolve casing error in tncinfo.h (6e1d9ed)

# Build instructions

## System

Ubuntu Server 20.04.3 LTS 64 bit  
Raspberry Pi 3B

## Dependencies

```
sudo apt install libminiupnpc-dev libconfig-dev libpcap-dev
```

## Build
```
make
```
... yep, that's it

# Post-build
```
sudo setcap "CAP_NET_ADMIN=ep CAP_NET_RAW=ep CAP_NET_BIND_SERVICE=ep" linbpq
chmod +x linbpq
```

edit linbpq.cfg and chatconfig.cfg to suit
run with `./linbpq`
