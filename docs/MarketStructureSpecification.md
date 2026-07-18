# Market Structure Specification

## Назначение

Документ описывает правила определения структуры рынка для QTR AI v2.

Все последующие модули должны следовать данной спецификации.

---

# Pipeline

```
MarketData
    │
SwingDetector
    │
Swing
    │
StructureEngine
    │
Structure
    │
BOSEngine
    │
BOS
    │
CHOCHEngine
    │
CHOCH
    │
TrendEngine
```

---

# Swing

Swing представляет локальный экстремум.

Типы:

- HIGH
- LOW

---

# Structure

Structure строится только на основании Swing.

Типы:

- HH (Higher High)
- HL (Higher Low)
- LH (Lower High)
- LL (Lower Low)

Правила:

HH:
новый HIGH выше предыдущего HIGH.

HL:
новый LOW выше предыдущего LOW.

LH:
новый HIGH ниже предыдущего HIGH.

LL:
новый LOW ниже предыдущего LOW.

Первый HIGH и первый LOW не классифицируются.

---

# Break Of Structure (BOS)

BOS означает продолжение существующей структуры.

Типы:

- BULLISH
- BEARISH

Bullish BOS возникает после подтвержденного продолжения бычьей структуры.

Bearish BOS возникает после подтвержденного продолжения медвежьей структуры.

BOS не означает смену направления.

BOS подтверждает существующее движение.

---

# Change Of Character (CHOCH)

CHOCH означает первое изменение структуры.

CHOCH появляется раньше нового тренда.

Типы:

- BULLISH
- BEARISH

Bearish CHOCH

После бычьей структуры появляется первое медвежье нарушение.

Bullish CHOCH

После медвежьей структуры появляется первое бычье нарушение.

CHOCH является предупреждением.

Он сам по себе еще не означает новый тренд.

---

# Trend

Trend определяется только после анализа BOS и CHOCH.

Типы:

- BULLISH
- BEARISH
- RANGE

Trend не определяется непосредственно по HH, HL, LH, LL.

---

# Responsibility

## SwingDetector

Вход:

MarketData

Выход:

list[Swing]

---

## StructureEngine

Вход:

list[Swing]

Выход:

list[Structure]

---

## BOSEngine

Вход:

list[Structure]

Выход:

list[BOS]

Отвечает только за определение Break Of Structure.

---

## CHOCHEngine

Вход:

list[Structure]

Выход:

list[CHOCH]

Отвечает только за определение Change Of Character.

---

## TrendEngine

Вход:

- list[BOS]
- list[CHOCH]

Выход:

Trend

Отвечает только за определение текущего направления рынка.

---

# Design Rules

Каждый модуль имеет только одну ответственность.

Модули не должны определять задачи других модулей.

Все движки работают последовательно.

Каждый следующий модуль использует результат предыдущего.
MarketStructureState

Responsibilities:
- хранит текущее состояние структуры рынка;
- хранит предыдущие и последние HH/HL/LH/LL;
- хранит последний BOS;
- хранит последний CHOCH;
- хранит текущий Trend.

Обновляется исключительно MarketStructureEngine.