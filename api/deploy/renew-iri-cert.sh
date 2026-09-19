#!/bin/sh
set -eu
if [ "${RENEWED_LINEAGE:-}" = "/etc/letsencrypt/live/api.iri.today" ]; then
    /usr/sbin/nginx -t
    /bin/systemctl reload nginx
fi
