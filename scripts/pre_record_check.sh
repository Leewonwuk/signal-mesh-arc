#!/usr/bin/env bash
# pre_record_check.sh — 녹화 직전 10초 체크. 실패하면 녹화 시작 금지.
#
# 사용:
#   bash scripts/pre_record_check.sh
#
# 통과 조건:
#   1. 브리지 /health 200
#   2. 대시보드 :5173 200
#   3. 페르소나 thresholdRate <= 0.001 (demo 모드)
#   4. 최근 60초 내 premium signal >= 1
#
# 실패 시 어떤 컴포넌트가 죽었는지 print.

set -u
BRIDGE="${ARC_BRIDGE_URL:-http://localhost:3000}"
DASH="${ARC_DASHBOARD_URL:-http://localhost:5173}"
FAIL=0

echo "[1/4] bridge health..."
if curl -sf "$BRIDGE/health" >/dev/null; then
    curl -s "$BRIDGE/health"; echo
else
    echo "  ❌ bridge down — cd bridge && npm run dev"
    FAIL=1
fi

echo "[2/4] dashboard..."
if curl -sf -o /dev/null -w "  http=%{http_code}\n" "$DASH"; then
    :
else
    echo "  ❌ dashboard down — cd dashboard && npm run dev"
    FAIL=1
fi

echo "[3/4] persona threshold..."
PERSONA=$(curl -s "$BRIDGE/policy/persona")
THRESH=$(echo "$PERSONA" | python -c "import json,sys;print(json.load(sys.stdin)['active'].get('thresholdRate',1))" 2>/dev/null)
if [ -z "$THRESH" ]; then
    echo "  ❌ persona not set"
    FAIL=1
elif python -c "import sys;sys.exit(0 if $THRESH <= 0.001 else 1)"; then
    echo "  ✅ thresholdRate=$THRESH"
else
    echo "  ⚠️  thresholdRate=$THRESH too strict — will block premium signals"
    echo "     fix:"
    echo "     curl -X POST $BRIDGE/policy/persona -H 'Content-Type: application/json' \\"
    echo "       -d '{\"exchangeId\":\"demo\",\"label\":\"Demo (relaxed threshold)\",\"feeRoundTrip\":0.0005,\"thresholdRate\":0.0005,\"supportsDualQuoteArb\":true}'"
    FAIL=1
fi

echo "[4/4] signal flow..."
PREMIUM=$(curl -s "$BRIDGE/health" | python -c "import json,sys;print(json.load(sys.stdin)['signals']['premium'])" 2>/dev/null)
if [ -n "$PREMIUM" ] && [ "$PREMIUM" -ge 1 ]; then
    echo "  ✅ premium count = $PREMIUM"
else
    echo "  ⚠️  premium=0. producer가 안 돌거나 threshold 너무 높음"
    echo "     fix: 데모 드라이버를 먼저 돌린 뒤 다시 체크 — python -m demo.run_demo --symbols DOGE --duration 60 --threshold 0.0005 --fee-rate 0"
    FAIL=1
fi

echo
if [ $FAIL -eq 0 ]; then
    echo "✅ ALL CHECKS PASSED — 녹화 OK"
    exit 0
else
    echo "❌ 일부 체크 실패 — 녹화 시작 금지"
    exit 1
fi
