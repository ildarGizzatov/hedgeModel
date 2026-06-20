---
type: task
status: completed
id: T004
created: 2026-06-10
updated: 2026-06-14
related: [[T001-conditions-closing]], [[T003-roll-economics]], [[T002-theta-monitoring]]
---

# T004 — Мониторинг открытых опционных позиций

> Создать систему фиксации Greeks/PnL/IV при покупке и автоматического обновления при мониторинге. Генерация рекомендаций для каждой позиции.

---

## 📁 Архитектура данных

### 1. `data/options_registry.csv` — Статический реестр позиций (ручное)

**Когда:** один раз при покупке
**Кто заполняет:** пользователь

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | int | Уникальный ID позиции |
| `symbol` | string | Символ опциона (SOL-26JUN26-66-P-USDT) |
| `type` | string | PUT или CALL |
| `strike` | float | Страйк |
| `expiry` | string | Дата экспирации (YYYY-MM-DD) |
| `qty` | int | Количество контрактов |
| `entry_date` | string | Дата покупки (YYYY-MM-DD) |
| `entry_price` | float | Цена покупки (премия) |
| `total_cost` | float | Общая стоимость (qty × entry_price) |
| `iv_entry` | float | Implied Volatility при покупке |
| `iv_atm_entry` | float | IV ATM той же экспирации при покупке |
| `delta_entry` | float | Delta при покупке |
| `gamma_entry` | float | Gamma при покупке |
| `theta_entry` | float | Theta при покупке |
| `vega_entry` | float | Vega при покупке |
| `layer` | string | `anchor` / `adaptation` / `active` |
| `status` | string | `open` / `closed` / `rolled` |
| `notes` | string | Комментарии |

---

### 2. `data/options_tracking.csv` — Динамический трекинг (автоматическое)

**Когда:** при каждом запуске скрипта мониторинга
**Кто заполняет:** система

| Поле | Тип | Описание | Источник |
|------|-----|----------|----------|
| `symbol` | string | Символ опциона | Из реестра |
| `current_price` | float | Текущая цена (mark) | Bybit API |
| `pnl` | float | NTL PnL (current_price - entry_price) × qty | Расчёт |
| `delta` | float | Текущая Delta | Bybit API |
| `gamma` | float | Текущая Gamma | Bybit API |
| `theta` | float | Текущая Theta | Bybit API |
| `vega` | float | Текущая Vega | Bybit API |
| `dte` | int | Days to Expiration | Расчёт |
| `iv` | float | Текущая Implied Volatility | Bybit API |
| `iv_atm` | float | IV ATM той же экспирации | Расчёт |
| `intrinsic_value` | float | Внутренняя стоимость | Расчёт |
| `layer` | string | Слой позиции | Из реестра |
| `updated` | string | Дата обновления (YYYY-MM-DD) | Система |

---

## 📊 Алгоритм мониторинга

### Процесс

1. Загрузка полного чейна SOL-опционов из Bybit API
2. Обновление портфеля SOL: `current_price` из API, пересчёт PnL
3. Чтение реестра опционов (`options_registry.csv`, статус open)
4. Запрос Bybit API → текущие Greeks, цена, IV по каждому символу
5. Расчёт: PnL, DTE, IV ATM (ATM-опцион delta ≈ 0.5)
6. Расчёт совокупных Greeks портфеля (net delta, theta)
7. Сравнение с триггерами (T001, T003)
8. Генерация рекомендаций для каждой позиции

### 4 типа рекомендаций

| Рекомендация | Когда | Действие |
|-------------|-------|----------|
| 🔴 **Закрыть** | Цель достигнута / стоп-лосс / time exit | Закрыть позицию, обновить реестр |
| 🟡 **Роллировать** | DTE заканчивается, потенциал есть, экономика ролла > 0 | Проверить IV фильтр (T003), роллировать |
| 🟢 **Мониторить** | Цели не достигнуты, потенциал есть, DTE нормальный | Продолжать держать |
| 🟣 **Держать** | Только Anchor: tail-хедж, держать до экспирации | Без изменений |

### Триггеры по слоям

Полная логика закрытия и ролла описана в [[T001-conditions-closing]].
Скрипт мониторинга только проверяет текущее состояние позиций и формирует рекомендации.

### Формат вывода

Сводка портфеля:
```
📊 ПОРТФЕЛЬ SOL
   Количество: 13.24 SOL
   Avg Price: $80.39
   Current: $67.69
   PnL: $-168.17 (-15.8%)

📊 ОПЦИОНЫ (1 позиций)
   Total Cost: $1.93
   Current Value: $1.78
   PnL: $-0.15 (-7.6%)

📊 GREEKS ПОРТФЕЛЯ
   Net Delta: -0.01 SOL
   Theta: $-0.11/день
```

Рекомендации по опционам:
```
🔴 SOL-19JUN26-60-P | Active | DTE=3 | PnL=+15% → Закрыть (цель достигнута)
🟡 SOL-26JUN26-66-P | Active | DTE=5 | PnL=-8% → Роллировать (delta ещё работает)
🟢 SOL-31JUL26-58-P | Anchor | DTE=30 | PnL=-5% → Мониторить (tail-хедж)
```

---

## 📋 Критерии завершения

- [x] Созданы шаблоны CSV (registry + tracking)
- [x] Поле `layer` добавлено в оба CSV-файла
- [x] Greeks при входе (delta, gamma, theta, vega) добавлены в registry
- [x] Архитектура данных описана в T004
- [x] Алгоритм мониторинга и рекомендации описаны
- [x] `monitor_options.py` создан и тестируется
- [x] Тестирование на реальной позиции (SOL-26JUN26-66-P)
- [x] Документация финальная

---

*Создана: 2026-06-10*
*Обновлена: 2026-06-14 — убраны дубликаты триггеров, валидация удалена*
*Завершена: 2026-06-14*
