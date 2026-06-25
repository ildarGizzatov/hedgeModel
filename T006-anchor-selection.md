---
type: task
status: in_progress
id: T006
created: 2026-06-16
updated: 2026-06-16
related: [[101-anchor-layer]], [[200-budget-allocation]], [[201-selection-criteria]], [[202-formulas]], [[203-anchor-selection-algorithm]]
---

# T006 — Реализация Anchor Selection алгоритма

> Перевести документ [[203-anchor-selection-algorithm]] в рабочий скрипт `anchor_picker.py`.

## 📌 Описание

Алгоритм подбора Core + Tail для Anchor Layer на основе матрицы эффективности E(S, K).

## Шаги алгоритма (по 203)

### Шаг 0: Расчёт бюджета
```
PositionSize = SOL_qty × Avg_Buy_Price
TotalBudget  = PositionSize × GlobalBudgetPct (5%)
AnchorBudget = TotalBudget × AnchorLayerPct (50%)
```

### Шаг 1: Фильтрация кандидатов
- PUT-опционы, DTE >= 25
- Distance от спота: >= 15%
- ❌ Delta > 0.20 (антипаттерн — близко к ATM)
- ❌ Delta < 0.05 (антипаттерн — слишком дешёвый)

### Шаг 2: Матрица эффективности E(S, K)
```
E(S, K) = (BS_Price(S_target, K, T, IV) - Premium) / Premium
```
- Baseline Strength = E(-20%) — эффективность при обычной коррекции
- Acceleration = E(-35%) - E(-20%) — ускорение при краше

### Шаг 3: Выбор Core (K1) и Tail (K2)
- **K1** = argmax E(-20%) при K > S_target (страйк выше целевого уровня)
- **K2** = argmax Acceleration при K2 ≠ K1 и K2 < K1

### Шаг 4: Расчёт количества контрактов
- ❌ DeltaRatio не смотрим
- Core <= 60% AnchorBudget (глобальный лимит)
- ❌ Core cost <= 60% AnchorBudget (убрано — заменилось глобальным лимитом)
- ❌ TotalCost <= AnchorBudget
- ❌ Минимизировать отклонение DeltaRatio от 100%

### Шаг 5: Коррекция по дистанции

Перед покупкой проверяем дистанцию каждого страйка от спота:

**Ситуация 1: dist >= 15%** (опцион дёшево)
- Покупка на весь выделенный бюджет для слоя
- Условия: Core по E20, Tail по Acceleration, дельта на целевом уровне

**Ситуация 2: dist < 15%** (опцион дорого)
- Покупка, но не на весь бюджет (скорректировать объём)
- Если и Core, и Tail дорого — минимальная покупка для защиты

### Шаг 6: Вывод рекомендаций
- Рекомендованные страйки и количества
- Delta-профиль на уровнях -10% до -35%
- PnL и Efficiency на каждом уровне

## 📋 Критерии завершения

- [x] Задача создана
- [ ] Скрипт переписан по правилам
- [ ] Тестирование на реальных данных
- [ ] Вывод рекомендаций в читаемом формате

---

*Создана: 2026-06-16 | Обновлено: 2026-06-16 23:46*
