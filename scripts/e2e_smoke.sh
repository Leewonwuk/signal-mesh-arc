#!/usr/bin/env bash
# E2E smoke — fire after F3 (online allocator consumer) lands.
# Assumes bridge :3000 and dashboard :5173 already running via `npm run dev`.
set -u
BRIDGE=${BRIDGE_URL:-http://localhost:3000}
DASHBOARD=${DASHBOARD_URL:-http://localhost:5173}
PASS=0; FAIL=0
ok()  { echo "  [PASS] $1"; PASS=$((PASS+1)); }
bad() { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }

echo "=== 1. infra health ==="
curl -sf $BRIDGE/health >/dev/null && ok "bridge /health" || bad "bridge /health"
curl -sf $DASHBOARD/ >/dev/null       && ok "dashboard /"     || bad "dashboard /"

echo "=== 2. allocator pretrain artifact ==="
python -c "import json,sys; d=json.load(open('consumers/capital_allocator/allocator_q.json')); \
  assert all(k in d for k in ['q_table','visit_counts','reward_stats','calibration']); \
  assert len(d['q_table'])==9 and len(d['q_table'][0])==7; \
  print(' q_table 9x7 OK, f_alloc_6_gate=', d.get('f_alloc_6_gate'))" \
  && ok "allocator_q.json schema" || bad "allocator_q.json schema"

echo "=== 3. regime encoder ==="
python -c "from ml.regime_features import state_index, STATE_LABELS; \
  s=state_index(0.04,0.00015,0.006,0.0009); \
  assert 0<=s<=8; \
  print(' state=',s,STATE_LABELS[s])" \
  && ok "regime_features.state_index" || bad "regime_features.state_index"

echo "=== 4. allocator consumer live (expect 1+ POST /allocation within 40s) ==="
TS_BEFORE=$(curl -s "$BRIDGE/allocation/history?limit=500" | python -c "import json,sys; print(json.load(sys.stdin).get('count',0))")
timeout 40 python -m consumers.capital_allocator.main --allocator-tick-seconds 10 --v3-entry-offset-sec 0 --verbose >/tmp/alloc.log 2>&1 &
ALLOC_PID=$!
sleep 35
TS_AFTER=$(curl -s "$BRIDGE/allocation/history?limit=500" | python -c "import json,sys; print(json.load(sys.stdin).get('count',0))")
kill $ALLOC_PID 2>/dev/null || true
if [ "$TS_AFTER" -gt "$TS_BEFORE" ]; then
  ok "allocator posted $((TS_AFTER-TS_BEFORE)) new allocation(s)"
else
  bad "no new allocations appended (before=$TS_BEFORE, after=$TS_AFTER)"
  tail -30 /tmp/alloc.log
fi

echo "=== 5. payload §7.2 enrichment ==="
python - <<'PY' || bad "§7.2 enrichment"
import json, urllib.request
r = json.load(urllib.request.urlopen("http://localhost:3000/allocation"))
required = ["tick_id","state_idx","action_idx","action_label","weights","q_values"]
missing = [k for k in required if r.get(k) is None]
assert not missing, f"missing {missing}"
# Enrichments — optional but at least one should be present after F3 lands
enriched = [k for k in ["v3_entry_offset_sec","q_value_second_best","regime_features","cadence_seconds","allocation_frozen"] if k in r]
print(f" required OK, enriched fields present: {enriched}")
PY
[ $? -eq 0 ] && ok "payload §7.2"

echo "=== 6. dashboard proxy ==="
curl -sf "$DASHBOARD/api/allocation" | head -c 200 >/dev/null && ok "dashboard → /api/allocation proxy" || bad "dashboard proxy"

echo ""
echo "==== SUMMARY: $PASS pass / $FAIL fail ===="
exit $FAIL
