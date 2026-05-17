#!/bin/bash
# SignalX — One-shot deploy script for Hetzner VPS
# Usage:  curl -fsSL https://raw.githubusercontent.com/YOU/signalx/main/deploy/scripts/deploy.sh | sudo bash
# Or:     git clone ...; cd signalx; sudo bash deploy/scripts/deploy.sh

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +%H:%M:%S)] $1${NC}"; }
warn() { echo -e "${YELLOW}[WARN] $1${NC}"; }
error() { echo -e "${RED}[ERROR] $1${NC}" >&2; exit 1; }

# ----- 1) Pre-flight checks -----
if [ "$EUID" -ne 0 ]; then error "Run as root: sudo bash $0"; fi
if [ ! -f "deploy/docker-compose.yml" ]; then
  error "Run from project root: cd /opt/signalx && sudo bash deploy/scripts/deploy.sh"
fi

log "✔ Running as root"
log "✔ Found deploy/docker-compose.yml"

# ----- 2) Install Docker if missing -----
if ! command -v docker >/dev/null 2>&1; then
  log "Installing Docker..."
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  log "✔ Docker installed"
else
  log "✔ Docker already installed"
fi

# ----- 3) Check .env -----
if [ ! -f "deploy/.env" ]; then
  warn ".env not found. Copying from .env.example..."
  cp deploy/.env.example deploy/.env
  warn "⚠️  EDIT deploy/.env BEFORE CONTINUING. Press ENTER when done..."
  read -r
fi

# Source .env to expose vars
set -a; . deploy/.env; set +a

# ----- 4) Build & start containers -----
cd deploy
log "Building containers (frontend bundle takes ~3-5 min on CX22)..."
docker compose build --pull

log "Starting all services..."
docker compose up -d

log "Waiting for backend health (max 90s)..."
for i in $(seq 1 30); do
  if curl -fsS http://localhost/api/health >/dev/null 2>&1; then
    log "✔ Backend healthy"
    break
  fi
  sleep 3
  echo -n "."
done
echo

# ----- 5) Status -----
echo
log "============================================="
log "🎉 SignalX is now LIVE on this server!"
log "============================================="
echo
log "Try these URLs:"
log "  Health  : http://$(curl -s ifconfig.me)/api/health"
log "  Frontend: http://$(curl -s ifconfig.me)/"
echo
log "To get HTTPS (recommended), point your domain to this IP and run:"
log "  sudo bash deploy/scripts/enable_ssl.sh signalx.YOUR_DOMAIN.com"
echo
log "Logs: docker compose -f deploy/docker-compose.yml logs -f backend"
log "Stop: docker compose -f deploy/docker-compose.yml down"
