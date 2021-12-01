#!/bin/sh -e

ln -s ~/linbpq /usr/local/bin/linbpq
ln -s /usr/local/bin/linbpq/linbpq.service /etc/systemd/system/linbpq.service
systemctl daemon-reload
systemctl enable linbpq.service
systemctl start linbpq.service
