---
type: rule
status: active
related: [[100-strategy]], [[101-anchor-layer]], [[102-adaptation-layer]], [[103-active-layer]]
created: 2026-05-28
updated: 2026-05-29
---
# Распределение бюджета по слоям

> Как глобальный лимит дробится на конкретные суммы для каждого слоя.

---

## Глобальный бюджет

```
TotalBudget = PositionSize × (5% … 10%)
```

Где `PositionSize` — текущая стоимость позиции в базовом активе.

## Распределение по слоям

| Слой | Доля бюджета | Формула |
|------|-------------|---------|
| Anchor (дальний) | 40–50% | `AnchorBudget = TotalBudget × [0.40, 0.50]` |
| Adaptation (средний) | 30–40% | `AdaptBudget = TotalBudget × [0.30, 0.40]` |
| Active (ближний) | 10–20% | `ActiveBudget = TotalBudget × [0.10, 0.20]` |

## Контроль бюджета слоя

```
N_contracts × Premium ≤ LayerBudget
N_contracts = floor(LayerBudget / Premium)
```

## Статус

- [ ] Определить, фиксированный или динамический процент
- [ ] Связь с ATR для адаптации к волатильности

---

*Создано: 2026-05-28 | Обновлено: 2026-05-29*
