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
sudo apt install git build-essential libminiupnpc-dev libconfig-dev libpcap-dev
```

## Fetch
```
cd ~
git clone https://github.com/M0LTE/linbpq.git
```

## Build
```
cd linbpq
make
```
... yep, that's it

# Post-build
```
chmod +x linbpq
sudo setcap "CAP_NET_ADMIN=ep CAP_NET_RAW=ep CAP_NET_BIND_SERVICE=ep" linbpq
cp chatconfig.cfg.sample chatconfig.cfg
cp linmail.cfg.sample linmail.cfg
cp bpq32.cfg.sample bpq32.cfg
```

edit bpq32.cfg, chatconfig.cfg and linmail.cfg to suit
run with `./linbpq`

# Startup
Here's how I'm trying out handling startup at boot:
```
sudo ln -s ~/linbpq /usr/local/bin/linbpq
sudo ln -s /usr/local/bin/linbpq/linbpq.service /etc/systemd/system/linbpq.service
sudo systemctl daemon-reload
sudo systemctl enable linbpq.service
sudo systemctl start linbpq.service
```

or

```
chmod +x install.sh
sudo -s ./install.sh
```
