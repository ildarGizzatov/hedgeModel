---
type: rule
status: active
related: [[100-strategy]], [[101-anchor-layer]], [[102-adaptation-layer]], [[103-active-layer]]
created: 2026-05-28
updated: 2026-05-28
---
# Распределение бюджета по слоям

> Как глобальный лимит дробится на конкретные суммы для каждого слоя.

---

## Параметры бюджета

| Параметр | Значение | Обоснование |
|---|---|---|
| `global_budget_pct` | 5% | Максимум от суммы покупки SOL на весь хедж |
| `target_dd_pct` | 20% | Хедж начинает защищать при просадке от Avg Buy Price |

## Распределение по слоям

| Слой | Доля бюджета | Описание |
|---|---|---|
| Anchor | 50% | Дальний слой — Tail Risk, структурная защита |
| Adaptation | 30% | Средний слой — стабилизация PnL |
| Active | 20% | Ближний слой — монетизация движения |

## Распределение Anchor бюджета

| Компонент | Доля | Описание                                |
| --------- | ---- | --------------------------------------- |
| Core      | 60%  | Ядро Anchor Layer — основной хедж       |
| Tail      | 40%  | Усиление Anchor Layer — защита в хвосте |

## Расчёт

```
PositionSize = SOL_qty × Avg_Buy_Price
TotalBudget  = PositionSize × GlobalBudgetPct

AnchorBudget  = TotalBudget × 50%
AdaptBudget   = TotalBudget × 30%
ActiveBudget  = TotalBudget × 20%
```

Где `PositionSize` — **сумма, потраченная на покупку** базового актива:

**Почему цена покупки, а не текущая:**
Хедж покупается для защиты от просадки относительно цены входа. Опционы должны компенсировать падение с `Avg_Price` вниз, а не от текущей цены.

```
N_contracts × Premium ≤ LayerBudget
N_contracts = floor(LayerBudget / Premium)
```

---

*Создано: 2026-05-28 | Обновлено: 2026-06-16*
