#!/usr/bin/env bash
# SignalX — Quick config script
# Usage:
#   /opt/signalx/deploy/scripts/quick-config.sh           # interactive
#   /opt/signalx/deploy/scripts/quick-config.sh preset    # apply Balanced preset only
#   /opt/signalx/deploy/scripts/quick-config.sh close LTC # force-close LTC position
#   /opt/signalx/deploy/scripts/quick-config.sh list      # list open positions
#   /opt/signalx/deploy/scripts/quick-config.sh deploy    # git pull + docker rebuild
#   /opt/signalx/deploy/scripts/quick-config.sh all       # deploy + preset + list

set -e

API=http://localhost:8001/api
EMAIL=ramzimehedhebi@gmail.com
PASSWORD='SignalX2026!'

login() {
    local resp
    resp=$(curl -sf -X POST "$API/auth/login" \
        -H 'Content-Type: application/json' \
        -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}") || {
        echo "❌ Login failed" >&2
        return 1
    }
    echo "$resp" | grep -oE '"token":"[^"]+' | cut -d'"' -f4
}

do_deploy() {
    echo "📦 Git pull..."
    cd /opt/signalx && git pull
    echo "🐳 Rebuild backend..."
    cd /opt/signalx/deploy && docker compose up -d --build backend
    echo "⏳ Wait 12s for startup..."
    sleep 12
    echo "✅ Deploy done"
}

do_preset() {
    local name=${1:-balanced}
    local token
    token=$(login) || exit 1
    echo "🎯 Applying preset: $name"
    local out
    out=$(curl -sf -X POST "$API/bot/preset/$name" -H "Authorization: Bearer $token") || {
        echo "❌ Preset apply failed"
        return 1
    }
    echo "✅ Preset $name applied"
    echo "$out" | grep -oE '"take_profit_pct":[0-9.]+|"stop_loss_pct":[0-9.]+|"max_positions":[0-9]+|"position_size_pct":[0-9.]+' | head -10
}

do_list() {
    local token
    token=$(login) || exit 1
    echo "📂 Open positions:"
    curl -sf "$API/bot/positions" -H "Authorization: Bearer $token" \
        | tr '{' '\n' \
        | grep -oE '"symbol":"[^"]+|"id":"[^"]+|"entry_price":[0-9.e+-]+|"quantity":[0-9.e+-]+' \
        | paste -d '|' - - - - \
        | sed 's/"symbol":"//; s/"id":"//; s/"entry_price"://; s/"quantity"://' \
        | awk -F'|' '{printf "  %-12s  id=%s\n               entry=%s  qty=%s\n", $1, $2, $3, $4}'
}

do_close() {
    local symbol=${1:?Provide symbol like LTC, BTC, ETH...}
    local token
    token=$(login) || exit 1
    local pair="${symbol}USDT"
    echo "🔍 Looking up $pair position..."
    local pid
    pid=$(curl -sf "$API/bot/positions" -H "Authorization: Bearer $token" \
        | grep -B1 -A0 "\"symbol\":\"$pair\"" \
        | grep -oE '"id":"[^"]+' | head -1 | cut -d'"' -f4)
    if [ -z "$pid" ]; then
        # try alternative regex
        pid=$(curl -sf "$API/bot/positions" -H "Authorization: Bearer $token" \
            | tr '{' '\n' | grep "\"symbol\":\"$pair\"" \
            | grep -oE '"id":"[^"]+' | head -1 | cut -d'"' -f4)
    fi
    if [ -z "$pid" ]; then
        echo "❌ No open $pair position found"; return 1
    fi
    echo "🎯 Force-closing $pair  (id=$pid)..."
    curl -sf -X POST "$API/bot/positions/$pid/force-close" \
        -H "Authorization: Bearer $token"
    echo ""
    echo "✅ Closed"
}

do_stats() {
    local token
    token=$(login) || exit 1
    echo "📊 Bot stats:"
    curl -sf "$API/bot/stats" -H "Authorization: Bearer $token" \
        | tr ',' '\n' | sed 's/^[{ ]*//; s/}$//'
}

do_analytics() {
    local token
    token=$(login) || exit 1
    echo "📈 Analytics (full report):"
    docker cp /opt/signalx/backend/tools/botstats.py deploy-backend-1:/tmp/x.py >/dev/null 2>&1 || true
    docker exec deploy-backend-1 python /tmp/x.py
}

CMD=${1:-help}
case "$CMD" in
    deploy)    do_deploy ;;
    preset)    do_preset "${2:-balanced}" ;;
    close)     do_close "$2" ;;
    list)      do_list ;;
    stats)     do_stats ;;
    report)    do_analytics ;;
    all)       do_deploy; do_preset balanced; do_list ;;
    help|*)
        cat <<'EOF'
SignalX — quick management
  deploy           git pull + rebuild backend
  preset [name]    apply preset (conservative | balanced | aggressive)  [def=balanced]
  list             list open positions with their IDs
  close <SYMBOL>   force-close a position by base symbol (LTC, BTC, ETH...)
  stats            show bot stats
  report           full performance report (botstats.py)
  all              deploy + preset balanced + list positions
EOF
        ;;
esac
