#!/usr/bin/env bash
# SignalX — Quick config script
# Usage:
#   /opt/signalx/deploy/scripts/quick-config.sh           # interactive
#   /opt/signalx/deploy/scripts/quick-config.sh preset    # apply Balanced preset only
#   /opt/signalx/deploy/scripts/quick-config.sh close LTC # force-close LTC position
#   /opt/signalx/deploy/scripts/quick-config.sh list      # list open positions
#   /opt/signalx/deploy/scripts/quick-config.sh deploy    # git pull + docker rebuild
#   /opt/signalx/deploy/scripts/quick-config.sh all       # deploy + preset + list

# Disable history expansion so '!' in passwords does not break
set +H 2>/dev/null || true
set -e

API=http://localhost/api
EMAIL=${SIGNALX_EMAIL:-ramzimehedhebi@gmail.com}
# Read password from env or prompt
if [ -z "${SIGNALX_PASSWORD:-}" ]; then
    # default fallback
    SIGNALX_PASSWORD='SignalX2026!'
fi
PASSWORD="$SIGNALX_PASSWORD"

login() {
    # Build JSON body via python to safely escape the password
    local body
    body=$(python3 -c "import json,os; print(json.dumps({'email': os.environ['E'], 'password': os.environ['P']}))" 2>/dev/null) \
        || body="{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}"
    local resp http
    resp=$(E="$EMAIL" P="$PASSWORD" curl -sS -w "\n__HTTP__%{http_code}" -X POST "$API/auth/login" \
        -H 'Content-Type: application/json' \
        -d "$body")
    http=$(echo "$resp" | grep -oE '__HTTP__[0-9]+' | tail -1 | sed 's/__HTTP__//')
    resp=$(echo "$resp" | sed 's/__HTTP__[0-9]*$//')
    if [ "$http" != "200" ]; then
        echo "❌ Login HTTP=$http  resp=$resp" >&2
        return 1
    fi
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
    reset-password)
        NEW_PWD=${2:-Trading2026}
        echo "🔑 Resetting password for $EMAIL to: $NEW_PWD"
        # 1. Generate hash inside backend container (uses prod bcrypt)
        HASH=$(docker exec deploy-backend-1 python -c "import bcrypt; print(bcrypt.hashpw(b'$NEW_PWD', bcrypt.gensalt()).decode())")
        if [ -z "$HASH" ]; then echo "❌ Hash generation failed"; exit 1; fi
        echo "Hash: $HASH"
        # 2. Update Mongo (signalx DB)
        docker exec deploy-mongo-1 mongosh --quiet --eval \
            "db=db.getSiblingDB('signalx'); print(JSON.stringify(db.users.updateOne({email:'$EMAIL'},{\$set:{password:'$HASH'}})))"
        # 3. Test login
        echo ""
        echo "🧪 Testing login..."
        BODY="{\"email\":\"$EMAIL\",\"password\":\"$NEW_PWD\"}"
        HTTP=$(curl -s -o /tmp/login.json -w "%{http_code}" -X POST "$API/auth/login" \
            -H 'Content-Type: application/json' -d "$BODY")
        if [ "$HTTP" = "200" ]; then
            echo "✅ Login OK (HTTP 200)"
            echo "Password is now: $NEW_PWD"
            echo "You can connect to http://178.104.105.112 with $EMAIL / $NEW_PWD"
        else
            echo "❌ Login FAILED (HTTP $HTTP)"
            cat /tmp/login.json
        fi
        ;;
    all)       do_deploy; do_preset balanced; do_list ;;
    help|*)
        cat <<'EOF'
SignalX — quick management
  deploy                git pull + rebuild backend
  preset [name]         apply preset (conservative | balanced | aggressive)  [def=balanced]
  list                  list open positions with their IDs
  close <SYMBOL>        force-close a position by base symbol (LTC, BTC, ETH...)
  stats                 show bot stats
  report                full performance report (botstats.py)
  reset-password [pwd]  reset password (default: Trading2026)
  all                   deploy + preset balanced + list positions
EOF
        ;;
esac
