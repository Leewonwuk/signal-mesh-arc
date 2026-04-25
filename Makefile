# AlphaLoop — one-command judge happy path
# Inspired by Judy's hackathon-trading-agent `make verify` pattern.
#
# Usage (from repo root):
#   make help     — list targets
#   make verify   — recompute Merkle root over docs/evidence/batch_tx_hashes.txt
#                   and compare to docs/evidence/merkle_root.txt
#   make merkle   — recompute and publish merkle_root.txt from the evidence file
#   make bridge   — start the bridge dev server (localhost:3000)
#   make dashboard — start the dashboard dev server (localhost:5173)
#   make demo     — launch the full demo driver (producers + meta + executor + allocator)
#   make batch    — fire 150 variably-priced USDC settlements on Arc testnet

.PHONY: help verify merkle bridge dashboard demo batch persona-demo persona-bybit pre-record

help:
	@echo "AlphaLoop Make targets:"
	@echo "  make verify     - verify Merkle root of 150-tx evidence manifest"
	@echo "  make merkle     - rebuild Merkle root and write merkle_root.txt"
	@echo "  make bridge     - start bridge dev server (localhost:3000)"
	@echo "  make dashboard  - start dashboard dev server (localhost:5173)"
	@echo "  make demo       - start demo driver (producers + meta + executor + allocator)"
	@echo "  make batch      - fire 150 variably-priced USDC tx on Arc testnet"
	@echo "  make persona-demo - set bridge persona to Demo (warmup)"
	@echo "  make persona-bybit - set bridge persona to Bybit (recording-ready)"
	@echo "  make pre-record - run pre_record_check.sh gate"

verify:
	python scripts/build_merkle_root.py --verify

merkle:
	python scripts/build_merkle_root.py

bridge:
	cd bridge && npm run dev

dashboard:
	cd dashboard && npm run dev

demo:
	python -m demo.run_demo --symbols DOGE,XRP,SOL --duration 900 --speed 100 --threshold 0.0005 --fee-rate 0

batch:
	node scripts/circle_batch_settle.js --count 150 --rate 3

persona-demo:
	curl -X POST http://localhost:3000/policy/persona \
	  -H 'Content-Type: application/json; charset=utf-8' \
	  --data-binary '{"exchangeId":"demo","label":"Demo - relaxed threshold","feeRoundTrip":0.0005,"thresholdRate":0.0005,"supportsDualQuoteArb":true}'

persona-bybit:
	curl -X POST http://localhost:3000/policy/persona \
	  -H 'Content-Type: application/json; charset=utf-8' \
	  --data-binary '{"exchangeId":"bybit","label":"Bybit - VIP 0 + USDC 50% off","feeRoundTrip":0.0015,"thresholdRate":0.0017,"supportsDualQuoteArb":true}'

pre-record:
	bash scripts/pre_record_check.sh
