# Arc 해커톤 진행상황 & TODO — 2026-04-24 (금)

> **현재 위치:** lablab.ai *Agentic Economy on Arc* 해커톤 / 프로젝트 *Signal Mesh on Arc* (solo, Leewonwuk)
> **오늘은 Draft Save 드라이런 데이**. 내일(2026-04-25)이 **실제 제출 마감**.
> 이 문서 하나로 "어디까지 왔고 · 지금 뭐 해야 하고 · 내일 뭐 해야 하는지" 즉시 파악되도록 압축.

---

## 0. 30초 현황 브리핑

| 항목 | 상태 |
|---|---|
| **GitHub repo 공개** | ✅ https://github.com/Leewonwuk/signal-mesh-arc |
| **Clean clone 검증** | ✅ 4/21 tmp_clone_test에서 import · parquet 로드 · `--help` 통과 |
| **E2E HTTP 루프** | ✅ producer→bridge→meta→executor→outcome 전 구간 4/21 검증 |
| **Circle pre-flight** | ✅ `PIPELINE_OK — only money missing` (4/21) |
| **SUBMISSION.md** | ✅ §1~§12 + 11.b 헤드라인 백테스트 (`p=0.49` vs ALL_V2 tie) 완성 + **4/24 정직성 패치 3건** (§1 AlphaLoop rename, §5 ERC-8004 row, §7 가격공식 정직화, §8 4번째 bullet) |
| **AlphaLoop 리네이밍** | 🟡 SUBMISSION 완료 / 덱·대시보드는 Claude Design 핸드오프 (아래 §2.5 참조) |
| **코드-문서 정합성** | ✅ `capital_allocator/main.py` reward Sutton dollar-only로 B2 수정 (Round 2 정합) |
| **SLIDES.pdf** | ✅ Marp 렌더 완료 (`docs/SLIDES.pdf`) |
| **RECORDING_GUIDE_KR.md** | ✅ S1~S5 씬 + 컷별 보이스오버 스크립트 |
| **폴백 B-roll** | ✅ `docs/evidence/` 13개 JSON + README |
| **프리컴파일 체크** | ✅ `scripts/pre_record_check.sh` |
| **Vercel 대시보드** | ✅ https://signal-mesh.vercel.app |
| **Circle faucet drip** | ❌ **오늘 아침 9시 KST 이후 unlock — 해야 함** |
| **온체인 tx 실행** | ❌ faucet 이후 `circle_preflight_transfer.js` 재실행 |
| **영상 녹화** | ❌ 오늘 or 내일 |
| **YouTube Unlisted 업로드** | ❌ 녹화 후 |
| **lablab Draft Save** | ❌ **오늘 dry-run** |
| **lablab Final Submit** | ❌ **내일(4/25)** |

**결론: 코드·문서·증빙은 다 준비됨. 남은 건 (1) 돈 넣고 (2) 영상 찍고 (3) 제출 폼 입력.**

---

## 1. 타임라인 — 어디까지 왔고 어디로 가나

```
4/21 (화) ┃ 기초공사 끝
          ┃  ├─ repo public push · README 광택
          ┃  ├─ Clean clone 검증
          ┃  ├─ E2E HTTP 루프 검증
          ┃  ├─ Circle pre-flight PIPELINE_OK
          ┃  ├─ 페르소나 threshold 버그 발견 (demo threshold=0.0005)
          ┃  ├─ Q 프리트레인 로드 updates=3800
          ┃  └─ 11.b 워크포워드 백테스트 (Round 2) — ALL_V2 tie p=0.49, DIVERSIFY win p=0.012
          ┃
4/22 (수) ┃ 프리컴파일 폴리싱
          ┃  ├─ SLIDES.pdf Marp 렌더
          ┃  ├─ docs/evidence/ 13개 JSON 덤프 + README
          ┃  ├─ scripts/pre_record_check.sh
          ┃  ├─ RECORDING_GUIDE_KR.md — OBS 5씬 + 컷별 대본
          ┃  └─ TODO_2026-04-22.md — 핸드폰용 원페이지
          ┃
4/23 (목) ┃ (로그 없음 — 회사 출근일)
          ┃
4/24 (금) ┃ 🎯 오늘 — Draft Save dry-run
          ┃  ├─ 아침: Circle faucet drip × 4 지갑
          ┃  ├─ 저녁: 온체인 tx 활성화 + 영상 녹화 + YouTube 업로드
          ┃  └─ lablab 폼 **Save Draft** (아직 Submit 아님)
          ┃
4/25 (토) ┃ 🚨 마감일 — Final Submit
          ┃  └─ Draft 재확인 → Submit
```

---

## 2. 완료 체크리스트 (do not redo)

### 2.1 코드·아키텍처
- [x] `bridge/` — Node.js + x402 paywall + EIP-3009 `transferWithAuthorization`
- [x] `producers/` — v1 kimchi · v2 dual-quote · v3 funding (strategy_tag emit)
- [x] `consumers/meta_agent/` — Gemini 2.5 Flash + GBM regime classifier
- [x] `consumers/executor_agent/` — 페이퍼 포지션 + variable-price settle + UCB1 Q-table
- [x] `consumers/capital_allocator/` — 9×7 tabular Q-learning, 8h cadence
- [x] `dashboard/` — React + Vite, Tx Stream · Allocator Heatmap · Fee Persona Explorer
- [x] `demo/run_demo.py` — 3코인 10분 런너, `--speed 100` 가속 지원

### 2.2 증빙·백테스트
- [x] `scripts/backtest_rules_v2.py` — rules baselines
- [x] `scripts/backtest_ml.py` — Ridge/LightGBM comparators
- [x] `scripts/backtest_allocator.py` — walk-forward 47-tick 홀드아웃
- [x] 결과: TrainedQ \$7.61 / Sharpe 2.89 / 83% win / `p=0.012` vs DIVERSIFY / `p=0.49` vs ALL_V2 (tie)
- [x] Round 1 → Round 2 Sutton-school 감사 기록 (SUBMISSION §11.b.1)
- [x] `docs/BACKTEST_REPORT.md` + `docs/BACKTEST_ML_REPORT.md` + `docs/BACKTEST_RULES_V2_REPORT.md`
- [x] `docs/ALLOCATOR_RL_DESIGN.md` — state/action/reward + F-ALLOC-1~7 pre-mortem
- [x] `docs/GIANTS_SHOULDERS_ALLOCATOR_REVIEW.md`

### 2.3 제출 자산
- [x] `docs/SUBMISSION.md` — §1 one-liner · §3 Why Arc · §5 Circle products · §10 pricing · §11 Allocator RL · §11.b 백테스트 · §12 로드맵
- [x] `docs/PRODUCT_FEEDBACK.md` — \$500 bonus용 정직한 DX 피드백
- [x] `docs/VIDEO.md` — 3분 영어 보이스오버 스크립트
- [x] `docs/RECORDING_GUIDE_KR.md` — OBS 운영 한국어 가이드
- [x] `docs/SLIDES.md` + `docs/SLIDES.pdf` — Marp 렌더
- [x] `docs/cover_image.svg`
- [x] `docs/evidence/` — 폴백 B-roll 13개 JSON
- [x] `docs/TRACK_AND_STACK.md` · `docs/ARCHITECTURE.md`

### 2.4 검증 환경
- [x] Clean clone 테스트 (`tmp_clone_test/signal-mesh-arc` pip install → import → --help)
- [x] E2E HTTP loop
- [x] `node scripts/circle_preflight_transfer.js` → PIPELINE_OK
- [x] `node scripts/circle_balances.js` — 4 wallet 주소 확인
- [x] `scripts/pre_record_check.sh` — 4개 ✅ 자동 체크

### 2.5 4/24 정직성 패치 & 핸드오프 (오늘 오전 완료)

**코드 수정**:
- [x] `consumers/capital_allocator/main.py:390-407` — `compute_reward` z-blend → **Sutton dollar-only** 교체. Round 2 감사 결과(SUBMISSION §11.b.1)와 코드 정합. reward-hacking 트랩 제거.

**SUBMISSION.md 수정** (3건):
- [x] §1 헤더 — `Signal Mesh on Arc — Submission` → `AlphaLoop on Arc — Submission`. **Naming note** 블록 추가(레포명 `signal-mesh-arc` 불변 명시).
- [x] §5 Circle products 표 — **Developer-Controlled Wallets** row + **ERC-8004 on-chain agent identity** row(`AlphaLoopAgentRegistry` 0xb276…b7ab) 2줄 추가.
- [x] §7 가격공식 — `price = clip(confidence × notional × |premium| × take_rate, ...)` **overclaim 제거** → `price = clip(fee_base × Q_mult, $0.0005, $0.01)` 로 코드(`pricing_policy.py:217`) 정합화. confidence가 reliability에만 쓰이고 가격 공식엔 없음을 명시.
- [x] §8 Originality — 4번째 bullet로 **ERC-8004 content-hashed producer lineage** 추가. 기존 3개 bullet의 "closed outcome loop"와 ERC-8004를 병렬로 각각 key 포인트로 승격.

**Claude Design 핸드오프 MD 2건 작성** (HTML/TSX는 Claude Design이 실제 편집):
- [x] [`arc해커톤_대시보드수정방향_260424.md`](docs/arc해커톤_대시보드수정방향_260424.md) — App.tsx 헤더 리네이밍 + 6-메트릭 hero ribbon + ProvenanceBar 신규 컴포넌트 diff 포함.
- [x] [`arc해커톤_덱수정방향_260424.md`](docs/arc해커톤_덱수정방향_260424.md) — 슬라이드 6 가격공식 정직화 + CSS orphan block(line 155-160) 해결 + footer 날짜 동기화(4/25 vs 4/26).

---

## 3. 오늘(4/24) TODO — Draft Save Dry-Run

### 3.1 ☀️ 아침 (09:00 KST 이후, 5분) — 반드시 가장 먼저

- [ ] **Circle Console faucet drip × 4 wallets** (00:00 UTC unlock = 09:00 KST)
  - https://console.circle.com → Wallets → Wallet Sets
  - `producer_kimchi` (`0x7f190347...`)
  - `producer_dual_quote` (`0xc3cd155b...`)
  - `meta_agent` (`0xf8f1ae7b...`)
  - `executor_agent` (`0x4d61a397...`)
  - 각각 **20 USDC** drip
- [ ] `node scripts/circle_balances.js` → 4개 전부 `balance: "20.0"` 확인
- [ ] **실패 시 폴백:** faucet quota 막히면 → paper-only 데모 + `docs/evidence/` B-roll

### 3.2 🕛 점심 or 🌙 저녁 (60분 블록)

#### Step 1 — 환경 기동 (3분)
- [ ] T1: `cd bridge && npm run dev` → "[bridge] listening on :3000" 확인
- [ ] T2: `cd dashboard && npm run dev` → 브라우저 http://localhost:5173 자동
- [ ] T3: `.env`에 `EXECUTOR_PRIVATE_KEY` + `TREASURY_ADDRESS` + `ARC_RPC_URL` 확인

#### Step 2 — 프리컴파일 체크 (30초)
- [ ] `bash scripts/pre_record_check.sh` → 4개 ✅
- [ ] 실패 항목 하나라도 있으면 → 원인 fix 후 재실행

#### Step 3 — 온체인 드라이런 (7분)
- [ ] `set -a; source .env; set +a`
- [ ] `node scripts/circle_preflight_transfer.js`
- [ ] 기대: HTTP 200 + tx_hash 반환, 또는 `INSUFFICIENT_FUNDS` 사라짐
- [ ] tx_hash를 https://testnet.arcscan.app 에서 조회 → ✅ Confirmed 확인
- [ ] 폴백: EXECUTOR_PRIVATE_KEY export 안 되면 별도 EOA 만들어 USDC 1-2개 송금 후 사용

#### Step 4 — 페르소나 세팅 (30초, 필수)
- [ ] ```bash
      curl -X POST http://localhost:3000/policy/persona \
        -H "Content-Type: application/json" \
        -d '{"exchangeId":"demo","label":"Demo (relaxed threshold)","feeRoundTrip":0.0005,"thresholdRate":0.0005,"supportsDualQuoteArb":true}'
      ```

#### Step 5 — 웜업 런 (15분, 녹화 전 premium 캐시 확보)
- [ ] `python -m demo.run_demo --symbols DOGE,XRP,SOL --duration 900 --speed 100 --threshold 0.0005 --fee-rate 0`
- [ ] 기대: raw 500 / premium **20-40** / onchain_tx **60+** / allocator_ticks 30+
- [ ] premium이 10 이하면 → threshold 0.0001로 낮추거나 duration을 1800으로 연장

#### Step 6 — 영상 녹화 (20분)
- [ ] OBS 5씬 (S1 콜드오픈 · S2 슬라이드 · S3 라이브 · S4 Arc Explorer · S5 클로징) 셋업
- [ ] 마이크 테스트: "신호 메시 온 아크" 명료한지 한 번 듣고
- [ ] 본 녹화 3분 — `RECORDING_GUIDE_KR.md` 컷별 대본 그대로
- [ ] 실패 시 2회까지 재시도, 그 이상이면 OBS 대신 Xbox Game Bar(`Win+G`)로 한 방 녹화
- [ ] Circle Console → Send USDC 별도 60초 영상 (Transaction Flow 증빙)

#### Step 7 — 편집·업로드 (10분)
- [ ] DaVinci Resolve or iMovie — 3분 정확히 맞추기 (초과 시 lablab 자동 컷)
- [ ] YouTube **Unlisted** 업로드 (Public 아님!)
- [ ] 제목: `Signal Mesh on Arc — Lablab Hackathon Submission`
- [ ] 설명에 GitHub URL + dashboard URL 포함

#### Step 8 — lablab 폼 **Save Draft** (10분, 아직 Submit 아님)
- [ ] https://lablab.ai/event/agentic-economy-on-arc → Submit Project
- [ ] **Project name:** `AlphaLoop` (codename-note: repo is `signal-mesh-arc`)
- [ ] **One-liner:** SUBMISSION §1 복사 ("A live A2A marketplace…")
- [ ] **Description:** SUBMISSION.md 본문 전체 붙여넣기
- [ ] **GitHub:** https://github.com/Leewonwuk/signal-mesh-arc
- [ ] **Video:** YouTube Unlisted URL
- [ ] **Demo:** https://signal-mesh.vercel.app
- [ ] **Cover image:** `docs/cover_image.svg` 업로드
- [ ] **Save Draft** 버튼 클릭 — 오늘은 여기서 멈춤

---

## 4. 내일(4/25) TODO — Final Submit

- [ ] Draft로 저장된 내용 전체 재확인 (특히 YouTube 링크가 unlisted 맞는지)
- [ ] SUBMISSION §5 (Circle products) 표에 **실제 tx hash 한 개 이상** 포함됐는지
- [ ] Cover image 썸네일 제대로 렌더되는지
- [ ] **Submit** 버튼 클릭 → 제출 완료 확인 화면 스크린샷
- [ ] 제출 후 lablab Discord에 "submitted" 한마디 (communal confirmation)

**Do NOT Submit 버튼 오늘 누르지 말 것.** lablab 규정상 수정 불가능할 수 있음.

---

## 5. 리스크 매트릭스 & 폴백

| # | 리스크 | 확률 | 충격 | 폴백 |
|---|---|---|---|---|
| R1 | Faucet 또 막힘 (quota) | 중 | 대 | paper-only 데모 + `docs/evidence/` 인서트 + SUBMISSION에서 "60+ tx" → "infrastructure validated, faucet-gated" 한 줄 |
| R2 | Circle private key export 막힘 | 저 | 대 | 별도 EOA 생성 후 그쪽으로 USDC 소량 이전 |
| R3 | Bridge 크래시 (녹화 중) | 저 | 대 | `docs/evidence/` JSON + VS Code 워크스루 |
| R4 | Premium 시그널 저빈도 (4/21 확인) | 고 | 중 | 웜업 10분 이상 선행 → 녹화 시작 시 40+ 캐시 상태 |
| R5 | 영상 3분 초과 | 중 | 중 | S2 슬라이드 30s → 15s로 컷 |
| R6 | OBS 설정 실패 | 중 | 중 | Xbox Game Bar `Win+G`로 한 방 녹화 |
| R7 | 마이크 안 됨 | 저 | 중 | OBS Text source 자막으로 대체 |
| R8 | YouTube 업로드 실패 | 저 | 대 | Vimeo unlisted 백업 계정 |
| R9 | lablab 폼 다운 | 저 | 극대 | Discord에 문의 + 스크린샷 보관 |

---

## 6. 🏛️ 거인의 어깨 pre-mortem (제출 국면)

> v2 규약 — "이 원칙이 무너지는 전형적 실패 시나리오"를 각 거장별로 1-2개씩.

### Paul Graham — "make something people want" / schlep blindness
- **실패 시나리오:** "RL agent marketplace" 제네릭 포지션으로 14개 클러스터 A 팀 속에 녹음.
- **현재 회피:** §1 TL;DR 3줄 = `USDC-as-gas closes loop` / `60+ sub-cent A2A tx` / `RL ties empirical optimum`. "43개 중 유일 live-bot backing" 차별화 축 유지.
- **남은 리스크:** 영상 0:00~0:30 콜드오픈이 "another agent economy demo"처럼 들리면 즉사. 좌(Base) vs 우(Arc) 대비로 **3초 침묵**부터 시작해야 wedge가 박힘.

### Garry Tan — ONE thing · 적 · aha 모멘트 · 클로징
- **실패 시나리오:** 3분 영상에 feature 나열만 나오고 "적"이 불명확 → 판사 메모리에 한 줄도 안 남음.
- **현재 회피:** 적 = "hidden human refunding the gas wallet". aha 모멘트 = 컷3 카운터 상승 + 페르소나 스왑 즉시 반응.
- **남은 리스크:** 클로징(컷5) 10초가 무력하면 CTA 실종. GitHub URL만 크게 띄우고 "thanks for judging"로 끝내는 것 유지.

### Andrej Karpathy — 파이프라인 일관성 · 데이터 정직성 · 과장 감지
- **실패 시나리오:** v1 kimchi synthetic을 synthetic이라 안 써두면 "데이터 조작" 의심. Round 1 z-blend 숨기고 Round 2만 보여주면 rigor가 사라짐.
- **현재 회피:** SUBMISSION §11 data provenance 표 — v3 real / v2 real 1d + bootstrap / v1 synthetic 명시. §11.b.1에서 Round 1 실패 → Sutton 감사 verbatim 인용 → 1-line fix까지 그대로 노출.
- **남은 리스크:** 영상 보이스오버에서 "1s tape from live v1.3 bot" 말할 때 "캡처 4/19"라고 명확히 말해야 함. "live"라고만 하면 claims가 커짐.

### Vitalik Buterin — L1 trust model · 서명 방식 · paymasters 반박
- **실패 시나리오:** "USDC-as-gas" 자랑하는데 판사가 "paymasters/4337이면 다른 L1도 같은 UX 가능"이라 반박 → 논파.
- **현재 회피:** SUBMISSION §6 margin math 표 — Base/Polygon/Solana 모두 two-unit accounting (USDC earn / native pay) 남아서 self-balance 불가 지적. Solana 낮은 fee조차 SOL top-up cron 필요.
- **남은 리스크:** 영상에서 "every other chain" 과장하지 말 것. Arc의 wedge는 "native unit of account"이지 "lowest fee" 아님.

### Kent Beck — shipping discipline · stale references · cut list
- **실패 시나리오:** SUBMISSION.md 내부 ref 중 하나라도 broken이면 rigor 신뢰 붕괴 (2060264 커밋에서 이미 한 번 고침).
- **현재 회피:** 오늘 `grep -rE "\[.*\]\(.*\)" docs/SUBMISSION.md`로 내부 링크 전수 검사 한 번 더. Cut list: 11.b 백테스트 · faucet tx 60+ · Allocator heatmap · 페르소나 스왑 — **이 4개만** 반드시 영상에 담김.
- **남은 리스크:** 영상 자막/설명란에 `docs/...` 상대경로 쓰지 말 것. GitHub 절대 URL로.

---

## 7. 제출 페이로드 최종 체크 (4/25 Submit 직전)

- [ ] **Project name** = `AlphaLoop` (본문 첫 줄에 "codename for signal-mesh-arc")
- [ ] **One-liner** ≤ 200자, SUBMISSION §1 첫 줄 그대로
- [ ] **Description** SUBMISSION.md 본문 복붙 (섹션 번호 유지됨)
- [ ] **GitHub** https://github.com/Leewonwuk/signal-mesh-arc — 열리는지 incognito로 확인
- [ ] **Video** YouTube Unlisted — 로그아웃 상태에서 재생되는지 확인
- [ ] **Demo** https://signal-mesh.vercel.app — 대시보드 live 렌더 확인
- [ ] **Cover** `docs/cover_image.svg` — lablab 썸네일 렌더 확인
- [ ] **Tracks** ✅ Agent-to-Agent Payment Loop (primary) · ✅ Per-API Monetization (secondary)
- [ ] **Circle products checklist** — Arc L1 · USDC on Arc · EIP-3009 nanopay · x402 · Developer Console 모두 체크
- [ ] **Product feedback link** — \$500 bonus용 `docs/PRODUCT_FEEDBACK.md` URL (GitHub 절대경로)
- [ ] **Team** solo — `Leewonwuk (skyskywin@gmail.com)`

---

## 8. 파일 레퍼런스 맵

| 상황 | 참조 파일 |
|---|---|
| 오늘 해야 할 일 압축 | [TODO_2026-04-22.md](docs/TODO_2026-04-22.md) (핸드폰용) |
| 상세 런북 | [TOMORROW_RUNBOOK_2026-04-22.md](docs/TOMORROW_RUNBOOK_2026-04-22.md) |
| OBS 씬·컷별 대본 | [RECORDING_GUIDE_KR.md](docs/RECORDING_GUIDE_KR.md) |
| 영어 보이스오버 | [VIDEO.md](docs/VIDEO.md) |
| 제출 본문 | [SUBMISSION.md](docs/SUBMISSION.md) |
| Product feedback (보너스) | [PRODUCT_FEEDBACK.md](docs/PRODUCT_FEEDBACK.md) |
| 백테스트 결과 | [BACKTEST_REPORT.md](docs/BACKTEST_REPORT.md) · [BACKTEST_ML_REPORT.md](docs/BACKTEST_ML_REPORT.md) · [BACKTEST_RULES_V2_REPORT.md](docs/BACKTEST_RULES_V2_REPORT.md) |
| Allocator 설계 근거 | [ALLOCATOR_RL_DESIGN.md](docs/ALLOCATOR_RL_DESIGN.md) |
| 폴백 B-roll | [docs/evidence/README.md](docs/evidence/README.md) |
| Giants' Shoulders 리뷰 | [GIANTS_SHOULDERS_ALLOCATOR_REVIEW.md](docs/GIANTS_SHOULDERS_ALLOCATOR_REVIEW.md) |
| 트랙·스택 | [TRACK_AND_STACK.md](docs/TRACK_AND_STACK.md) |

---

## 9. 마음가짐

- 오늘은 **Draft Save만** — Submit 버튼 누르지 않음
- 영상이 100% 완벽할 필요 없음 — 영상 30%, GitHub 40%, SUBMISSION.md 30%가 판사 점수 분포 경험칙
- 막히면 **폴백 B-roll** 있음 — `docs/evidence/` 13개 JSON은 조작 없이 실측
- 43팀 중 유일한 **live-bot backing** · 유일한 **walk-forward Q-learning tied to empirical optimum** · 유일한 **Sutton-school adversarial audit 증빙** — 이 세 개가 moat

오늘 블록 끝내고 체크해줘. 내일 아침 Submit.
