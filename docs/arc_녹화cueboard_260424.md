# 🎬 녹화 운영 큐보드 (2026-04-24 촬영용)

> **사용법**: 핸드폰 세로 화면에서 위→아래로 스크롤. 왼쪽 PC 모니터에서 녹화, 오른쪽 핸드폰에서 이 문서 따라 읽기.
> **핵심**: 스크립트 영문은 **회색 박스**에 담겨있음. 그대로 읽으면 됨. 말 씹어도 계속 진행.
> **원본**: [`docs/VIDEO_SCRIPT_KR.md`](VIDEO_SCRIPT_KR.md) · [`docs/RECORDING_GUIDE_KR.md`](RECORDING_GUIDE_KR.md)

---

## 📋 0. 녹화 전 30분 체크리스트

> 폰 타이머 켜고 하나씩 지워가며 진행.

| ⏱ 시간 | ✅ 할 일 | 터미널 |
|---|---|---|
| **T-30** | `cd bridge && npm run dev` | T1 |
| **T-29** | `cd dashboard && npm run dev` | T2 |
| **T-28** | 페르소나 curl POST (아래 코드블록) | T4 |
| **T-25** | `localhost:5173` 브라우저 열기 | — |
| **T-20** | 데모 드라이버 실행 (아래 코드블록) | T3 |
| **T-15** | Allocator tick 3-5회 들어오는지 확인 → 히트맵 칸 차는지 | — |
| **T-10** | `docs/SLIDES.pdf` 풀스크린 F5 | — |
| **T-5** | `testnet.arcscan.app` 빈 탭 준비 | — |
| **T-3** | OBS 5씬 · 마이크 게인 · 배경소음 | — |
| **T-1** | 심호흡 3번, 물 한 모금 | — |
| **T-0** | **🔴 Record** | — |

### T-28: 페르소나 POST

```bash
# ⚠️ WARMUP: demo persona (0.05% threshold)로 시작해서 premium 흐름 생성 (Bybit 0.17%는 demo 데이터에 너무 strict).
# 녹화 T-2 시점에 Bybit로 스위치해 "persona switching is live, demotions tick" 2:27 내레이션 연결.

# T-28 WARMUP (demo persona)
curl -X POST http://localhost:3000/policy/persona \
  -H 'Content-Type: application/json; charset=utf-8' \
  --data-binary '{"exchangeId":"demo","label":"Demo - relaxed threshold","feeRoundTrip":0.0005,"thresholdRate":0.0005,"supportsDualQuoteArb":true}'

# T-2 (녹화 직전, Bybit로 전환)
# ASCII-only label — `·` 중간점은 Windows Git Bash cp949 인코딩과 충돌해서 mojibake (Bybit 占쏙옙 VIP)
curl -X POST http://localhost:3000/policy/persona \
  -H 'Content-Type: application/json; charset=utf-8' \
  --data-binary '{"exchangeId":"bybit","label":"Bybit - VIP 0 + USDC 50% off","feeRoundTrip":0.0015,"thresholdRate":0.0017,"supportsDualQuoteArb":true}'
```

### T-20: 데모 드라이버 (T3 터미널)

```bash
python -m demo.run_demo --symbols DOGE,XRP,SOL --duration 900 --speed 100 --threshold 0.0005 --fee-rate 0
```

### 🚨 T-15 검증 포인트 — 여기서 막히면 녹화 금지

- 대시보드 **Policy Heatmap**: 최소 2-3 칸은 색 들어와야 함
- 대시보드 **Fee Persona Explorer**: Bybit 표시되어야 함
- 대시보드 **Settlement tx**: 0이어도 OK (batch는 녹화 중 발사)
- 스모크 재확인: `bash scripts/pre_record_check.sh`

---

## 🖥 1. 화면 레이아웃 (녹화 직전)

```
┌─────────────────────┬──────────────────────┐
│                     │  T1 대시보드 크롤    │
│  슬라이드 PDF       │  localhost:5173      │
│  (풀스크린 대기)    ├──────────────────────┤
│                     │  T2 터미널:          │
│                     │  demo.run_demo       │
│                     │  (돌아가는 중)       │
│                     ├──────────────────────┤
│                     │  T3 터미널:          │
│                     │  circle_batch_settle │
│                     │  (엔터 대기)         │
└─────────────────────┴──────────────────────┘
```

**OBS 5 씬**:
1. **S1 타이틀** — 검은 배경 흰 글씨
2. **S2 대시보드 + 터미널** — 메인 데모 씬
3. **S3 슬라이드 풀스크린** — PDF 리더
4. **S4 arcscan 브라우저** — tx 검증용
5. **S5 클로징** — cover_image.svg + GitHub URL

---

## 🎙 2. 영상 1 — 3분 피치 (컷별 스크립트)

> ⏱ **분당 150단어**. 총 ~420단어. 3:00 하드컷.

### 🎬 0:00-0:05 │ 타이틀 카드 (말 없음)

**씬 S1** · 2컷, 각 2.5초

- **컷 1** (검은 배경, 흰 글씨): **USDC is the gas.**
- **컷 2** (검은 배경, 시안 글씨): **On Arc.**

> 🎯 Tan 규약: 단정형. 부정형 ("there isn't one") 금지.

---

### 🎬 0:05-0:30 │ The Wedge (25초)

**씬 S2** · 좌우 분할: 왼쪽 Base Etherscan fee 스크린샷, 오른쪽 터미널에 Arc tx fee

```
I run a live arb bot on EC2 — nine coins, running right now.
This demo is me selling its signals to other agents, on-chain,
every second. On every other chain, agents earn USDC but pay
gas in ETH — a hidden human refills that wallet. On Arc,
USDC IS the gas. Signal in, payment out, gas — all USDC.
The agent closes its own books.
```

> 🎯 "closes its own books" 말하고 1초 정적 → 다음 컷.

---

### 🎬 0:30-0:50 │ 문제 정의 (20초)

**씬 S3** · `SLIDES.pdf` "The Problem" 슬라이드 풀스크린

```
Per-signal value in an agent marketplace is a fraction of a cent.
On Base or Polygon or Solana, gas alone eats most of that.
And worse, agents earn in USDC but pay gas in ETH or SOL —
two-unit accounting. The agent literally cannot self-balance.
Every existing agent-economy demo you've seen has a human
quietly refilling the gas wallet.
```

---

### 🎬 0:50-1:15 │ 왜 Arc인가 (25초)

**씬 S3** · `SLIDES.pdf` "Why Arc" 슬라이드

```
Arc makes USDC the native gas. One unit of account for fee,
payment, and gas. That collapses the architecture — a producer
earning USDC can fund its own gas from its own revenue.
An agent stack that runs forever without an operator topping
up native tokens. That is what CLOSED LOOP means in this pitch.
No paymaster layer, no subsidy pipeline, no hidden operator.
```

---

### 🔴 1:15-2:00 │ 라이브 데모 (45초) — 본진

**씬 S2** · 대시보드 + 터미널 T3

#### 1:15 — 대시보드 오프닝

```
This is the AlphaLoop dashboard — bridge and three producers
are already live in the background.
```

#### 1:18 — 터미널 T3로 포커스 → 엔터

```bash
node scripts/circle_batch_settle.js --count 150 --rate 3
```

**말**:
```
I'm firing one-hundred-fifty variably-priced USDC settlements between four Circle-managed
agent wallets on Arc testnet. Each one is a real block.
```

#### 1:25 — 대시보드로 돌아가서 Settlement tx 카드 가리키기

```
Watch the on-chain tx counter climb — these are real hashes
on arcscan, not staged.
```

#### 1:40 — tx 하나 클릭 → arcscan 탭 열림

```
Block confirmed. USDC 0.01. Sender: our producer agent.
Recipient: our meta agent.
```

#### 1:50 — 대시보드 raw/premium 카운터 가리키기

```
At the same time, the Gemini-powered meta agent is arbitrating
incoming signals from three producers — the dual-quote feed is
a one-second replay of my live v1.3 production arb bot.
Real prices, not synthetic.
```

> 🎯 45초 안에 한 문장 씹어도 OK. 계속 가세요.

---

### 🎬 2:00-2:30 │ RL 핵심 (30초)

**씬 S3** · SLIDES "Walk-forward backtest" 테이블

#### 2:00 — 드라마 먼저

```
Round one, this learner lost to a one-line if-statement.
We fixed the reward function. Round two — it ties the empirical
optimum. P equals zero point four nine versus ALL underscore
V two. The convergence IS the rigor signal. If it had diverged
from the rule, that would have been the bug.
```

#### 2:20 — 대시보드 Policy Heatmap 확대

```
Nine regime states, seven actions. The sparse ALL_V3 column
is expected — ninety percent of the history window was
cold-funding. A heatmap that enthusiastically picked ALL_V3
would be the red flag.
```

#### 2:27 — FeeExplorer: Bybit → Coinbase 클릭

```
And persona switching is live — the bridge demotes incompatible
venues in real time. See the demotion counter tick.
```

---

### 🎬 2:30-2:50 │ Originality (20초)

**씬 S3** · SLIDES "Originality" 슬라이드

```
This is not a chatbot wrapping a wallet. It's a market.
Variable on-chain price encodes signal quality. Outcome
feedback retroactively re-prices future signals from the
same producer. A learned meta-policy sits above that,
deciding which strategy even gets to trade.
That is a real market, not a cron job.
```

---

### 🎬 2:50-3:00 │ CTA (10초)

**씬 S5** · cover_image.svg + GitHub URL

```
One-fifty variably-priced tx, closing the loop. One unit of account. Zero humans in the gas tank.
Open the repo, fire the demo, watch the allocator pick.
AlphaLoop — on Arc.
```

*(1초 침묵 → 하드컷)*

> 🎯 Tan 규약: 동사 3개 (open/fire/watch) + 숫자 3개 (60/1/0).

---

## 🎙 3. 영상 2 — Circle Console tx 검증 (≤60초)

> lablab.ai 명시 요건. **별개 영상 파일.**

### 0:00-0:15 │ Console

**화면**: Circle Developer Console → Wallets → `producer_kimchi` 클릭

```
This is the Circle Developer Console. I have four
developer-controlled wallets provisioned for the four agents
in my marketplace. Here's one — producer_kimchi — funded
with 20 USDC from the Arc testnet faucet.
```

### 0:15-0:35 │ Console tx 실행

- Console UI → **Send** 클릭
- 주소 붙여넣기: `0xf8f1ae7b49901e6a93b5ddf7f5bd7af998466a0f` (meta_agent)
- Amount: `0.01 USDC` → Submit

```
I'll send a settlement tx from the Console — point-zero-one
USDC to the meta agent. Transaction queued.
```

- tx hash 복사

### 0:35-0:55 │ Arc Explorer 검증

- 새 탭: `testnet.arcscan.app` → hash 붙여넣기 → Enter

```
And here on Arc Block Explorer — block confirmed, token
transfer event, one-cent USDC moved from agent wallet
to agent wallet.
```

### 0:55-1:00 │ 클로징

```
One tx via the Console. Verified on arcscan. The full demo
runs one-hundred-fifty variably-priced settlements like this through the AlphaLoop pipeline.
```

---

## 🎤 4. 딕션 & 톤

- **한국 억양 OK** — 심사위원 다국어 콘텐츠 익숙
- **빠르되 웅얼거리지 말기** — 키워드 또박또박
- **강조 단어 3개**: **agent**, **marketplace**, **closed loop**
- **숫자는 풀어서**: "p equals zero point four nine" (p=0.49 안 읽음)
- **"signal mesh on arc"** 끝 발음 떨어뜨리기 (질문형 금물)

---

## 🚨 5. 비상 폴백

| 상황 | 대응 |
|---|---|
| Circle batch "FAIL" 뜸 | 침착하게 "Let me continue with the existing tx history" — evidence 파일에 150 records 이미 landed |
| 대시보드 빈 화면 | "Bridge connection" 한마디 + F5 |
| 말 씹음 | 1초 침묵 → 문장 다시. 편집으로 잘라냄 |
| 배경 소음 | 계속 진행. 편집에서 노이즈 제거 |
| **3분 초과** | 0:30-0:50 문제 슬라이드를 10초로 압축 |
| 심각한 에러 | 녹화 중단 → 재시도. 2회까지는 자연스러움 |

---

## 📦 6. 편집 가이드

- **컷 5군데**: 0:05 / 0:30 / 1:15 / 2:00 / 2:50
- **BGM**: 없어도 됨. 있다면 lo-fi 20% 볼륨
- **자막**: 영어 자막 **필수** (심사위원 국적 다양)
- **말 중간 긴 침묵 (2초+)** → 자르거나 jumpcut
- **끝 2초 침묵** → 로고 페이드 → 하드컷

---

## 🚀 7. 업로드 + 제출

### 7.1 YouTube

1. 제목: `AlphaLoop — Agentic Economy on Arc Hackathon Submission (Track 2: Agent-to-Agent Payment Loop)`
2. 설정: **Unlisted** (Public 아님)
3. 설명란에 GitHub URL + dashboard URL
4. URL 복사

### 7.2 lablab.ai

1. 제출 폼에 YouTube URL 붙여넣기
2. GitHub URL 붙여넣기
3. 영상 2 (Console tx) URL 붙여넣기
4. **Save Draft** → 리뷰 → **Submit**
5. **Deadline: 2026-04-26 09:00 KST**

---

## 💡 8. 마지막 조언

> 이 스크립트를 **3번 리허설**하세요.
> 3번째에 익숙해집니다.
> 첫 녹화가 제일 별로입니다.
> 2-3번 찍으세요.
> **실전 컷은 보통 4번째.**

깊게 호흡. 3분 안에 끝남. 화이팅. 🔥
