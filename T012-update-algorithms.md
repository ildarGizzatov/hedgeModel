---
type: task
status: pending
id: T012
created: 2026-07-16
updated: 2026-07-16
related: [[203-anchor-selection-algorithm]], [[204-active-layer-selection]], [[105-layer-resource-management]], [[106-layer-health-monitoring]]
---

# T012 — Обновить алгоритмы выбора опционов

> Добавить в 203 и 204 ссылки на 105 (ресурс) и 106 (здоровье). Учет жизнеспособности при выборе опционов.

---

## Задачи

1. Обновить `docs/203-anchor-selection-algorithm.md`:
   - Добавить ссылку на `docs/105-layer-resource-management.md`
   - Добавить ссылку на `docs/106-layer-health-monitoring.md`
   - Добавить проверку жизнеспособности перед покупкой

2. Обновить `docs/204-active-layer-selection.md`:
   - Добавить ссылку на `docs/105-layer-resource-management.md`
   - Добавить ссылку на `docs/106-layer-health-monitoring.md`
   - Добавить проверку жизнеспособности перед покупкой

3. Определить **минимальный уровень жизнеспособности** для каждого слоя:
   - Anchor: DTE >= N, Gamma > X, Theta < Y
   - Active: DTE >= N, Gamma > X, Theta < Y

---

## Ожидаемый результат

Обновлённые алгоритмы выбора опционов, которые учитывают не только эффективность, но и остаточный ресурс слоя.

---

*Создана: 2026-07-16*
