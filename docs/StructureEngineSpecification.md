# StructureEngine Specification

## Назначение

StructureEngine преобразует последовательность Swing в рыночную структуру.

На вход получает подтвержденные Swing High и Swing Low.

На выходе возвращает список объектов Structure.

---

# Входные данные

```python
list[Swing]
```

Swing должны быть отсортированы по времени.

---

# Выходные данные

```python
list[Structure]
```

Каждый Structure содержит:

- index
- timestamp
- price
- type

где type:

- HH
- HL
- LH
- LL

---

# Логика определения структуры

Сравнение выполняется только между Swing одного типа.

High сравнивается только с предыдущим High.

Low сравнивается только с предыдущим Low.

---

## Higher High (HH)

Если текущий Swing High выше предыдущего Swing High.

```
High2 > High1
```

---

## Lower High (LH)

Если текущий Swing High ниже предыдущего Swing High.

```
High2 < High1
```

---

## Higher Low (HL)

Если текущий Swing Low выше предыдущего Swing Low.

```
Low2 > Low1
```

---

## Lower Low (LL)

Если текущий Swing Low ниже предыдущего Swing Low.

```
Low2 < Low1
```

---

# Первый Swing

Первый найденный Swing High не классифицируется.

Первый найденный Swing Low не классифицируется.

Для определения структуры требуется предыдущий Swing такого же типа.

---

# Порядок обработки

Swing обрабатываются строго по времени.

Каждый новый Swing сравнивается только с последним Swing своего типа.

---

# Ограничения

StructureEngine не определяет:

- Trend
- BOS
- CHOCH
- Retest

Он отвечает только за классификацию:

HH

HL

LH

LL

---

# Ответственность

StructureEngine ничего не знает о стратегии.

Он только преобразует Swing → Structure.