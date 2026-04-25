# AlphaLoop — 녹화 + 제출 체크리스트 (2026-04-24 작성, rev 2)

> **마감**: 2026-04-26 (일) 09:00 KST (= 2026-04-25 17:00 PT)
> **기준점**: 2026-04-24 22:40 KST 작성, 23:00 KST rev 2 (deck revision 2 반영)
> **권장 제출 시각**: 2026-04-25 23:00 KST (버퍼 10h)
> **Claude Code 태스크 트래커**: #22~#33 (12 tasks)

---

## 🗺 Phase-Gated 실행 흐름

```
PHASE 0: Deck revision (현재)
  ├── ✅ SLIDES_v2.md revision 2 완료 (9 critical edits baked in)
  └── 🔜 사용자 → Claude Design 재의뢰 (Task #22)
      │
      ▼
PHASE 1: Deck 검증 (Task #23)
  ├── margin counterfactual box 렌더됨?
  ├── Slide 8 error bar 실제 있거나 캡션 삭제됨?
  ├── Slide 11 hero + chips 구조?
  └── 150 / 0xb276… / 400039d5… 숫자 정확?
      │
      ▼
PHASE 2: 녹화 준비 + 녹화 (Task #24~#26)
  ├── cueboard §0 T-32~T-0 준비
  ├── Video 1 녹화 (3분 피치+데모)
  └── Video 2 녹화 (Circle Console+Arcscan, ≤60s)
      │
      ▼
PHASE 3: 업로드 + 제출 (Task #27~#28)
  ├── YouTube Unlisted × 2
  ├── lablab.ai 폼 Save Draft (dry-run)
  └── Submit (권장 4/25 23:00 KST)
      │
      ▼
PHASE 4: 후순위 정리 (Task #29~#33)
  ├── [A] 레거시 파일 삭제 (135MB)
  ├── [B] Vercel memory rename (alphaloop)
  ├── [C] CLAUDE.md §3 Tufte + Duarte 추가
  ├── [D] Stale memory 4개 삭제
  └── [E·선택] secrets 파일 이동
```

---

## ✅ 이미 완료된 것 (판사 검증 가능)

### 코드 / 인프라
- [x] **AlphaLoop 브랜드 전면 적용** (repo legacy URL `signal-mesh-arc` / `signal-mesh.vercel.app`는 의도적 유지)
- [x] **150 variably-priced USDC settlements** 배치 완료 (`scripts/circle_batch_settle.js`)
- [x] **Merkle root** over 150 tx = `400039d5af1f5ea1ab6ee6068df6274d2b360f523b63b545e88e03aa06605b80`
- [x] `scripts/build_merkle_root.py` + `make verify` 원클릭 검증
- [x] **ERC-8004 Registry 배포** = `0xb276b96f2da05c46b60d4b38e9beaf7d3355b7ab` on Arc testnet chainId 5042002
- [x] **소스 검증** (Arcscan Blockscout API — `is_fully_verified: true`)
- [x] **4개 AgentRegistered 이벤트** on-chain (content-addressed sha256 of agent cards)
  - producer_dual_quote: `0xa9c5…3a93`
  - producer_kimchi: `0xc8e3…93c2ff` (재등록 후 성공)
  - meta_agent: `0x9c8d…7101`
  - executor_agent: `0x70ac…d26ab`
- [x] **ERC-8004 agent cards × 4** Vercel 정적 서빙
- [x] **MIT LICENSE** 루트
- [x] Dashboard 5 새 컴포넌트 (Req bar / ProductionAnchor / WhyArc / FeeMatrix / AgentIdentityCard)
- [x] scaffold banner (Vercel scaffold 모드 disclosure)
- [x] 코드 리뷰 버그 픽스 (H1 scaffold flicker, Python CTRL+C)

### 문서
- [x] `README.md` STATUS 섹션 (verify in 60 seconds)
- [x] `docs/SUBMISSION.md` — TL;DR + §5 Circle products (ERC-8004 + Compliance Agent) + §11.c Honest Reporting
- [x] `docs/PRODUCT_FEEDBACK.md` — 7 pain points + Gateway observation
- [x] `docs/SLIDES_v2.md` — Claude Design 핸드오프용 spec (578 lines, ground-truth 표 포함)
- [x] `docs/alphaloop_lablab_submission_draft_260424.md` — lablab 폼 copy-paste draft
- [x] `docs/VIDEO_SCRIPT_KR.md` — 녹화 스크립트 (150 tx + ERC-8004 내레이션)
- [x] `docs/arc_녹화cueboard_260424.md` — 녹화 cue (T-32 bridge kill, T-28 demo persona, T-5 Bybit)
- [x] `Makefile` — make verify / demo / batch / persona-demo / persona-bybit / pre-record
- [x] `docs/cover_image.svg` — AlphaLoop 리브랜드
- [x] `docs/SLIDES_v1_archived.{md,pdf}` — 구 v1 아카이브
- [x] Notion cueboard 페이지 업데이트

### 전역 규약
- [x] `~/.claude/CLAUDE.md` §4 "선행 구현 적극 활용" 규약 추가
- [x] `memory/feedback_prior_work_mining.md` 신설

### 라이브 URL 검증
- [x] `https://signal-mesh.vercel.app` → HTTP 200
- [x] `https://signal-mesh.vercel.app/scoreboard.html` → HTTP 200
- [x] `https://signal-mesh.vercel.app/.well-known/agent-card/{role}.json × 4` → HTTP 200
- [x] `https://testnet.arcscan.app/address/0xb276b96f…b7ab` — verified source
- [x] 5개 tx hashes all `status: success` on Arcscan

---

## 🎬 녹화 전 30분 체크리스트 (내일 오후)

### 사전 환경 (T-32 ~ T-15)

- [ ] **T-32** Bridge kill: `netstat -ano | findstr :3000` → `taskkill /F /PID <pid>` (stale tx + mojibake persona 제거)
- [ ] **T-30** Bridge 재기동: `make bridge` (또는 `cd bridge && npm run dev`)
- [ ] **T-29** Dashboard 재기동: `make dashboard`
- [ ] **T-28** DEMO persona warmup: `make persona-demo` (0.05% threshold, ASCII label)
- [ ] **T-25** 브라우저에서 `http://localhost:5173` 열기
- [ ] **T-20** Demo 드라이버 실행: `make demo`
- [ ] **T-15** Allocator tick 3-5회 + `pre_record_check.sh` ALL PASSED 확인
- [ ] **T-12** Dress rehearsal: `node scripts/circle_batch_settle.js --count 30 --rate 3` (1.5분 스모크)
- [ ] **T-10** SLIDES 풀스크린 준비
- [ ] **T-5** Bybit persona 스위치: `make persona-bybit`
- [ ] **T-4** `testnet.arcscan.app` 빈 탭 준비
- [ ] **T-3** OBS 5-scene + 마이크 + 배경소음 체크
- [ ] **T-1** 심호흡 + 물 한 모금

### Gemini 상태 재확인 (필수)
- [ ] `tail -3 demo/logs/meta.log`
- [ ] "gemini failed" 없으면 스크립트 원문
- [ ] 여전히 503이면 1:50 내레이션 "with a local deterministic stub fallback" 부분 강조

### 녹화 직전 시각 점검 (localhost:5173)
- [ ] RequirementsBadge 6개 chip 모두 green/met
- [ ] ProductionAnchor `v1.3 EC2 bot · 9 coins · pool $1,977 USDT`
- [ ] WhyArcCard `-$0.002 / +$0.003` 양쪽 표시
- [ ] AgentIdentityCard — registry addr + source verified 태그 + 4 row
- [ ] FeeMatrix 3 coin × 5 venue 표 렌더
- [ ] Policy Heatmap 최소 2-3 칸 색 입력됨

---

## 🎥 녹화 (2 영상)

### Video 1 (3:00 하드컷, 피치 + 데모)
- [ ] **Script**: `docs/VIDEO_SCRIPT_KR.md` 따라 읽기
- [ ] **Cues**: 0:05 / 0:30 / 1:15 / 2:00 / 2:50
- [ ] 1:18 시점 터미널에 `node scripts/circle_batch_settle.js --count 150 --rate 3` 엔터
- [ ] ⚠️ `circle_batch_settle.js:39` `AMOUNT_MIN=0.0005` 등 상수 화면에 노출 금지
- [ ] 리허설 3회 후 실전 녹화

### Video 2 (≤60s, Circle Developer Console + Arc Explorer)
- [ ] Circle Console → `producer_kimchi` wallet 열기
- [ ] Send 클릭 → meta_agent 주소 `0xf8f1ae7b…` → Amount 0.01 USDC → Submit
- [ ] tx hash 복사
- [ ] `testnet.arcscan.app` 새 탭 → hash 붙여넣기
- [ ] 블록 + token transfer event 보여주기
- [ ] 클로징: "The full demo runs 150 variably-priced of these through the AlphaLoop pipeline"

### 편집
- [ ] 컷 5군데 (0:05 / 0:30 / 1:15 / 2:00 / 2:50)
- [ ] 긴 침묵 (2초+) 자르기
- [ ] **영어 자막 필수**
- [ ] 끝 2초 침묵 → 하드컷

---

## 📄 발표 자료 (Claude Design 의뢰)

- [ ] `docs/SLIDES_v2.md` 전체 내용 복사
- [ ] Claude Design 새 대화 → 붙여넣기
- [ ] 프롬프트: *"이 brief대로 12-slide PDF 생성해줘. 파일명 `AlphaLoop_Deck.pdf`. 1920×1080 16:9. 폰트 Inter + JetBrains Mono. 다크 테마."*
- [ ] 결과 PDF를 `docs/AlphaLoop_Deck.pdf`로 저장
- [ ] ⚠️ 12 페이지 정확히 나왔는지 확인
- [ ] 혹시 실패하면 대체: `SLIDES_v1_archived.pdf` 수동 수정 (마지막 수단)

---

## ☁️ YouTube 업로드

### Video 1 (Pitch + Demo)
- [ ] 제목: `AlphaLoop — Agentic Economy on Arc Hackathon Submission (Track 2: Agent-to-Agent Payment Loop)`
- [ ] 공개 설정: **Unlisted** (Public 아님)
- [ ] 설명란:
  ```
  AlphaLoop: the agent-to-agent alpha loop on Arc. Four specialist trading
  agents pay each other sub-cent USDC (variable $0.0005–$0.010),
  backed by a live v1.3 production arb bot running on EC2.

  Track: Agent-to-Agent Payment Loop
  Dashboard: https://signal-mesh.vercel.app
  Scoreboard: https://signal-mesh.vercel.app/scoreboard.html
  GitHub: https://github.com/Leewonwuk/signal-mesh-arc
  Registry: https://testnet.arcscan.app/address/0xb276b96f2da05c46b60d4b38e9beaf7d3355b7ab
  ```
- [ ] ⚠️ **BGM 없이 업로드** (Copyright flag 회피)
- [ ] URL 복사

### Video 2 (Console tx)
- [ ] 제목: `AlphaLoop — Circle Developer Console + Arc Explorer Verification (≤60s)`
- [ ] Unlisted
- [ ] URL 복사

---

## 📝 lablab.ai 제출

### 사전 (녹화 전 or 녹화 후)
- [ ] lablab.ai 계정 로그인
- [ ] Submit Project 폼 열기
- [ ] **Save Draft** 먼저 (폼 호환성 dry-run) — 어떤 필드 있는지 확인

### 폼 필드 (`docs/alphaloop_lablab_submission_draft_260424.md` 참조)

- [ ] Project Title: `AlphaLoop — the agent-to-agent alpha loop on Arc`
- [ ] Short Description: 1-liner 붙여넣기
- [ ] Long Description: 5-bullet 버전 붙여넣기
- [ ] Technology & Category Tags: `Arc · USDC · Circle Wallets · Developer API · x402 · Gemini · React · TypeScript · Python · Q-learning · RL · Algorithmic Trading · EIP-3009 · ERC-8004 · MIT`
- [ ] Cover Image: `docs/cover_image.svg` 업로드 (SVG 미지원 시 PNG 변환)
- [ ] Video Presentation: Video 1 YouTube URL
- [ ] Slide Presentation: `docs/AlphaLoop_Deck.pdf`
- [ ] GitHub Repository: `https://github.com/Leewonwuk/signal-mesh-arc` (Public 확인)
- [ ] Demo Application Platform: `Vercel`
- [ ] Application URL: `https://signal-mesh.vercel.app`
- [ ] **Circle Product Feedback** 필드: `docs/PRODUCT_FEEDBACK.md` 본문 붙여넣기
- [ ] Transaction Flow Demo Video: Video 2 YouTube URL
- [ ] Track: `🤖 Agent-to-Agent Payment Loop`

### 제출 직전 최종 체크

- [ ] Application URL 클릭 → HTTP 200 확인
- [ ] Video 1 Unlisted URL 동료 계정으로 테스트 (재생 가능?)
- [ ] Video 2 Unlisted URL 동일 테스트
- [ ] GitHub repo Public 상태?
- [ ] LICENSE 파일 있음? (repo 랜딩에 "MIT" 배지 표시)
- [ ] `docs/evidence/batch_tx_hashes.txt` 첫 hash 클릭 → Arcscan 확인
- [ ] Registry contract 주소 Arcscan에서 "Code" 탭 볼 수 있는지

### Submit

- [ ] **Save Draft** 한 번 더 (최종 저장)
- [ ] Submit 버튼 클릭
- [ ] 확인 메일 수신 확인
- [ ] Discord/Slack으로 제출 인증 확인 가능하면 인증

---

## 🚨 비상 시 대응

| 상황 | 대응 |
|---|---|
| Circle API batch 중 FAIL | `Let me continue with the existing tx history` — evidence file 150 records로 이미 landed |
| Dashboard 빈 화면 (localhost) | Bridge 재시작 → F5 |
| Gemini 503 | 1:50 내레이션에 "with a local stub fallback" 강조, stub 자체가 premium 생성 |
| 3분 초과 | 0:30-0:50 문제 슬라이드 10초로 압축 |
| signal-mesh.vercel.app 4xx | Vercel 상태 페이지 확인 → 재배포 `cd dashboard && vercel --prod && vercel alias set ...` |
| YouTube 업로드 Copyright | BGM 없이 재업로드 |
| SLIDES Claude Design 실패 | 마지막 수단: Google Slides 수동으로 4-5슬라이드 축약 |
| kimchi tx on-chain 이상 | `bridge/scripts/reregister_kimchi.js` 재실행 (gas=350000 고정) |

---

## 📊 Critical Facts Reference Sheet (녹화 중 혹시 질문 받으면)

| | |
|---|---|
| Project | **AlphaLoop** |
| Track | 🤖 Agent-to-Agent Payment Loop |
| Chain | Arc testnet (chainId 5042002) |
| Tx count | 150 + 5 ERC-8004 (1 deploy + 4 register) |
| Pricing range | $0.0005 – $0.010 (60/30/10 tier) |
| Registry contract | `0xb276b96f2da05c46b60d4b38e9beaf7d3355b7ab` |
| Merkle root | `400039d5af1f5ea1ab6ee6068df6274d2b360f523b63b545e88e03aa06605b80` |
| v1.3 coins (9) | ADA · BNB · DOGE · SOL · TRX · XRP · APT · FET · WLD |
| Demo subset | DOGE · XRP · SOL |
| Walk-forward | TrainedQ $7.61 · ALL_V2 $9.44 (p=0.49) · DIVERSIFY $1.60 (p=0.012) |
| Repo | github.com/Leewonwuk/signal-mesh-arc |
| Dashboard | signal-mesh.vercel.app |
| Scoreboard | signal-mesh.vercel.app/scoreboard.html |
| License | MIT |

---

## 💤 제출 후

- [ ] 확인 메일 도착 / lablab 페이지에서 내 submission 공개 확인
- [ ] Discord 해커톤 채널에 인증 코멘트 (선택)
- [ ] 결과 발표 (2026-04-27 07:00 KST = 4/26 15:00 PT, Live Winners stream) 대기
- [ ] 수상 여부 관계없이 경험 회고 — 이 md + 메모리로 다음 해커톤 refine

---

## 🔄 Post-Deck 재의뢰 흐름 (PHASE 0→1)

### Task #22 — Claude Design 재의뢰

**입력**: `docs/SLIDES_v2.md` (rev 2, 상단에 🔄 REVISION REQUEST 블록 포함)

**프롬프트 예시** (Claude Design 새 대화에 붙여넣기):

> 이 revision 2대로 AlphaLoop deck 재생성해줘.
> - 파일명: `AlphaLoop_Deck.html` 덮어쓰기
> - 1920×1080 16:9, 12 pages
> - 폰트 Inter + JetBrains Mono, 다크 테마
> - §8 "Designer self-check" 8개 checkbox 모두 통과 확인 후 반환

**반환물 저장 위치**: `C:\Users\user\hackerton\arc\AlphaLoop_Deck.html`

### Task #23 — Deck 검증

반환받은 HTML 열어서 아래 확인:

- [ ] **Slide 1 (Cover)** v1.3 credential 서브라인 있음? repo rename disclosure 11pt로?
- [ ] **Slide 3 (Problem)** 펀치라인 1.4× bold? **정량 margin box** (Ethereum -$0.495 / Polygon 0 / Arc +$0.003) 렌더됨?
- [ ] **Slide 5 (Architecture)** 아이콘 2색만? (cyan+purple, 4색 아님)
- [ ] **Slide 8 (Backtest)** 헤드라인 "A blind agent matched the oracle that cheated"?
- [ ] **Slide 8** error bar 실제 whisker OR 캡션 삭제?
- [ ] **Slide 8** Round 1 드라마 **full-width 콜아웃 카드** (footer 태그 아님)?
- [ ] **Slide 10 (Circle)** 3 failure modes 단일 line + `SUBMISSION.md §5` 링크?
- [ ] **Slide 11 (Originality)** 1 hero (ERC-8004) + 3 chips 구조?
- [ ] **Slide 12 (Close)** pause-beat (40px 공백)? GitHub 컬럼 아래 rename disclosure?

이상 있으면 → 어느 항목 이상인지 지적 → 제게 말하면 SLIDES_v2.md에서 해당 부분 refine 후 재의뢰.

---

## 🛠 [후순위] Phase 4 — 제출 후 정리

**⚠ 제출 완료 전에는 건드리지 않음.** 제출 후 or deck 확정 후 원샷 실행.

### 후순위 A — 레거시 파일 삭제 (135MB 회수) · Task #29

```bash
cd /c/Users/user/hackerton/arc
rm -f SignalMesh_on_Arc_Deck.html SignalMesh_on_Arc_Deck.html.bak \
      submission_pdf.pdf recovery_file_2026-04-21.dat \
      docs/SignalMesh_on_Arc_Deck_v2.pdf
git worktree remove --force .claude/worktrees/cool-satoshi-0a3874
git worktree prune
```

### 후순위 B — Vercel memory rename · Task #30
- `memory/reference_vercel_signal_mesh.md` → `reference_vercel_alphaloop.md`
- 내용: 프로젝트명 AlphaLoop, ERC-8004 registry 배포(0xb276…b7ab), Arcscan verified 사실, agent cards 경로 추가
- `MEMORY.md` 인덱스 라인 병행 업데이트

### 후순위 C — Giants에 Tufte + Duarte 추가 · Task #31
- `~/.claude/CLAUDE.md` §3 제출 국면 5인 → 7인
- 추가 이유: 이번 deck 리뷰에서 Tufte가 error bar honesty 지적, Duarte가 slide density 지적 → 기존 5인 (PG/Tan/Karpathy/Vitalik/Beck)엔 디자인/시각 렌즈 없음
- `memory/feedback_giants_shoulders_arb.md` 동기화

### 후순위 D — Stale memory 4개 삭제 · Task #32
- `project_v12_status.md` (13일 전)
- `project_v121_next_steps.md` (17일 전)
- `project_hotsprings_v02.md`, `project_hotsprings_v03.md` (v031으로 대체됨)
- MEMORY.md 인덱스 라인 동시 제거

### 후순위 E (선택) — Secrets 파일 이동 · Task #33
- `circle_secrets.txt`, `gemini_api_key.txt` → repo root에서 `~/.claude/` 또는 별도 위치로 이동
- `.gitignore` 커밋 방지는 이미 있지만 root 배치 자체가 위생 안 좋음
- 이미 `.env`에 동일 값 있는지 먼저 확인 → 있으면 삭제, 없으면 이동
- deprecated인지 사용자 판단 필요

---

## 📋 Claude Code 태스크 트래커 현재 상태

모든 pending 액션은 `/tasks`로 확인 가능 (예상 상태):

| # | 상태 | 항목 |
|---|---|---|
| 22 | pending | [사용자] Claude Design 재의뢰 |
| 23 | pending | [사용자] 재생성 deck 검증 |
| 24 | pending | [사용자] 녹화 전 30분 준비 |
| 25 | pending | [사용자] Video 1 녹화 |
| 26 | pending | [사용자] Video 2 녹화 |
| 27 | pending | [사용자] YouTube × 2 업로드 |
| 28 | pending | [사용자] lablab 제출 폼 |
| 29 | pending | [후순위 A] 레거시 삭제 |
| 30 | pending | [후순위 B] Vercel memory rename |
| 31 | pending | [후순위 C] Giants Tufte+Duarte 추가 |
| 32 | pending | [후순위 D] Stale memory 삭제 |
| 33 | pending | [후순위 E·선택] secrets 이동 |

---

**끝. 화이팅. 🏆**
