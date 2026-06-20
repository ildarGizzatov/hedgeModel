---
type: ops
status: active
related: [[100-strategy]], [[200-budget-allocation]]
created: 2026-06-01
updated: 2026-06-01
---
# 📊 Хранение позиций

> Структура файлов для учёта открытых и закрытых позиций.

---

## Файлы

### data/open_positions.csv
Единая строка с усреднёнными данными по всем открытым позициям одного актива.

```csv
symbol,qty,avg_price,total_cost,current_price,total_value,pnl,updated
SOL,9.84,83.03,816.99,80.97,796.75,-20.24,2026-06-01
```

**Поля:**
- `symbol` — символ актива (SOL, BTC...)
- `qty` — текущее количество (уменьшается при закрытии)
- `avg_price` — средняя цена покупки (не меняется при закрытии части)
- `total_cost` — cost basis (qty × avg_price)
- `current_price` — текущая рыночная цена
- `total_value` — current_price × qty
- `pnl` — total_value - total_cost
- `updated` — дата последнего обновления

### data/buy_history.csv
История всех покупок (каждая покупка — отдельная строка).

```csv
date,qty,price,total,symbol,notes
2026-03-27,1,82.97,82.97,SOL,покупка 27 марта
```

**Поля:**
- `date` — дата покупки
- `qty` — количество куплено
- `price` — цена за единицу
- `total` — цена × количество
- `symbol` — символ актива
- `notes` — комментарий

### data/closed_positions.csv
История закрытых позиций (продажи).

```csv
date,qty,price_closed,avg_price,pnl,symbol,notes
2026-06-01,1,85.00,83.03,1.97,SOL,частичное закрытие
```

**Поля:**
- `date` — дата закрытия
- `qty` — количество продано
- `price_closed` — цена продажи за единицу
- `avg_price` — средняя цена покупки (из open_positions)
- `pnl` — (price_closed - avg_price) × qty
- `symbol` — символ актива
- `notes` — комментарий

## Обновление позиций

### Открытие новой позиции
1. Добавить строку в `data/buy_history.csv`
2. Пересчитать `avg_price` в `data/open_positions.csv`:
   ```
   avg_price = (old_qty × old_avg + new_qty × new_price) / (old_qty + new_qty)
   ```
3. Обновить все поля в `data/open_positions.csv`

### Частичное закрытие
1. Уменьшить `qty` в `data/open_positions.csv` на проданное количество
2. Добавить запись в `data/closed_positions.csv`
3. `avg_price` в `data/open_positions.csv` **не меняется**

### Полное закрытие
1. `qty = 0` в `data/open_positions.csv` (или удалить строку)
2. Добавить запись в `data/closed_positions.csv`
3. Добавить запись в `data/buy_history.csv` с `qty_closed`

## Зависимости

- [[001-input-parameters]] — целевая просадка, бюджет, распределение по слоям

---

*Создано: 2026-06-01*
