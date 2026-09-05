# QTR Long — Hierarchical SMC Architecture

## Why vNext exists

Genesis Setup #1 is frozen as a completed research result. The five-year validation did not demonstrate a durable edge, so vNext must not continue by tuning the same score thresholds or stacking more indicators onto the same flat rule set.

The vNext architecture treats Smart Money Concepts as an ordered decision process rather than a bag of additive signals.

## Core invariant

QTR Long is LONG-only.

Final decisions remain:

- BUY
- SKIP

Bearish information can only block a LONG thesis. It must never create SELL/SHORT execution.

## Four-layer timeframe model

QTR Long vNext uses four explicit, synchronized layers:

- 4H — higher-timeframe narrative
- 1H — structural confirmation / dealing-range context
- 15m — setup context, POI and liquidity map
- 5m — execution trigger

Every decision is evaluated only from candles that are already closed at the terminal 5m decision time. Missing higher-timeframe data blocks the hierarchy rather than silently falling back to a lower timeframe.

## Decision hierarchy

```text
4H Narrative
    ↓
1H Structure Confirmation
    ↓
15m Dealing Range / Location
    ↓
15m POI: bullish OB + optional active bullish FVG
    ↓
15m Sell-Side Liquidity Map
    ↓
5m Liquidity Raid / Reclaim
    ↓
5m Bullish Displacement
    ↓
5m MSS / Bullish BOS
    ↓
5m Execution FVG / OB
    ↓
Pending LIMIT BUY Plan
    ↓
Risk / Position Sizing
    ↓
BUY or SKIP
```

The order is intentional. Later evidence cannot compensate for a failed mandatory gate earlier in the chain.

## Gate philosophy

The old Long Score is not allowed to turn a structurally invalid setup into BUY just because enough independent points were accumulated.

Mandatory gates in vNext:

1. Narrative gate — no LONG without an explicit bullish 4H thesis.
2. 1H structure gate — bearish or unsupported structure produces SKIP.
3. 15m location / POI gate — the setup must exist in an allowed structural location.
4. 15m liquidity gate — a meaningful sell-side liquidity reference must exist for a future LONG raid.
5. 5m raid gate — price must trade below mapped sell-side liquidity and reclaim above it on a closed candle.
6. 5m displacement gate — the raid must be followed by meaningful bullish expansion.
7. 5m structure gate — bullish MSS/CHOCH or bullish BOS must confirm the execution shift.
8. Execution-value gate — a valid bullish FVG / Order Block must be known by structure confirmation time.
9. Risk gate — invalid stop geometry, insufficient R:R, or account limits always produce SKIP.

Scores may still rank already-valid candidates, but scores do not override failed gates.

## No-lookahead contract

The execution clock is the close time of the terminal 5m candle.

At that moment:

- the terminal 5m candle is closed and usable;
- only closed 15m candles are visible;
- only closed 1H candles are visible;
- only closed 4H candles are visible.

A future retracement is never inspected before entry planning. Once raid → displacement → structure confirmation is complete, QTR Long creates a resting LONG entry plan from execution value that is already known. Later price action decides whether that order is filled.

## Current vNext execution sequence

```text
4H bullish narrative
        ↓
1H bullish/supportive structure
        ↓
15m discount/equilibrium POI
        ↓
15m mapped sell-side liquidity
        ↓
5m liquidity raid + reclaim
        ↓
5m bullish displacement
        ↓
5m bullish MSS / BOS
        ↓
5m bullish FVG / OB execution zone
        ↓
LIMIT BUY PLAN
```

If any mandatory stage fails, the result is SKIP. Bearish evidence never authorizes SHORT.

## Current implementation status

Implemented on `feature/qtr-long-smc-hierarchy`:

- HTF narrative domain gate
- synchronized 4H / 1H / 15m / 5m data contract
- structural dealing range
- structural 4H narrative engine
- 1H structure confirmation gate
- 15m POI gate
- 15m sell-side liquidity map
- 5m liquidity raid detector
- 5m displacement engine
- 5m MSS / bullish BOS confirmation
- 5m execution FVG / OB entry planning
- stateful hierarchical orchestrator returning BUY PLAN or SKIP with reason

The previous Genesis setup remains frozen and is not modified by vNext work.

## Session context

Session metadata may be added as context, not as an automatic source of edge. Crypto trades 24/7, so session assumptions must be validated rather than imported unchanged from FX or index markets.

Session logic is intentionally not a mandatory permission gate at the current milestone.

## Risk and scoring

The hierarchical pipeline is the permission mechanism.

The legacy additive Long Score must not rescue a failed structural gate. If retained, score can only rank candidates that have already passed every mandatory narrative, structure, liquidity and execution gate.

Account-based position sizing remains a separate downstream concern. Leverage changes margin usage, not the planned loss defined by entry and stop before fees, slippage and liquidation effects.

## Validation discipline

Each setup family gets a frozen specification and validation cycle.

```text
specification
→ implementation
→ mechanical quality gate
→ diagnostic check
→ one declared hypothesis if needed
→ frozen OOS validation
→ GO / NO-GO
```

Do not rescue a weak setup by repeatedly changing thresholds on the same sample.

## Next milestone

Before any new strategy feature or backtest optimization:

1. run focused pytest for the complete hierarchy;
2. run focused mypy;
3. run focused ruff;
4. fix mechanical typing/lint issues only;
5. wire the four synchronized timeframes into a dedicated QTR Long vNext backtest;
6. freeze the first hierarchical setup specification before evaluating performance.
