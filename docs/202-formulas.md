---
type: formula
status: active
related: [[100-strategy]], [[101-anchor-layer]], [[102-adaptation-layer]], [[103-active-layer]], [[200-budget-allocation]]
created: 2026-05-29
updated: 2026-05-29
---
# Формулы и расчёты

> Математические формулы для расчёта хеджа.

---

## Anchor sizing

```
N_contracts = (PositionSize × TargetFactor) / (Delta × SpotPrice)
```

Где `TargetFactor ∈ [0.8, 1.2]` — коэффициент покрытия.

**Цель:** обеспечить `Δ_hedge ≈ Δ_position` при падении цены до target_price.

## Adaptation sizing

```
N_contracts = AdaptBudget / Premium
```

Приоритет: максимальное снижение просадки.

## Active sizing

```
N_contracts = ActiveBudget / Premium
```

Приоритет: максимальная Gamma.

## Стоимость хеджа

```
CostPerDay = MarkPrice / DTE
TotalHedgeCost = Σ(N_contracts_i × Premium_i)
```

## PnL от хеджа

```
PnL_hedge = Σ(N_contracts_i × (ExitPrice_i - Premium_i))
```

## Efficiency (эффективность слоя)

### До покупки (выбор комбинации)

```
Efficiency = PnL_hedge_at_target / TotalHedgeCost
```

Где:
- `PnL_hedge_at_target` = сумма PnL всех опционов при цене SOL = целевой уровень
- `TotalHedgeCost` = общая стоимость покупки (премии × количество)

**Обоснование:** высокая Efficiency = асимметричный риск/доход. Рисуем $1, чтобы при падении получить $3-5.

Цель: **максимизировать**. Отбрасываем комбинации с Efficiency < 1.

### После закрытия (оценка сделки)

```
Efficiency_closed = PnL_hedge_realized / TotalHedgeCost
```

Цель: максимизировать Efficiency для Anchor, MinDrawdown для Adaptation, Gamma для Active.

## Anchor selection (T006)

### PnL портфеля (моделирование)

```
PositionPnL = (SpotPrice - EntryPrice) × SOL_qty
HedgePnL = Σ( (MarkPrice(K, SpotPrice, DTE, IV) - Premium_K) × N_i )
TotalPnL = PositionPnL + HedgePnL
Drawdown = TotalPnL / НачальныйКапитал
```

**MarkPrice** считаем через Black-Scholes с текущим `markIv`.

### Подбор количества контрактов

```
Σ(Premium_i × N_i) ≤ AnchorBudget
Drawdown(SpotPrice) ≤ TargetDrawdown
```

---

*Создано: 2026-05-29 | Обновлено: 2026-06-15*
