# Submission Requirements — lablab.ai Agentic Economy on Arc

## Judging Criteria (4 axes, equal weight assumed)

1. **Application of Technology** — how effectively chosen models are integrated
2. **Presentation** — clarity & effectiveness of project presentation
3. **Business Value** — impact & practical value, business-area fit
4. **Originality** — uniqueness & creativity

> ⚠️ **"50+ onchain tx" is a REQUIREMENT, not a judging axis.** Don't optimize for tx count beyond the minimum; optimize for the 4 axes above.

---

## Required submission components

### 📋 Basic info
- [ ] Project Title: **Signal Mesh on Arc**
- [ ] Short Description (1-liner)
- [ ] Long Description
- [ ] Technology & Category Tags

### 📸 Presentation assets
- [ ] **Cover Image**
- [ ] **Video Presentation** (pitch + demo)
- [ ] **Slide Presentation**

### 💻 Code & deployment
- [ ] **Public GitHub Repository**
- [ ] **Demo Application Platform** (hosted)
- [ ] **Application URL** (live link)

### 📝 Circle Product Feedback (REQUIRED + $500 USDC bonus eligibility)
Must include:
- [ ] Which Circle products used (Arc, USDC, Circle Wallets, Circle Gateway, CCTP/Bridge Kit, Nanopayments)
- [ ] **Why** chosen for the use case
- [ ] What worked well
- [ ] What could be improved
- [ ] Recommendations for DX / scalability

### 📸 Transaction Flow Demonstration Video (REQUIRED)
Must clearly show:
- [ ] **Transaction executed via Circle Developer Console**
- [ ] **Verification of that transaction on Arc Block Explorer**

### ✅ Technical requirements
- [ ] per-action pricing **≤ $0.01**
- [ ] **50+ onchain transactions** in demo
- [ ] **Margin explanation**: why traditional gas would kill this model
- [ ] Clearly state **challenge track** participated in
- [ ] Clearly state **Circle products used**

---

## Mapping to our project

| Requirement | Our deliverable |
|---|---|
| Cover Image | Signal Mesh architecture diagram (stylized) |
| Video Presentation | 3-min pitch + live demo |
| Slide Presentation | 10-12 slides (problem / solution / tech / margin / demo / roadmap) |
| Demo App URL | Vercel-hosted React dashboard showing live tx stream |
| Circle Developer Console video | Screen-record of console issuing one USDC tx + Arc explorer verification |
| 50+ tx | Demo driver runs 60 signals through meta + executor consumers |
| Track | **🤖 Agent-to-Agent Payment Loop** (primary) + secondary fit to 🪙 Per-API Monetization |

---

## Video Guidance (from lablab.ai official tutorial)

Source: `C:\Users\user\trading\arb\youtube_VKgOh0rKjSM_상세요약.md`

- **Format**: MP4 upload
- **Length**: ≤ 5 minutes (concise pitch)
- **Must include**:
  - Problem / Solution
  - Project structure
  - Technologies used
  - Team (optional)
  - Business plan / monetization (recommended)
  - **Live demo** (non-negotiable)
- **Editing tips**:
  - Remove silence / dead air
  - Don't over-accelerate (audio quality drops)
- **Slides**: separate PDF, 6~10 slides, compressed version of structure/tech/team/business
- **Tags**: fill Categories + Technologies Used accurately (discovery + judge framing)
- **GitHub**: public preferred; private OK but grant judge access. **Scrub API keys / secrets** before submit.
- **Demo URL**: must actually work when clicked

### Common submission mistakes to avoid
1. Lazy or missing tags/categories
2. No live demo in video
3. Broken / gated demo link
4. Private repo without judge access
5. Leaked API keys in code
6. Rambling video, slow to the point

---

## Critical Tool: Circle Developer Console

The required video explicitly names **Circle Developer Console** as the tool through which at least one tx must be executed. This is not optional — judges validate on-chain execution via this + Arc Block Explorer. Integration plan must include:

1. Create Circle Developer account
2. Provision Arc testnet wallet via Developer Console
3. Execute at least one signal-settlement tx from the Console UI (can be recorded separately from the main demo)
4. Screenshot + link the tx on Arc Block Explorer
