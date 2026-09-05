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
- 1H — structural confirmation and structural dealing range
- 15m — setup POI and liquidity map inside the 1H range context
- 5m — execution trigger

Every decision is evaluated only from candles that are already closed at the terminal 5m decision time. Missing higher-timeframe data blocks the hierarchy rather than silently falling back to a lower timeframe.

The 1H layer is the authoritative owner of the dealing range used for location permission. The 15m layer may identify a bullish OB/FVG candidate, but its own swings do not redefine the higher-timeframe dealing range.

## Decision hierarchy

```text
4H Narrative
    ↓
1H Structure Confirmation
    ↓
1H Structural Dealing Range / Location Context
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
3. 1H location context — a structural dealing range must exist and is the authoritative frame for POI location.
4. 15m POI gate — the bullish setup must exist in an allowed location within that 1H dealing range.
5. 15m liquidity gate — a meaningful sell-side liquidity reference must exist for a future LONG raid.
6. 5m raid gate — price must trade below mapped sell-side liquidity and reclaim above it on a closed candle.
7. 5m displacement gate — the raid must be followed by meaningful bullish expansion.
8. 5m structure gate — bullish MSS/CHOCH or bullish BOS must confirm the execution shift.
9. Execution-value gate — a valid bullish FVG / Order Block must be known by structure confirmation time.
10. Risk gate — invalid stop geometry, insufficient R:R, or account limits always produce SKIP.

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
1H structural discount/equilibrium context
        ↓
15m bullish POI inside that context
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
- explicit 1H ownership of the dealing range used by the 15m POI gate
- 15m POI gate
- 15m sell-side liquidity map
- 5m liquidity raid detector
- 5m displacement engine
- 5m MSS / bullish BOS confirmation
- 5m execution FVG / OB entry planning
- stateful hierarchical orchestrator returning BUY PLAN or SKIP with reason
- dedicated MTF historical loader, synchronized snapshot stream, analysis coordinator and decision-level backtest runner
- explicit warmup support so higher-timeframe state is built before the evaluation window without contaminating evaluation statistics

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

Before any backtest optimization or new strategy feature:

1. run focused pytest for the updated hierarchy and MTF backtest stack;
2. run focused mypy;
3. run focused ruff;
4. fix mechanical typing/lint issues only;
5. freeze the first hierarchical setup specification;
6. run the first real BTCUSDT MTF diagnostic period with declared warmup and evaluation windows;
7. inspect stage diagnostics before any performance tuning.
