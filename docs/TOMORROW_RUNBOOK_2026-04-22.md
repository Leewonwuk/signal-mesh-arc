# 내일(2026-04-22) 런북 — 30~60분 안에 데모 영상 완성

> 회사 출근일이라 시간 없음. 이 문서는 **점심시간 30분 또는 퇴근 후 60분에 끝낼 수 있게** 짜인 체크리스트.
> 모든 명령어는 잘라 붙이면 그대로 동작. 실패 시 폴백 명시.
>
> **사전검증 완료 (2026-04-21):** producer→bridge→meta→executor→outcome 전체 HTTP 루프 동작 확인. 남은 건 (1) Circle faucet drip, (2) 온체인 tx 활성화, (3) 영상 녹화.

---

## Phase 0 — 환경 점검 (3분)

```bash
cd /c/Users/user/hackerton/arc
git pull
ls data/v1_3_replay/ | wc -l        # 6 나와야 함 (DOGE/XRP/SOL × USDT/USDC)
node --version                      # v18+ (현재 v24)
python --version                    # 3.11+ (현재 3.13)
```

**문제 시:** `git pull`이 conflict 나면 `git stash; git pull; git stash pop`.

---

## Phase 1 — Circle Faucet Drip (5분)

> 4/22 00:00 UTC 이후 unlock. 한국시간 4/22 09:00.

1. https://console.circle.com 로그인
2. 좌측 메뉴 **Wallets → Wallet Sets → (기존 set)** 진입
3. 4개 지갑 각각 **Faucet → 20 USDC 드립** (아래 주소 확인용):

| Wallet name | Arc testnet address |
|---|---|
| `producer_kimchi`     | `0x7f190347...` |
| `producer_dual_quote` | `0xc3cd155b...` |
| `meta_agent`          | `0xf8f1ae7b...` |
| `executor_agent`      | `0x4d61a397...` |

4. 드립 후 **각 지갑 잔고 ≥ 20 USDC** 확인 (Wallets 페이지 새로고침)

**Sanity check:**
```bash
node scripts/circle_balances.js
# 4개 지갑 모두 balance: "20.0" 출력 확인
```

**문제 시:** faucet quota 또 막히면 → 영상은 데모 모드(paper-only)로 찍고, 1-2건만 진짜 tx 찍어서 Arc Explorer 인서트로 끼워넣기

---

## Phase 2 — 온체인 모드 활성화 (5분)

`.env`에 다음 키 **있는지** 확인 (없으면 추가):

```ini
# 이미 있어야 함:
CIRCLE_API_KEY=...
CIRCLE_ENTITY_SECRET=...

# 온체인 tx 발행에 필요:
EXECUTOR_PRIVATE_KEY=0x...   # executor_agent 지갑의 private key
TREASURY_ADDRESS=0x...       # producer_dual_quote 주소 (수신측)
ARC_RPC_URL=https://rpc.testnet.arc.network

# x402 paywall (선택, 영상에 paywall 보여주려면 ON):
# X402_ENABLED=1
# PRODUCER_WALLET_ADDRESS=0xc3cd155b...
```

> ⚠️ Circle wallet의 private key를 export하는 방법: Circle Console **Wallets → 지갑 클릭 → Export private key** (developer-controlled wallet은 이게 가능). 만약 막히면 별도 EOA를 만들어서 그쪽으로 USDC 1-2개 보내고 사용.

**Sanity check (faucet 후):**
```bash
set -a; source .env; set +a
node scripts/circle_preflight_transfer.js
# 어제는 "PIPELINE_OK — only money missing" 나왔음.
# 오늘 faucet 후엔 HTTP 200 + tx_hash 반환 또는 INSUFFICIENT_FUNDS 사라짐
```

---

## Phase 3 — 데모 실행 (15분)

3개 터미널 또는 tmux/Windows Terminal 분할:

### T1: Bridge
```bash
cd /c/Users/user/hackerton/arc/bridge
npm run dev
# "[bridge] listening on http://localhost:3000" 확인
```

### T2: Dashboard
```bash
cd /c/Users/user/hackerton/arc/dashboard
npm run dev
# 브라우저 http://localhost:5173 자동 열림
```

### T3: 페르소나 설정 + 데모 드라이버

**먼저 페르소나 threshold 낮추기 (필수 — 어제 발견):**
```bash
curl -X POST http://localhost:3000/policy/persona \
  -H "Content-Type: application/json" \
  -d '{"exchangeId":"demo","label":"Demo (relaxed threshold)","feeRoundTrip":0.0005,"thresholdRate":0.0005,"supportsDualQuoteArb":true}'
```

**그 다음 10분 데모:**
```bash
cd /c/Users/user/hackerton/arc
python -m demo.run_demo \
  --symbols DOGE,XRP,SOL \
  --duration 600 \
  --speed 100 \
  --threshold 0.0005 \
  --fee-rate 0
```

**기대 출력 (10분 후):**
- `raw signals: 500` (cap)
- `premium signals: 40-60` (5분에 12개 봤으니 10분에 24개+, 3코인이라 ×3)
- `onchain tx: 60+`  ← **이게 핵심 KPI**
- `allocator ticks: 30` (20s 간격)

**문제 시:**
- `onchain_tx = 0`인데 라이브 onchain ON이면 → executor 로그 확인 (`demo/logs/executor.log`)
- 가장 흔한 원인: `EXECUTOR_PRIVATE_KEY` mismatch / 지갑 잔고 부족
- 폴백: `--no-onchain` 모드로 paper-only 돌리고 Circle Console 별도 캡처

---

## Phase 4 — 증빙 캡처 (10분)

데모가 돌아가는 동안 **이 5개 캡처**:

1. **Dashboard 스크린샷** (브라우저)
   - Tx Stream 카드 — settlement 흐름
   - Allocator Heatmap — Q-table 변화
   - Fee Persona Explorer — 페르소나 스왑 시연 (Bybit ↔ Coinbase 클릭)

2. **Arc Explorer 스크린샷** (https://testnet.arcscan.app)
   - executor 지갑 주소 검색 → 최근 tx 30+개 리스트

3. **Circle Console 스크린샷**
   - Wallets 페이지 — 4지갑 잔고 (변화)
   - Transactions 페이지 — outgoing tx 리스트

4. **Bridge 로그 캡처** (T1 터미널)
   ```bash
   curl -s http://localhost:3000/economics/summary | python -m json.tool > /tmp/final_econ.json
   cat /tmp/final_econ.json
   ```

5. **터미널 데모 출력 전체** (T3에서 셀 셀렉트 → 복사)

---

## Phase 5 — 영상 녹화 (15-20분)

> VIDEO.md의 3분 시나리오. OBS Studio 또는 macOS 화면녹화.

**컷 1 (0:00-0:30) — 콜드 오픈**
- 화면 분할: 좌(Arc) / 우(Base 계산기). 3초 침묵 후 보이스오버:
  *"Every agent economy demo outside Arc has a hidden human re-funding the gas wallet. We don't."*

**컷 2 (0:30-1:15) — Why Arc**
- SUBMISSION.md §3 (Why Arc) 위 3줄을 화면에 띄우면서 설명

**컷 3 (1:15-2:15) — 라이브 데모** (이게 본진)
- 3터미널 + 대시보드 4분할 화면
- T3 카운터가 raw → premium → tx 올라가는 거 보여줌
- Fee Persona Explorer에서 Bybit → Coinbase 클릭 (페르소나 스왑) → 대시보드 demotion 카운터 변화

**컷 4 (2:15-2:45) — 증빙**
- Arc Explorer로 컷 → tx 리스트 → 한 개 클릭해서 USDC 0.005 transfer 보여줌

**컷 5 (2:45-3:00) — 클로징**
- TL;DR 3줄 + GitHub 링크 https://github.com/Leewonwuk/signal-mesh-arc

---

## Phase 6 — 제출 (10분)

1. https://lablab.ai/event/agentic-economy-on-arc 에서 **Submit Project** 클릭
2. 폼에 붙여넣기:
   - **Project name:** Signal Mesh on Arc
   - **One-liner:** SUBMISSION.md §1 복사
   - **Description:** SUBMISSION.md 본문 (전체)
   - **GitHub:** https://github.com/Leewonwuk/signal-mesh-arc
   - **Video:** YouTube 업로드 후 unlisted 링크
   - **Demo:** https://signal-mesh.vercel.app
   - **Cover image:** `docs/cover_image.svg` 업로드

3. **Save Draft** (4/24 dry-run용) → **Submit** (4/25 마감 전)

---

## 비상 폴백 (시간 없을 때)

**제일 간소한 데모 (5분만 있을 때):**
1. Phase 3만 실행 → 영상 OBS로 한 번 길게 녹화 (대시보드 + 터미널)
2. 컷 편집 없이 unlisted YouTube 업로드
3. Phase 6 제출 — 영상이 거칠어도 GitHub 코드+SUBMISSION.md가 본진

**Faucet 또 막힐 때:**
1. Phase 1 스킵
2. 데모는 paper-only (`onchain_tx=0`)로 실행
3. SUBMISSION.md에서 "60+ tx" 클레임 일시 삭제 + "infrastructure validated, faucet-gated" 한 줄 추가
4. pre-flight 결과 (어제 PIPELINE_OK)를 증빙으로 첨부

---

## 어제(2026-04-21) 검증 요약 — 안 다시 할 것들

- ✅ Clean clone 테스트 통과 (`tmp_clone_test/signal-mesh-arc`에서 `pip install` + 임포트 + parquet 로드 + `--help` 모두 OK)
- ✅ Circle pre-flight: PIPELINE_OK (auth/ciphertext/wallet/token 정상)
- ✅ E2E HTTP loop: producer→bridge→meta→executor→outcome 전부 동작
- ✅ Q-learning 프리트레인 로드 OK (updates=3800)
- ✅ 페르소나 핫스왑 즉시 반영
- ✅ GitHub `signal-mesh-arc` 푸블릭 푸시 완료 (3 commits, README 광택, .gitignore 강화)

내일 새로 검증해야 하는 건 **온체인 tx 한 줄과 영상 녹화** 둘뿐.
