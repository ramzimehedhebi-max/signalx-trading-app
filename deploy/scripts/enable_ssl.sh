#!/bin/bash
# Enable HTTPS via Let's Encrypt for SignalX
# Usage: sudo bash deploy/scripts/enable_ssl.sh signalx.your-domain.com [email@you.com]

set -euo pipefail
DOMAIN="${1:-}"
EMAIL="${2:-admin@$DOMAIN}"

if [ -z "$DOMAIN" ]; then
  echo "Usage: $0 <domain> [email]"
  exit 1
fi

cd "$(dirname "$0")/.."

# Initial bootstrap with HTTP only (already running)
echo "→ Requesting Let's Encrypt certificate for $DOMAIN..."
docker compose run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    --email $EMAIL --agree-tos --no-eff-email --force-renewal \
    -d $DOMAIN" certbot

# Replace HTTP-only nginx config with HTTPS version
sed -i "s|# server {|server {|g; s|server_name signalx.YOUR_DOMAIN.com|server_name $DOMAIN|g; s|/etc/letsencrypt/live/signalx.YOUR_DOMAIN.com|/etc/letsencrypt/live/$DOMAIN|g" nginx/signalx.conf

docker compose restart nginx
echo "✅ HTTPS enabled. Test: https://$DOMAIN/api/health"
