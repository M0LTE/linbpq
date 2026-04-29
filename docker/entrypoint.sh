#!/bin/sh
# linbpq Docker entrypoint.
#
# Refreshes /data/HTML from the image (version markers must match the
# binary or the BBS/Mail pages 404), checks for /data/bpq32.cfg, then
# execs linbpq from /data so cwd-relative state (BPQNODES.dat,
# logs/, *.mes files, etc.) lands inside the volume.
#
# Usage:
#   docker run --rm -it \
#       -v "$PWD/mybpq:/data" \
#       -p 8008:8008 -p 8010:8010 \
#       <image>:latest
#
# Pass extra linbpq arguments at the end (e.g. ``mail chat`` to
# enable the BBS / Chat subsystems — only when your cfg registers
# BBSCALL / CHATCALL).  By default no subsystems are started, so
# AGW application slots stay free for APPLn registrations.

set -e

# Sync HTML/ templates from the image.  ``cp -rf`` overwrites
# files that exist in /data/HTML so the templates stay in lock-step
# with the binary; user state files elsewhere in /data are
# untouched.
if [ -d /opt/linbpq/HTML ]; then
    cp -rf /opt/linbpq/HTML /data/
fi

cd /data

if [ ! -f bpq32.cfg ]; then
    cat >&2 <<'EOF'
ERROR: /data/bpq32.cfg not found.

Mount a host directory containing your bpq32.cfg as /data, e.g.:

    docker run --rm -it \
        -v "$PWD/mybpq:/data" \
        -p 8008:8008 -p 8010:8010 \
        <image>:latest

A starter config ships at /opt/linbpq/bpq32.cfg.example — copy it
into your mounted dir and edit it for your callsign / locator:

    cp /opt/linbpq/bpq32.cfg.example /data/bpq32.cfg
EOF
    exit 1
fi

exec linbpq "$@"
