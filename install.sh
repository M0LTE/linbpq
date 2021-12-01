#!/bin/sh -e

systemctl stop linbpq || true
systemctl disable linbpq || true

rm -f /usr/local/bin/linbpq
ln -s ~/linbpq /usr/local/bin/linbpq

ln -s /usr/local/bin/linbpq/linbpq.service /etc/systemd/system/linbpq.service
systemctl daemon-reload
systemctl enable linbpq.service
systemctl start linbpq.service
