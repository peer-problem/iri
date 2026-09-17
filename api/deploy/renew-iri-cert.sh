#!/bin/sh
set -eu
if [ "${RENEWED_LINEAGE:-}" = "/etc/letsencrypt/live/iri.5.104.87.93.sslip.io" ]; then
    /usr/sbin/nginx -t
    /bin/systemctl reload nginx
fi
