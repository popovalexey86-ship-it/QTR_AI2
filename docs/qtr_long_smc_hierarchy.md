# QTR Long — Hierarchical SMC Architecture

## Why vNext exists

Genesis Setup #1 is frozen as a completed research result. The five-year validation did not demonstrate a durable edge, so vNext must not continue by tuning the same score thresholds or stacking more indicators onto the same flat rule set.

The next architecture treats Smart Money Concepts as an ordered decision process rather than a bag of additive signals.

## Core invariant

QTR Long is LONG-only.

Final decisions remain:

- BUY
- SKIP

Bearish information can only block or downgrade a LONG thesis. It must never create SELL/SHORT execution.

## Decision hierarchy

```text
HTF Narrative
    ↓
Location / Dealing Range
    ↓
Liquidity Map
    ↓
Liquidity Event / Raid
    ↓
Displacement
    ↓
MSS / BOS confirmation
    ↓
POI selection: OB / FVG / Breaker
    ↓
LTF Retest / Reaction
    ↓
Session Context
    ↓
Risk Gate
    ↓
BUY or SKIP
```

The order is intentional. Later evidence cannot compensate for a failed mandatory gate earlier in the chain.

## Gate philosophy

The old Long Score is not allowed to turn a structurally invalid setup into BUY just because enough independent points were accumulated.

Examples of mandatory gates for vNext:

1. Narrative gate — no LONG without an explicit bullish higher-timeframe thesis.
2. Location gate — price must be in an allowed location for the selected setup family.
3. Liquidity gate — the setup must reference a meaningful liquidity objective/event, not merely a local wick.
4. Displacement gate — structural confirmation must come from meaningful expansion, not any minor BOS print.
5. Execution gate — entry must occur at a defined POI/retest condition.
6. Risk gate — invalid stop geometry, insufficient R:R, or portfolio limits always produce SKIP.

Scores may still rank already-valid candidates, but scores do not override failed gates.

## Multi-timeframe requirement

A real HTF narrative cannot be inferred honestly from the same 15m stream used for execution. vNext therefore needs explicit higher-timeframe market data.

Target first composition for BTCUSDT 15m execution:

- HTF context: 4h
- intermediate context: 1h
- execution: 15m

This is an architectural target, not an optimization claim. Exact timeframe combinations must be validated out-of-sample rather than selected retrospectively for best historical performance.

## vNext implementation order

### Phase 1 — Narrative domain model

Create explicit bullish / neutral / bearish narrative state and a LONG-only narrative gate. No backtest behavior change until multi-timeframe data is wired correctly.

### Phase 2 — Multi-timeframe data contract

Provide synchronized HTF/ITF/LTF data without look-ahead. At a 15m decision timestamp, every higher-timeframe candle must be closed and known at that timestamp.

### Phase 3 — Structural dealing range and liquidity map

Replace the rolling-window premium/discount proxy with a structurally anchored dealing range. Track meaningful BSL/SSL targets.

### Phase 4 — Displacement and structural confirmation

Model displacement explicitly. BOS/MSS must be tied to the impulse that generated the POI used by the setup.

### Phase 5 — POI and execution

Link OB/FVG/Breaker objects to the structural event that created them. Require LTF reaction/retest before candidate creation.

### Phase 6 — Session context

Add session metadata as context, not as an automatic source of edge. Validate crypto-specific session behavior rather than importing assumptions unchanged from FX/index markets.

### Phase 7 — Candidate ranking and risk

Apply score only after all mandatory gates pass. Keep BUY/SKIP execution boundary and account-based risk sizing.

## Anti-overfit rule

Each setup family gets its own frozen specification and validation cycle.

```text
specification
→ implementation
→ diagnostic check
→ one declared hypothesis if needed
→ frozen OOS validation
→ GO / NO-GO
```

Do not rescue a weak setup by repeatedly changing thresholds on the same sample.

## First vNext milestone

The first code milestone is intentionally narrow: introduce an explicit HTF narrative model and LONG-only gate without pretending that the current single-timeframe AnalysisContext is already a true HTF narrative.
