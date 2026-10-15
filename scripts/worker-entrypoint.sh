#!/bin/sh
set -eu
if [ -r /opt/lead-hunter/proxy-ca.pem ]; then
  cat /etc/ssl/certs/ca-certificates.crt /opt/lead-hunter/proxy-ca.pem > /tmp/lh-ca-bundle.pem
  export SSL_CERT_FILE=/tmp/lh-ca-bundle.pem
  export REQUESTS_CA_BUNDLE=/tmp/lh-ca-bundle.pem
fi
exec "$@"
