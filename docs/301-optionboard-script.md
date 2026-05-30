---
type: script
status: active
related: [[300-pipeline]]
created: 2026-05-28
updated: 2026-05-29
---
# OptionBoard.py

> Скрипт для загрузки и обновления данных опционной цепочки с биржи Bybit.

---

## Назначение

Этап 1 пайплайна: загрузка сырой опционной цепочки с Bybit API в Excel.

## Источник данных

- **API:** Bybit v5 (`https://api.bybit.com/v5/market/tickers`)
- **Параметры:** `category=option`, `baseCoin=SOL`
- **Данные:** все торгуемые опционы (delta, gamma, theta, vega, markPrice, IV, openInterest)

## Выход

- **Файл:** `sol_options_chain.xlsx`
- **Лист:** `OptionBoard`
- **Колонки:** symbol, strike, delta, gamma, vega, theta, mark_price, iv, dte, T, type, spot_price, hedge_cost_per_day, open_interest

## Фильтрация

| Параметр | PUT | CALL |
|----------|-----|------|
| Delta | -0.70 … -0.01 | 0.01 … 0.70 |
| DTE | > 3 дня | > 3 дня |

## Расчётные поля

- `hedge_cost_per_day = mark_price / DTE`
- `T = DTE / 365`

## Запуск

```bash
cd /home/maks/projects/hedgeModel
./venv/bin/python src/OptionBoard.py
```

## Статус

- [x] Базовая загрузка с Bybit
- [x] Фильтрация по дельте и DTE
- [x] Запись в Excel
- [ ] Оптимизация производительности
- [ ] Обработка ошибок API

---

*Создано: 2026-05-28 | Обновлено: 2026-05-29*
