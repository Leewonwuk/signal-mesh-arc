# 영상 녹화 한국어 운영 가이드

> VIDEO.md는 영어 보이스오버 스크립트. 이 문서는 **OBS 옆에 두고 보는 운영 체크리스트** — 어떤 창, 어떤 명령어, 어떤 순서.
> 핸드폰으로 봐도 읽힐 수 있게 압축.

---

## 사전 준비 (촬영 시작 30분 전)

### 1. 화면 자산
- 모니터 해상도 **1920×1080** 권장 (영상 압축률 좋음)
- 다크 모드 통일: 터미널·VS Code·브라우저 전부 다크
- 폰트 크기 **터미널 16pt 이상** (1080p에서 가독성)
- 알림·슬랙·디스코드 모두 **방해 금지 모드**
- 시계 위젯·배터리·와이파이 표시 가린 가상 데스크톱 사용

### 2. OBS 씬 구성 (5개)

| 씬 | 구성 | 사용 컷 |
|---|---|---|
| **S1 콜드오픈** | 좌(터미널 Base 모의) / 우(터미널 Arc) 50:50 분할 | 0:00-0:30 |
| **S2 슬라이드** | Marp 슬라이드 풀스크린 (브라우저) | 0:30-1:15 |
| **S3 라이브** | 좌상(브리지 로그) / 좌하(데모 카운터) / 우(대시보드) | 1:15-2:30 |
| **S4 익스플로러** | 풀스크린 브라우저 (testnet.arcscan.app) | 2:30-2:50 |
| **S5 클로징** | 커버 이미지 + 깃허브 URL 큰 글씨 | 2:50-3:00 |

> Tip: 씬마다 **Display Capture** 대신 **Window Capture**로 캡처해야 알림창 새로 떠도 안 잡힘

### 3. 마이크 + 오디오
- 음성 한 번 테스트 녹음 → "신호 메시 온 아크" 발음 명료한지 확인
- 노이즈 게이트 -40dB
- 배경 음악 ❌ (해커톤 영상은 보이스오버 명료성 우선)

---

## 컷별 작전 시나리오 (3분짜리)

### 🎬 컷 1 (0:00-0:30) — 콜드오픈

**준비:**
- T1 터미널 좌측: `echo "tx fee: \$0.012 (ETH)"; echo "wallet ETH balance: 0.0008"` 미리 복붙해놓고 화면에 표시
- T1 터미널 우측: 진짜 Arc tx 결과 (Phase 4에서 캡처한 거 또는 라이브 호출)

**진행:**
1. S1 씬 활성화
2. 녹화 시작
3. **3초 침묵** (시각적 대비만)
4. 보이스오버 시작:
   > "Same A2A call, two chains. Left: gas in ETH, signal in USDC — a human has to keep refilling that ETH wallet. Right: gas in USDC, signal in USDC. The agent closes its own books. **That is the wedge.**"
5. 0:25 즈음에 **커버 이미지** (`docs/cover_image.svg`) 페이드인 → 0:30 컷

---

### 🎬 컷 2 (0:30-1:15) — 슬라이드

**준비:**
- 슬라이드 3, 4 미리 띄워둠 (Marp 미리보기 또는 화면 PPT)
- 슬라이드 넘기는 단축키 ↔ 사용

**진행:**
1. S2 씬으로 전환
2. 슬라이드 3 (Problem) 보이스오버:
   > "Per-signal value is half a cent. On Base/Polygon/Solana, gas is a large fraction of that. Worse — the agent earns USDC but pays gas in ETH. Two-unit accounting. Cannot self-balance. Every existing 'agent economy' demo has a hidden human refilling the gas wallet."
3. 슬라이드 4 (Why Arc) 보이스오버:
   > "USDC is the native gas token on Arc. Signal in USDC, paid in USDC, gas in USDC. Closed loop. An agent can pay upstream producers from downstream premiums — forever."

---

### 🎬 컷 3 (1:15-2:30) — 라이브 데모 (본진, 75초)

**🚨 가장 중요한 컷. 사전 검증 필수.**

**준비 (촬영 1시간 전 한 번):**
1. T1 터미널: `cd /c/Users/user/hackerton/arc/bridge && npm run dev` → "[bridge] listening" 확인
2. T2 터미널: `cd dashboard && npm run dev` → 브라우저 자동 열림
3. **페르소나 threshold 사전 설정** (필수!):
   ```bash
   curl -X POST http://localhost:3000/policy/persona \
     -H "Content-Type: application/json" \
     -d '{"exchangeId":"demo","label":"Demo (relaxed threshold)","feeRoundTrip":0.0005,"thresholdRate":0.0005,"supportsDualQuoteArb":true}'
   ```
4. T3 터미널: 데모 명령어 미리 입력만 (엔터 안 침)
   ```bash
   python -m demo.run_demo --symbols DOGE,XRP,SOL --duration 600 --speed 100 --threshold 0.0005 --fee-rate 0
   ```

**진행:**
1. S3 씬으로 전환
2. T3에서 데모 명령어 엔터 → 카운터 올라가기 시작
3. 보이스오버 (~75초, 카운터 보면서 자연스럽게):
   > "Three producer agents replaying real production data — the dual-quote feed is **a 1-second tape from my live v1.3 arbitrage bot, captured April 19**. Funding agent uses real Binance fapi data. Meta agent — Gemini 2.5 Flash — arbitrates conflicts weighted by each producer's hit rate. Every premium signal triggers a USDC settlement on Arc. Watch the counter."
4. 카운터가 raw=200+ 도달하면:
   > "Each settlement is variable-priced — confidence × notional × premium. Receipt is the market."
5. 대시보드 **Fee Persona Explorer** 클릭 → Bybit → Coinbase 변경 → demotion 카운터 변화 캡처
   > "Switch to Coinbase — no alt/USDT pairs, structurally arb-incompatible. The premium lane drops to zero. Persona drives the marketplace live."
6. 한 tx 클릭 → arcscan.app 탭 열림 (미리 북마크 필수)

**버그 방지:**
- 데모 시작 후 **첫 30초는 카운터가 0**일 수 있음 (producer warmup) — 이 구간엔 "you'll see signals start streaming in just a moment" 식으로 늘어뜨리기
- 만약 60초 지나도 raw=0 → 페르소나 setup 안 된 것. 컷하고 재시작
- 10분 런이지만 영상은 75초만 사용. 그 동안 카운터 30→100+ 변화 캡처

---

### 🎬 컷 4 (2:30-2:50) — Originality

**준비:**
- 슬라이드 7 (Originality) 미리 띄움
- VS Code로 `consumers/capital_allocator/main.py` 핵심 부분 (Q-update) 미리 스크롤

**진행:**
1. S2 씬 (슬라이드)으로 전환
2. 보이스오버:
   > "Variable on-chain price encodes signal quality. Outcome feedback retroactively re-prices future signals from the same producer. The Allocator sits above all of that — a learned meta-policy, not a threshold. It's a real market, not a cron job."
3. 2:45쯤 코드 잠깐 인서트 (5초)

---

### 🎬 컷 5 (2:50-3:00) — CTA

**준비:**
- S5 씬에 커버 이미지 + GitHub URL 큰 글씨 미리 배치
- `https://github.com/Leewonwuk/signal-mesh-arc`
- `https://signal-mesh.vercel.app`

**진행:**
1. S5 씬으로 전환
2. 보이스오버:
   > "Repo, live dashboard, product feedback — all linked in the submission. Signal Mesh on Arc. Thanks for judging."
3. 3:00에 페이드아웃

---

## 영상 2 — Transaction Flow (60초, 별도 파일)

요구사항: Circle Console 한 건 + Arc Explorer 검증

**준비:**
- 브라우저 탭 2개 미리: Circle Console / testnet.arcscan.app
- 송금할 액수: **0.01 USDC** (작게)

**진행:**
1. 0:00-0:15 — Circle Console 씬, executor_agent 지갑 잔고 표시 → "Send USDC" 버튼 → treasury 주소 붙여넣기
2. 0:15-0:30 — Pending 상태 표시 → tx hash 카피
3. 0:30-0:55 — testnet.arcscan.app 탭 → hash 붙여넣기 → ✅ Confirmed + USDC transfer 이벤트
4. 0:55-1:00 — End card

---

## 후처리 (편집)

- DaVinci Resolve 또는 macOS iMovie
- **3분 정확히 맞추기** — 초과하면 잘림 (lablab 규정)
- 컷 사이 1프레임 검은 화면 (선명한 트랜지션)
- 자막 ❌ (3분에 자막까지 만들 시간 없음, 보이스오버만)
- BGM 넣을 거면 -25dB로 깔기 (보이스오버 우선)

---

## 업로드 + 제출

1. YouTube **Unlisted** 업로드 (Public 아님)
2. 제목: `Signal Mesh on Arc — Lablab Hackathon Submission`
3. 설명: GitHub URL + dashboard URL
4. **링크 복사 → SUBMISSION 폼에 붙여넣기**

---

## 비상 폴백

| 상황 | 대응 |
|---|---|
| 데모 카운터 안 올라감 | 페르소나 setup 안 된 것. 컷하고 curl로 페르소나 POST 후 재시작 |
| Arc Explorer 검색 안 됨 | testnet.arcscan.app/address/{wallet} URL로 직접 이동 |
| 페르소나 스왑 시연이 너무 빨라서 흐릿 | 컷에서 5초 정지(freeze frame) 추가 |
| 영상이 3분 초과 | 컷 2 (슬라이드)를 30초 → 20초로 압축 |
| 마이크 안 됨 | 컷 4 보이스오버를 컷 3와 합쳐서 부담 줄이기 |
