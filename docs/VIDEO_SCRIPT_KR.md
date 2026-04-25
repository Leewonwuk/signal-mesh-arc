# 🎬 AlphaLoop — Video 1 (3분 본 피치 + 데모) 스크립트

> **프로젝트명**: **AlphaLoop** (~~working title: Signal Mesh on Arc~~)
> **Alpha** = 트레이딩 moat (live v1.3 EC2 봇이 생성) · **Loop** = Track 2 "Agent-to-Agent Payment Loop" 명명 계승

> **타겟**: lablab.ai 심사위원 (영어권, AI/크립토 초심자 아님). 3:00 하드컷.
> **말하기 속도**: 분당 150단어 정도. 총 ~420 단어 budget.
> **이 문서는 "그대로 말하면 된다"가 목표** — 변주는 최소화하고, 실수해도 계속 가세요.
>
> **화면 셋업 (녹화 직전)**:
> 1. 왼쪽: 크롬 브라우저 — **공개 대시보드** `https://signal-mesh.vercel.app/` (URL 바 보이게) + `http://localhost:5173` (로컬 데모 — 라이브 신호용)
> 2. 오른쪽 위: 터미널 1 — `python -m demo.run_demo --symbols DOGE,XRP,SOL --duration 900 --speed 100 --threshold 0.0005 --fee-rate 0` (이미 돌아가는 중. `--with-kimchi`, `--with-funding`, `--funding-demo-threshold 0.00002` 모두 default ON — v1/v2/v3 3-lane 동시 emit)
> 3. 오른쪽 아래: 터미널 2 — 아직 엔터 안 친 상태로 `node scripts/circle_batch_settle.js --count 150 --rate 3` 준비
> 4. 추가 탭: `https://testnet.arcscan.app` (빈 페이지, 나중에 붙여넣기용) + `https://signal-mesh.vercel.app/scoreboard.html` (5 ERC-8004 agent identity 검증용)
> 5. 슬라이드 PDF 풀스크린 모드 대기
>
> **녹화 시점 대시보드 상태 검증 (3분 warm-up 후)**:
> - StrategyMixChip: `mix v1·N v2·N v3·N`에서 모두 ≥1, `?·0` (unk 0건)
> - Strategy Cards 3장 모두 live signal 흐름 (v1 kimchi · v2 dual · v3 funding)
> - AgentIdentityCard: 5건 (3 producers + 1 meta + 1 executor) 모두 contentHash + tx 링크 표시
> - Settlement TX: 다양한 amount ($0.0005~$0.010 분포 보이는 게 이상적; 동일 $0.01만 보이면 Q-learner saturation)

---

## 0:00 – 0:05 │ **제로-초 타이틀 카드 (말 없음, 2컷)**

**컷 1 (검은 배경 흰 글씨, 2.5초)**:
> **"USDC is the gas."**

**컷 2 (검은 배경 시안 글씨, 2.5초)**:
> **"On Arc."**

**컷 3 (추가 — 프로젝트 브랜드 카드, 2초)**:
> **"AlphaLoop"** (90pt, cyan on black)
> _하단 muted 18pt_: `The agent-to-agent alpha loop · Track: Agent-to-Agent Payment Loop · lablab.ai Agentic Economy on Arc`

*(총 5초 후 페이드 → 0:05 씬으로)*

**🎯 Tan 규약**: 단정형 2컷 — 부정형 ("there isn't one") 헤드는 YC 금기. ONE thing을 먼저 박고 적은 0:05-0:30 내에서 제시.
**🎯 요건 반영**: 컷 2 하단에 트랙 명시 (판사 분류 용이). SUBMISSION_REQUIREMENTS.md "Clearly state challenge track" 요건 직접 대응.

---

## 0:05 – 0:30 │ **The wedge — 왜 Arc가 다른가**

**화면**: 좌우 분할
- 왼쪽: Etherscan의 Base mainnet 평균 tx fee 스크린샷 ("~$0.012 in ETH")
- 오른쪽: 터미널에 `curl https://testnet.arcscan.app/tx/0x2c97f3fc...` 결과 (fee ≈ 0.007 USDC)

**음성 (영어, 25초)**:
> "I run a live arb bot on EC2 — nine coins, running right now. And those signals flow to other agents on-chain — every second. On every other chain, agents earn USDC but pay gas in ETH — a hidden human refills that wallet. On Arc, USDC *is* the gas. Signal in, payment out, gas — all USDC. The agent closes its own books."

**🎯 핵심 tip**: 마지막 문장 "closes its own books"에서 정적. 다음 슬라이드로 컷. PG 규약: 기술 얘기 전에 "I AM the user" 증명 먼저.

---

## 0:30 – 0:50 │ **문제 정의 (슬라이드)**

**화면**: `docs/SLIDES.pdf` 중 "The Problem" 슬라이드 풀스크린

**음성 (20초)**:
> "Per-signal value in an agent marketplace is a fraction of a cent. On Base or Polygon or Solana, gas alone eats most of that. And worse, agents earn in USDC but pay gas in ETH or SOL — two-unit accounting. The agent has no way to self-balance. Behind every agent-economy demo, there's a human quietly refilling the gas wallet."

---

## 0:50 – 1:15 │ **왜 Arc인가 (슬라이드)**

**화면**: SLIDES.pdf "Why Arc" 슬라이드

**음성 (25초)**:
> "Arc makes USDC the native gas. One unit of account for fee, payment, and gas. That removes a whole layer — a producer earning USDC can fund its own gas from its own revenue. An agent stack that runs forever without an operator topping up native tokens. That is the *closed loop*. No paymaster layer, no subsidy pipeline, no hidden operator."

---

## 1:15 – 2:00 │ **🔴 라이브 데모 — 마켓플레이스** (45초, 여기가 본진)

**화면 전환**: 크롬 (대시보드) + 터미널 2 (Circle batch 대기)

**🎬 액션 시퀀스 — 반드시 이 순서**:

1. **[1:15]** 대시보드를 먼저 보여주며 말하기 시작 (URL 바 `signal-mesh.vercel.app` 보이도록):
   > "This is the AlphaLoop dashboard — live at signal-mesh.vercel.app. Bridge plus **three strategy producers** — kimchi, dual-quote, funding — are running in the background, backed by my v1.3 production arb bot. The mix chip up top shows v1, v2, v3 signals interleaving in real time."

2. **[1:20]** 터미널 2로 포커스 이동 → 엔터:  
   `node scripts/circle_batch_settle.js --count 150 --rate 3`
   > "I'm firing one-hundred-fifty **variably-priced** USDC settlements. Real Arc testnet, real x402, five ERC-8004 agent wallets. Each amount sampled from signal quality — half-a-tenth of a cent up to the one-cent cap."

3. **[1:28]** 대시보드로 돌아가서 **"Settlement tx (Arc testnet)"** 카드 손가락으로 가리키기:
   > "Watch the tx counter climb — these are real hashes on arcscan, and the **amounts vary per tx** — that's what *variable-price x402 settler* means. Low-signal clears at one-twentieth of a cent; high-confidence at the one-cent cap. This is the **alpha loop**, not a round-number receipt."

4. **[1:40]** 하나 클릭 → `testnet.arcscan.app` 새 탭 열림:
   > "Block confirmed. Amount reflects what the meta agent judged this specific signal was worth. Sender: our producer agent. Recipient: our meta agent."

5. **[1:50]** 다시 대시보드 → **Strategy Lanes** 3장 카드 가리키기:
   > "Meanwhile, the Gemini-powered meta agent is arbitrating across **three strategy lanes** — v1 kimchi premium between Korean and Global venues, v2 dual-quote spread inside one venue, v3 funding-rate basis on perp. The dual-quote lane is a one-second replay of my live v1.3 production arb bot — real prices, not synthetic."

**🎯 tip**: 이 45초 안에 문장 하나라도 씹어도 괜찮음. "하나씩 채점되지 않음"이 피치의 미덕.

---

## 2:00 – 2:30 │ **RL 핵심 — "왜 3개 전략을 RL로 고르나?"에 답하기** (30초)

**🎬 화면**: 대시보드 **Regime → Strategy** 카드 (RegimeMap) 확대 → SLIDES.pdf "Walk-forward backtest" 테이블

**음성 (30초, 2개 비트)**:

**Beat 1 — Regime wedge (먼저 WHY)**:
> "Each strategy has its own regime where it shines. v1 kimchi spikes hardest when KR-Global volatility blows out. v2 dual-quote is most reliable when funding is hot but vol is calm. v3 funding-rate captures pure carry in calm-cold regimes. **No human can switch fast enough between these as regimes drift.** So we let an RL agent learn the switch from realized PnL."

**Beat 2 — Round 2 receipt (그 다음 PROOF)**:
> "Round one, this learner lost to a one-line if-statement. We fixed the reward function. Round two — ties the empirical optimum. P equals zero point four nine versus ALL underscore V two — because the holdout window happened to be v2-favorable. **In the hot-vol regimes the q-value gap is three-point-two-two versus one-point-eight-one — that's where v1 kimchi pulls away.** The convergence is the rigor signal."

**🎯 Tan 규약**: WHY (regime → strategy 매핑) → PROOF (Round 2 동률). 동률이 weakness 아닌 **honest disclosure**로 reframe — *"holdout이 v2 유리한 구간이었지만 hot-vol regime에선 q=3.22로 이긴다"* 가 핵심.

**🎯 Karpathy 규약**: 추상 RL 용어 안 씀. "regime where it shines" / "switch from realized PnL" — 실제 작동 원리를 영어 한 문장으로.

**[2:20]** → 대시보드 전환 → **Policy Heatmap** 카드 확대 (axes legend 같이 보이게):
> "Nine regime states — vol, funding, dislocation. Seven actions. The heatmap shows the learned policy in production: hot-vol rows light up ALL_V1, hot-funding rows light up ALL_V2, calm-cold rows light up ALL_V3. **The mapping you saw above is what the model actually does.**"

**[2:27]** → FeePersonaExplorer 탭에서 **Bybit retail-tagged VIP 0 → Coinbase** 클릭:
> "And persona switching is live — note the *retail* tag on VIP 0 and the warning chip if you pick an institutional tier. The bridge demotes incompatible venues in real time."

---

## 2:30 – 2:50 │ **Originality + ERC-8004 on-chain (슬라이드 + 대시보드)**

**화면**: 대시보드 스크롤 → **Agent Identity** 카드 (on-chain ERC-8004) 확대 → 그 다음 SLIDES.pdf "Originality" 슬라이드

**음성 (20초)**:
> "This is not a chatbot wrapping a wallet. Each of our five agents has its own ERC-8004 registration card. Our AlphaLoopAgentRegistry on Arc testnet emitted five AgentRegistered events — each carrying the sha256 hash of the agent's card. Off-chain document, on-chain anchor. Variable price encodes signal quality, outcome feedback re-prices future signals, and a learned meta-policy decides which strategy trades. That is a real market — verifiable end-to-end."

---

## 2:50 – 3:00 │ **CTA** (10초)

**화면**: 표지 이미지 (`docs/cover_image.svg`) + GitHub URL + **`signal-mesh.vercel.app`** 대시보드 URL 큰 글씨

**음성 (10초)**:
> "One-fifty variably-priced tx, closing the loop. One unit of account. Zero humans in the gas tank. **Open signal-mesh.vercel.app, fire the demo, watch the allocator pick.** **AlphaLoop — on Arc**."

*(침묵 1초 후 하드컷)*

**🎯 Tan 규약**: CTA에 동사 3개(open/fire/watch) + 숫자 3개(150/1/0). "thanks for watching" 류 회의록 톤 금지. URL을 동사 안에 넣어서 외울 필요 없게.

---

# 🎬 Video 2 — "Circle Console tx 검증" 영상 (≤ 60초)

lablab.ai 명시 요건: "tx via Circle Developer Console + Arc Explorer 검증". **별개 영상.**

## 0:00 – 0:15 │ Console
- 화면: Circle Developer Console → Wallets → `producer_kimchi` 클릭
- 말: *"This is the Circle Developer Console. I have four Circle developer-controlled wallets provisioned for four of the five agents in my marketplace — the v3 funding producer is operator-controlled pending Circle SCA rotation, honestly disclosed in its agent-card. Here's one — producer_kimchi — funded with 20 USDC from the Arc testnet faucet."*

## 0:15 – 0:35 │ Console 내에서 tx 실행
- Console UI에서 **Send** 클릭 → 주소 붙여넣기: `0xf8f1ae7b49901e6a93b5ddf7f5bd7af998466a0f` (meta_agent)
- Amount: `0.01 USDC` → Submit
- 말: *"I'll send a settlement tx from the Console — point-zero-one USDC to the meta agent. Transaction queued."*
- tx hash 복사

## 0:35 – 0:55 │ Arc Explorer 검증
- 새 탭: `testnet.arcscan.app` → hash 붙여넣기 → Enter
- 말: *"And here on Arc Block Explorer — block confirmed, token transfer event, one-cent USDC moved from agent wallet to agent wallet."*

## 0:55 – 1:00 │ 클로징
- 말: *"One tx via the Console. Verified on arcscan. The full demo runs one-hundred-fifty variably-priced settlements like this through the AlphaLoop pipeline."*
- 컷.

---

# 📝 녹화 전 30분 체크리스트

| 시간 | 할 일 |
|---|---|
| T-30 | `cd bridge && npm run dev` (T1) |
| T-29 | `cd dashboard && npm run dev` (T2) |
| T-28 | 페르소나 curl (ASCII-only label — `·` 중간점은 Windows Git Bash cp949 인코딩 충돌로 mojibake 됨): `curl -X POST http://localhost:3000/policy/persona -H 'Content-Type: application/json; charset=utf-8' --data-binary '{"exchangeId":"bybit","label":"Bybit - VIP 0 + USDC 50% off","feeRoundTrip":0.0015,"thresholdRate":0.0017,"supportsDualQuoteArb":true}'` |
| T-25 | 대시보드 `http://localhost:5173` 열기 (페르소나 이미 표시됨) |
| T-20 | `python -m demo.run_demo --symbols DOGE,XRP,SOL --duration 900 --speed 100 --threshold 0.0005 --fee-rate 0 --funding-demo-threshold 0.00002` 실행 (T3) — `--with-kimchi`, `--with-funding` default ON |
| T-17 | StrategyMixChip이 `mix v1·N v2·N v3·N`로 3-lane 모두 ≥1 표시될 때까지 대기 (보통 30~60초) |
| T-15 | Allocator tick 3-5회 들어올 때까지 대기 → heatmap 칸 차는지 + Strategy Cards 3장 모두 신호 흐름 확인 |
| T-10 | `SLIDES.pdf` 풀스크린 모드 프리뷰 (F5) |
| T-5 | Arc Explorer 빈 탭 준비 (`testnet.arcscan.app`) |
| T-3 | OBS 5씬 체크 → 마이크 게인 확인 → 배경 소음 확인 |
| T-1 | 심호흡 3번, 물 한 모금 |
| T-0 | **Record** |

---

# 🚨 비상 폴백 (촬영 중 뭐 터졌을 때)

| 상황 | 대응 |
|---|---|
| Circle batch "FAIL" 뜸 | 침착하게 "Let me continue with the existing tx history" — evidence 파일에 150 records 이미 landed, scoreboard.html 으로 보여주기 |
| 대시보드 빈 화면 | "Bridge connection" 한마디 하고 F5 → Recording Guide의 '브릿지 죽음' 폴백 |
| 말 씹었음 | 침묵 1초 → 문장 다시 시작. 편집으로 잘라냄 |
| 배경 소음 | 계속 진행. 편집에서 노이즈 제거 |
| 3분 초과 | **0:30-0:50 문제 정의 슬라이드를 10초로 압축 가능** (가장 잘라내기 쉬움) |
| 심각한 에러 | 녹화 중단 → 재시도. 2회까지는 자연스럽다 |

---

# 🛡️ 6. 판사 Q&A 백포켓 (녹화 후 인터뷰 / Judge 페이지 댓글 대응)

> 녹화 외에 lablab.ai 판사 페이지 댓글이나 후속 인터뷰에서 다음 질문이 나오면 즉답. 전문 답변은 `docs/arc해커톤_경쟁작방어라인_260426.md` 참조.

| 질문 | 1줄 답변 (영어) | 근거 |
|------|----------------|------|
| **"Arc-native fit이 약하다 — Arc 빼도 봇 그대로 돌지 않나?"** | "Arc isn't our payment rail — it's our agent identity & verifiable performance ledger. Five ERC-8004 events with sha256 contentHash linkage. Without Arc, the marketplace claim is unverifiable." | 5 AgentRegistered on `0xb276b96f…b7ab` |
| **"9 instances of same bot 아닌가?"** | "Three structurally distinct lanes — kimchi, dual-quote, funding. Different threshold semantics, different data sources, different action verbs, different ideal regimes. Q-learner picks among lanes by regime." | RegimeMap dashboard + `allocator_q.json` |
| **"왜 RL? sharpe 제일 높은 거 항상 쓰면 되잖아"** | "Each strategy has a regime where it shines. v1 wins hot-vol at q=3.22, v2 wins hot-funding, v3 wins calm-cold. Static allocation captures the average, not the regime gap." | Slide 7 + RegimeMap |
| **"p=0.49 동률 — 그럼 ALL_V2만 쓰자"** | "Holdout window happened to be v2-favorable. In hot-vol regimes the Q-gap is 3.22 vs 1.81 — that's where v1 pulls away." | Slide 8 + Q-table state 4 |
| **"수수료 변동 시 edge 음수 안 되나?"** | "Threshold is config-only — POST `/policy/persona`. Bybit VIP-0 promo end → 0.20% threshold flag, not a code change. FeePersonaExplorer surfaces this in real time." | SUBMISSION §13 |
| **"Kelly fraction 명시 했나?"** | "1/4 Kelly cap, bounded by 0.01% × 24h venue volume per coin. Notional ≤ $500 paper book." | SUBMISSION §13 |
| **"Tail risk / VaR?"** | "Three kill-switches today: 6s IOC timeout, 0.25% stop-loss, per-coin notional cap. Portfolio-level coordinated halt is v1.32 roadmap. We disclose the gap rather than overclaim." | SUBMISSION §13 + §14 |
| **"BTC flash crash 시 9코인 동시 손실?"** | "v2 dual-quote and v3 funding lanes are net-delta-neutral by construction. Only v1 kimchi has directional KR-Global beta. Spread compression risk acknowledged, not directional drawdown across all three." | SUBMISSION §13 |
| **"Variable-price 라며 왜 다 $0.01만 보이지?"** | "Q-learner saturated to cap during this demo window. Historical evidence is in `docs/evidence/batch_tx_hashes_60_variable_run.txt` — $0.0005 to $0.0083 distribution, on-chain verifiable." | evidence file |
| **"v3 funding wallet이 Circle SCA 아니라며?"** | "Honest disclosure on the agent-card itself — v3 is operator-controlled pending Circle SCA rotation. Four of five wallets are Circle-SCA. We didn't fake the fifth." | producer-funding.json |

> **원칙**: 약점 부정 X, "v1.32 로드맵 + config-only"로 reframe. Karpathy 정직성 > 방어적 부정.

---

# 🎤 7. 딕션 & 톤

- **한국 억양 OK** — 심사위원은 다국어 콘텐츠 일상적으로 봄
- **빠르게 말하되 웅얼거리지 말기** — 키워드(Arc, USDC, walk-forward, p-value, ERC-8004)는 또박또박
- **"agent"/"marketplace"/"closed loop"/"variable-price"** — 이 4단어는 강조
- **숫자는 풀어서**: "p equals zero point four nine" ← "p=0.49" 안 읽음
- **"five agents"** — 항상 "three producers, one meta, one executor"로 풀어줌 (5라는 숫자가 청각 처리에 약하므로)
- **"signal-mesh.vercel.app"** — 마지막 음절 ("app")까지 또박또박, URL 시각 자막과 싱크
- **"AlphaLoop"** 끝 발음 떨어뜨리기 (질문형 금물)

---

# 📦 편집 팁 (DaVinci/Premiere/CapCut 아무거나)

1. 컷 5군데: (0:05) (0:30) (1:15) (2:00) (2:50)
2. BGM — 없어도 됨. 있다면 lo-fi beat 20% 볼륨
3. 말 중간 긴 침묵 (2초 이상) → 자르거나 jumpcut
4. 자막: **영어 자막 필수** (심사위원 국적 다양)
5. 끝 2초 침묵 → 로고 페이드 → 하드컷

---

**마지막 조언**: 이 스크립트를 **세 번 리허설** 하세요. 3번째에 익숙해집니다. 첫 녹화가 제일 별로입니다. 2-3번 찍으세요. 실전 컷은 보통 4번째.
