---
type: script
status: active
related: [[300-pipeline]]
created: 2026-05-28
updated: 2026-05-29
---
# LastPrice.py

> Скрипт для обновления последних цен опционов.

---

## Назначение

Этап 3 пайплайна: обновление last/bid/ask/mark цен для отфильтрованных опционов.

## Источник данных

- **API:** Bybit v5 (`https://api.bybit.com/v5/market/tickers`)
- **Параметры:** `category=option`, `baseCoin=SOL`

## Вход

- **Файл:** `sol_options_chain.xlsx`
- **Лист:** `ListOption`
- **Ключ:** `symbol`

## Выход

Обновлённые поля:
- `last_price` — последняя цена
- `bid_price` — цена покупки
- `ask_price` — цена продажи
- `mark_price_live` — live mark price

## Запуск

```bash
cd /home/maks/projects/hedgeModel
./venv/bin/python src/LastPrice.py
```

## Статус

- [x] Базовое обновление цен
- [ ] Обработка ошибок
- [ ] Логирование изменений

---

*Создано: 2026-05-28 | Обновлено: 2026-05-29*
