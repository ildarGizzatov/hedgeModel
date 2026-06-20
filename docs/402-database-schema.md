---
type: ops
status: active
related: [[300-pipeline]], [[100-strategy]], [[200-budget-allocation]]
created: 2026-06-20
updated: 2026-06-20
---
# 🗄️ Хранение данных — SQLite

> Все данные в `hedge_model.db`. Полный DDL в `schema.sql`.

---

## Почему SQLite

| Критерий | CSV | SQLite |
|----------|-----|--------|
| История | один snapshot | неограниченная история |
| Запросы | pandas, медленно | SQL WHERE/AVG/ORDER BY |
| Инкрементная запись | append, дубликаты | INSERT с FK |
| Встроен в Python | ❌ `pip install` | `sqlite3` (stdlib) ✅ |

---

## Таблицы

### 1. `positions` — SOL-позиции (текущее состояние)

Единая строка: усреднённые данные по открытой позиции SOL.

**Поля:**

| Поле | Тип | Описание |
|------|-----|----------|
| `symbol` | TEXT | Символ актива (SOL) |
| `qty` | REAL | Текущее количество (уменьшается при закрытии) |
| `avg_price` | REAL | Средняя цена покупки (не меняется при частичном закрытии) |
| `total_cost` | REAL | Cost basis: qty × avg_price |
| `current_price` | REAL | Текущая рыночная цена |
| `total_value` | REAL | current_price × qty |
| `pnl` | REAL | total_value - total_cost |
| `updated` | TEXT | Дата последнего обновления |

**Ключевые правила:**
- `avg_price` не меняется при частичном закрытии. Используется как основа для расчёта просадки и Budget.
- Просадка считается от `avg_price` (цены входа), не от текущей цены.
- `current_price` обновляется автоматически при каждом `pipeline.py fetch`.

**Пример:**

| symbol | qty | avg_price | total_cost | current_price | total_value | pnl |
|--------|-----|-----------|------------|---------------|-------------|-----|
| SOL | 13.24 | 80.39 | 1064.39 | 71.90 | 951.96 | -112.43 |

---

### 2. `options` — реестр опционов

Справочник открытых опционов.

**Поля:**

| Поле | Тип | Описание |
|------|-----|----------|
| `option_id` | INTEGER PK | Уникальный ID |
| `symbol` | TEXT | Символ опциона (SOL-31JUL26-54-P-USDT) |
| `strike` | REAL | Страйк |
| `expiry_date` | TEXT | Дата экспирации |
| `type` | TEXT | put/call |
| `layer` | TEXT | anchor / adaptation / active |
| `qty` | REAL | Количество контрактов |
| `entry_price` | REAL | Цена покупки |
| `entry_date` | TEXT | Дата покупки |
| `status` | TEXT | open / closed |
| `close_reason` | TEXT | Причина закрытия (если закрыт) |
| `close_date` | TEXT | Дата закрытия |
| `close_price` | REAL | Цена закрытия |
| `pnl` | REAL | Реализованный PnL |

**Ключевые правила:**
- Фильтрация для LLM: `WHERE status = 'open'` — только открытые позиции.
- `layer` определяет правила закрытия (anchor = держать до экспирации, active = закрыть при срабатывании).

---

### 3. `option_chain_snapshot` — снимки рынка

Каждый `fetch` — полный снимок опционного чейна Bybit. История IV, liquidity.

**Поля:**

| Поле | Тип | Описание |
|------|-----|----------|
| `snapshot_id` | INTEGER PK | Уникальный ID |
| `snapshot_date` | TEXT | Дата/время снимка |
| `spot_price` | REAL | Цена SOL на момент снимка |
| `symbol` | TEXT | Символ опциона |
| `strike` | REAL | Страйк |
| `type` | TEXT | put/call |
| `delta` | REAL | Delta |
| `gamma` | REAL | Gamma |
| `theta` | REAL | Theta |
| `vega` | REAL | Vega |
| `mark_price` | REAL | Цена опциона |
| `iv` | REAL | Implied Volatility |
| `dte` | INTEGER | Дни до экспирации |
| `open_interest` | INTEGER | Открытый интерес |

**Использование:**
- Анализ трендов IV: `SELECT iv, snapshot_date FROM option_chain_snapshot WHERE symbol='SOL-...' ORDER BY snapshot_date DESC LIMIT 7`
- История Greeks рынка для выбора страйков.

---

### 4. `option_greeks_history` — история Greeks

**Ключевая таблица для LLM.** Daily snapshot Greeks для каждого опциона из registry.

**Поля:**

| Поле | Тип | Описание |
|------|-----|----------|
| `greeks_id` | INTEGER PK | Уникальный ID |
| `option_id` | INTEGER FK | Ссылка на `options` |
| `snapshot_date` | TEXT | Дата снимка |
| `delta` | REAL | Текущая Delta |
| `gamma` | REAL | Текущая Gamma |
| `theta` | REAL | Текущая Theta |
| `vega` | REAL | Текущая Vega |
| `mark_price` | REAL | Текущая цена |
| `iv` | REAL | Текущая IV |
| `spot_price` | REAL | Цена SOL |
| `dte` | INTEGER | Дни до экспирации |

**Использование:**
- Тренды Delta/IV за N дней — input для рекомендаций.
- `option_greeks_history` → `monitor_options.py` → `recommendations`.

---

### 5. `closed_positions` — закрытые опционы

Полный PnL с причиной закрытия. Заменяет `closed_positions.csv`.

**Поля:**

| Поле | Тип | Описание |
|------|-----|----------|
| `close_id` | INTEGER PK | Уникальный ID |
| `option_id` | INTEGER FK | Ссылка на закрытый опцион |
| `symbol` | TEXT | Символ опциона |
| `close_date` | TEXT | Дата закрытия |
| `entry_price` | REAL | Цена покупки |
| `close_price` | REAL | Цена продажи |
| `pnl` | REAL | PnL = (close - entry) × qty |
| `close_reason` | TEXT | Причина закрытия |
| `notes` | TEXT | Комментарий |

**Причины закрытия:**
- `take_profit` — фиксация прибыли
- `stop_loss` — ограничение убытка
- `roll` — роллирование на новый срок
- `expiry` — истечение срока
- `layer_rule` — по правилу слоя (anchor/adaptation/active)

---

### 6. `buy_history` — история покупок SOL

Усреднение cost basis. Заменяет `buy_history.csv`.

**Поля:**

| Поле | Тип | Описание |
|------|-----|----------|
| `buy_id` | INTEGER PK | Уникальный ID |
| `buy_date` | TEXT | Дата покупки |
| `qty` | REAL | Количество куплено |
| `price` | REAL | Цена за единицу |
| `total` | REAL | price × qty |
| `symbol` | TEXT | Символ актива |
| `notes` | TEXT | Комментарий |

**Расчёт avg_price:**
```
avg_price = (old_total_cost + new_total) / (old_qty + new_qty)
```

---

### 7. `recommendations` — рекомендации LLM

Фиксирует action, reason, confidence. Обратная связь → обучение.

**Поле**

| Поле | Тип | Описание |
|------|-----|----------|
| `rec_id` | INTEGER PK | Уникальный ID |
| `option_id` | INTEGER FK | Ссылка на опцион (NULL для общего) |
| `rec_date` | TEXT | Дата рекомендации |
| `action` | TEXT | close / hold / roll / buy / sell |
| `reason` | TEXT | Объяснение |
| `confidence_score` | REAL | 0-1 |
| `layer` | TEXT | anchor / adaptation / active |
| `status` | TEXT | pending / applied / rejected |
| `model` | TEXT | Какая модель дала рекомендацию |
| `user_feedback` | TEXT | Ответ пользователя: accepted / rejected |

---

## Потоки данных

```
Bybit API → pipeline.py → БД (option_chain_snapshot)
                      ↓
              anchor_picker.py → выбор Core + Tail
                      ↓
              monitor_options.py → greeks_history + recommendations
                      ↓
              buy_sol.py / buy_option.py → positions + options
```

### Кратко

1. **Рынок → БД:** snapshot IV, Greeks, цен всех опционов
2. **Позиции → БД:** buy_sol.py, buy_option.py — пишут в БД
3. **История → БД:** daily snapshot Greeks для каждого опциона
4. **Рекомендации → БД:** action/reason/confidence

---

## SQL-схема

Полный DDL с индексами: `schema.sql`.

---

*Создана: 2026-06-20 | Обновлено: 2026-06-20 — объединена с 401-positions-storage, добавлены поля и правила*
