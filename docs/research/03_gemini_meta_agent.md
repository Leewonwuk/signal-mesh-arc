# Gemini / Meta Agent Design (Team Member 3 Output)

> Produced by research agent, 2026-04-21

## 🚨 Bombshell: $40k GCP bonus does NOT apply to our event

- The $40k GCP / Google DeepMind track was for **"Agentic Commerce on Arc" (Jan 9–24, 2026)** — a previous event.
- Our event: **"Agentic Economy on Arc" (Apr 20–26, 2026)** — **Circle only**, **$10,000 prize pool** + **$500 USDC feedback incentive**. No Google sponsorship.
- **Plan around $10k, not $40k.** Don't mention Google DeepMind in the pitch.

## Gemini API practical setup

- **SDK**: `google-genai` (old `google-generativeai` deprecated). `pip install -U google-genai`
- **Key signup**: **Google AI Studio** (aistudio.google.com). Vertex AI overkill for 4-day prototype
- **Free tier (2026)**: Flash ≈ 10 RPM / 250 RPD, Flash-Lite ≈ 15 RPM / 1,000 RPD, Pro ≈ 5 RPM / 100 RPD
- **Pro leaves free tier 2026-04-01** — paid-only for our event
- **Recommended model**: `gemini-2.5-flash` for Meta Agent (fast, cheap, native structured output)
- **50-call demo cost (paid Flash)**: ~$0.0325 (3 cents). Non-issue.

## ★ Meta Agent — pivot to cross-producer conflict resolution

**NOT** "summarize signal in natural language" (cosmetic).
**YES** — resolve contradictions between Kimchi and Dual-Quote on USDT fair value:
- Kimchi: "buy USDT via KRW premium" (USDT undervalued)
- Dual-Quote: "USDT is rich vs USDC on Binance" (USDT overvalued)
- Gemini emits `net_stance` + `dominant_leg` + reasoning

This directly justifies the 5× price jump ($0.002 → $0.01) and showcases **marketplace composition** (the real originality driver).

## Prompt design

System:
```
You are a trading-signal arbiter. Inputs: time-ordered window of raw signals
from two producers (kimchi: KRW/USDT premium; dualquote: USDT/USDC on Binance).
Output ONE JSON object matching the schema. No prose.
Fields:
  regime ∈ {trending, mean_reverting, choppy},
  confidence ∈ [0,1],
  justification (<=200 chars),
  recommended_action (<=80 chars, imperative)
Resolve conflicts: if two producers imply opposite USDT fair-value moves,
state which leg dominates and why.
```

User (templated):
```
Window (last 30s):
{"t":0,"src":"kimchi","pair":"KRW/USDT","spread_bps":42,"side":"buy_usdt"}
{"t":3,"src":"dualquote","pair":"USDT/USDC","spread_bps":-8,"side":"sell_usdt"}
...
Return JSON only.
```

## Structured output (native schema)

```python
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import Literal

class MetaSignal(BaseModel):
    regime: Literal["trending", "mean_reverting", "choppy"]
    confidence: float
    justification: str
    recommended_action: str

client = genai.Client(api_key=API_KEY)
resp = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[system_prompt, user_window],
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=MetaSignal,
        temperature=0.2,
    ),
)
signal: MetaSignal = resp.parsed
```

## Token budget

50 calls × 700 tokens = 35k tokens over 2min. TPM trivial (12.5k vs 250k cap). **RPM kills free tier**: 25 RPM > 10 RPM limit. Options:
- Flash-Lite (15 RPM, still too low for burst) — batch 2 windows/call
- **Pay tier-1 (~3 cents for demo)** ← recommended
- Pre-compute 30 responses before demo (fragile)

## ★ Judging reality check — honest

**Gemini alone = LLM decoration** for this domain. Judges have seen 100 "LLM summarizes X" projects.

**The originality driver = A2A nanopayment marketplace + cross-producer composition, NOT the LLM.**

### Killer idea: sklearn GBM regime classifier

Train on user's **actual v1.1/v1.3 historical log data** → unique data-scientist angle most hackathon teams can't replicate. Use GBM as the real regime detector; use Gemini only for conflict-resolution natural-language justification. **"Let Gemini explain, let ML decide."**

This differentiates our submission from generic "LLM reads signals" entries.

## Final recommendation

1. Keep Gemini, narrow its job: conflict resolution + justification text only, not regime prediction
2. Drop $40k GCP assumption — re-focus on $10k Circle pool + $500 feedback
3. Use `gemini-2.5-flash` via `google-genai` SDK + Pydantic `response_schema` (~20 lines)
4. Pay tier-1 fee (~$0.03/demo) over fighting free-tier RPM limits live
5. Add sklearn GBM on v1.1/v1.3 historical data — **this is the originality multiplier**
