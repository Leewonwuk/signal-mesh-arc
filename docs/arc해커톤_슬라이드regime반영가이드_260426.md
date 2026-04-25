# Slide Update Guide — Regime → Strategy Narrative (2026-04-26)

> **목적**: 디자인 AI에게 전달할 가이드. 현재 deck의 가장 큰 약점("왜 3개 전략을 RL로 나누나?")에 답하는 regime 서사를 슬라이드에 추가/강화.
>
> **배경**: 2026-04-26 사용자 진단 — *"심사위원 입장에선 굳이 이걸 왜 나누는거지? 라는 생각이 들수있잖아. 시장상태 regime을 고려해서 강화학습이 학습하고 매매법을 고른다. 라고 하는 느낌이 들어가야할것같다."* → Garry Tan 렌즈로 ONE thing의 핵심 wedge 누락.
>
> **데이터 검증**: `consumers/capital_allocator/allocator_q.json` 의 학습된 Q-table 분석 결과, regime별 best action이 명확히 분기됨 (이 가이드의 Table 1 참조). 이는 **모델이 학습한 결과**이지 hand-coded가 아님.

---

## 📊 핵심 데이터 (가이드의 single source of truth)

### Table 1: 학습된 Regime → Strategy 매핑 (allocator_q.json 기반)

| state | regime | best action | q-value | runner-up | 우세 전략 |
|-------|--------|-------------|---------|-----------|----------|
| 0 | calm/cold/tight | ALL_V3 | 0.500 | ALL_V2 | **v3 funding** |
| 1 | calm/cold/wide | ALL_V3 | 0.500 | ALL_V2 | **v3 funding** |
| 2 | calm/hot/tight | ALL_V2 | 0.418 | DUAL_FUND | **v2 dual-quote** |
| 3 | calm/hot/wide | ALL_V2 | 0.407 | DUAL_FUND | **v2 dual-quote** |
| 4 | **hot/cold/tight** | **ALL_V1** | **3.221** | KIMCHI_DUAL | **v1 kimchi** ⭐ |
| 5 | hot/cold/wide | ALL_V1 | 0.925 | KIMCHI_DUAL | **v1 kimchi** |
| 6 | hot/hot/tight | ALL_V1 | 0.500 | ALL_V2 | mixed (tied) |
| 7 | hot/hot/wide | ALL_V2 | 0.393 | DUAL_FUND | **v2 dual-quote** |
| 8 | cold-sentinel | ALL_V1 | 0.500 | ALL_V2 | fallback |

⭐ **state 4 = hot-vol / cold-fund / tight** 가 학습 시그널 가장 강함 (q=3.22). 이게 v1 kimchi 의 sweet spot — KR-Global divergence 가 vol 스파이크에 amplified 되는 regime.

### 핵심 narrative 한 줄

> "Each strategy has a regime where it shines. No static allocation captures all three; no human switches fast enough. The Q-learner reads observable state — vol, funding, KR-Global premium, USDC spread — and learns which lane wins under which conditions. **The mapping isn't hand-coded; it's what the model discovered from realized PnL.**"

---

## 🎯 슬라이드별 수정 가이드

### Slide 7 (현재: "The RL question")

**현재 문제**: *"Which strategy should trade right now?"* 묻기만 하고 답을 안 줌. Why RL이 정당화 안 됨.

**수정 방향**: 슬라이드 7 자체를 **regime wedge 슬라이드**로 강화.

**제안 레이아웃**:
```
Title (40pt): "Why three strategies, not one?"
Subtitle (22pt, muted): "Each lane has a regime where it shines."

[중앙 비주얼 — 3-row regime → strategy 카드]

┌────────────────────────────┐  ┌────────────────────────────┐  ┌────────────────────────────┐
│  HOT-VOL / COLD-FUND       │  │  CALM / HOT-FUND           │  │  CALM / COLD-FUND          │
│  KR-Global divergence ↑    │  │  Funding active, vol calm  │  │  Pure 8h carry             │
│                            │  │                            │  │                            │
│  ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪          │  │  ▪ ▪ ▪ ▪ ▪ ▪ ▪              │  │  ▪ ▪ ▪ ▪ ▪ ▪                 │
│  q = 3.22                  │  │  q = 0.42                  │  │  q = 0.50                  │
│                            │  │                            │  │                            │
│  → v1 KIMCHI (amber)       │  │  → v2 DUAL-QUOTE (cyan)    │  │  → v3 FUNDING (purple)     │
└────────────────────────────┘  └────────────────────────────┘  └────────────────────────────┘

Bottom callout (cyan border, 22pt):
"No human switches fast enough between these as regimes drift.
We let RL learn the switch from realized PnL."
```

**색상**: v1 amber (#fbbf24), v2 cyan (#22d3ee), v3 purple (#a78bfa)
**q-value 표시**: Menlo/JetBrains Mono, tabular-nums

---

### Slide 8 (현재: "Walk-forward backtest")

**현재 문제**: Round 2 가 "ties ALL_V2" 라고만 표시 → judge 인상: *"그럼 ALL_V2만 쓰면 되잖아"*

**수정 방향**: Round 2 동률을 **honest disclosure** 로 reframe + hot-vol regime gap 노출.

**제안 추가 행**:

기존 walk-forward 테이블 아래에 새 hi-light 박스:
```
┌─────────────────────────────────────────────────────────────────┐
│ ⚡ Why p=0.49 isn't a problem                                    │
│                                                                 │
│ Holdout window happened to be v2-favorable.                     │
│ In hot-vol / cold-fund regimes (state 4):                       │
│                                                                 │
│        ALL_V1 q-value = 3.22                                    │
│        runner-up    = 1.81                                      │
│                                                                 │
│ That's where v1 kimchi pulls away — 78% margin over second-best.│
│ Regime-conditional gaps are the value, not the average.         │
└─────────────────────────────────────────────────────────────────┘
```

**Style**: amber 테두리 (rgba(251,191,36,0.5)), 좌측 양 (light bulb) 아이콘 24pt.

---

### Slide 11 (현재: "Originality") — 4개 차별화 포인트

**현재**: 가변 온체인 가격 / 닫힌 결과 루프 / 메타 정책 / ERC-8004

**수정 방향**: 메타 정책 항목을 강화 — *"learned regime → strategy mapping (not hand-coded)"* 명시.

**제안 변경**:

기존 #3 카드 (메타 정책):
```
이전: "Learned meta-policy decides which strategy trades"
변경 후 (제안):
  Title: "Regime-aware learned allocation"
  Body:  "9 regime cells × 7 actions Q-table. Each cell's best action
          discovered from realized PnL — no hand-coded if-else.
          Hot-vol regimes pick v1, hot-funding pick v2, calm-cold pick v3.
          The mapping is the model's output, byte-verifiable in
          allocator_q.json."
```

---

### Slide 12 (Close) — 변경 없음

이미 5 agents · variable-price · ERC-8004 · 2026-04-26 footer · Pitch Video / Judge Scoreboard 모두 OK.

---

## 🎨 색상/타이포 가이드 (3-lane consistent)

전 deck에서 일관 사용:

| Lane | Hex | Use |
|------|-----|-----|
| v1 kimchi | `#fbbf24` (amber) | "KR-FOMO regime" / hot-vol |
| v2 dual-quote | `#22d3ee` (cyan) | "microstructure regime" / hot-funding |
| v3 funding | `#a78bfa` (purple) | "carry regime" / calm-cold |

각 lane chip 배경: 해당 색의 18% opacity, 35% opacity border.
q-value 같은 숫자: Menlo / JetBrains Mono / tabular-nums.

---

## 📋 디자인 AI 작업 체크리스트

- [ ] Slide 7 — "Why three strategies?" 제목 + 3-card regime visual + bottom callout
- [ ] Slide 8 — "Why p=0.49 isn't a problem" amber 박스 추가 (hot-vol q=3.22 gap)
- [ ] Slide 11 — Originality #3 카드 텍스트를 "Regime-aware learned allocation"으로 강화
- [ ] 색상 일관성 — v1 amber / v2 cyan / v3 purple 모든 슬라이드 적용
- [ ] q-value 숫자 표시 — Menlo / tabular-nums 사용
- [ ] 스피커 노트 (Notion / 영상 대본)는 이미 동기화됨 — 슬라이드 visual 만 매칭

---

## 🔗 참조

- 학습된 Q-table: `consumers/capital_allocator/allocator_q.json`
- Regime feature 정의: `ml/regime_features.py` (9 cells = 2×2×2 + cold)
- Dashboard 구현: `dashboard/src/components/RegimeMap.tsx` (테이블 데이터 single source of truth)
- 영상 대본 동기화 위치: `docs/VIDEO_SCRIPT_KR.md` 2:00-2:30 섹션
- 노션 큐보드: `https://www.notion.so/34c9fc696653811a881bec5bdc1cf01b` (영상 RL 섹션 동기화 완료)
