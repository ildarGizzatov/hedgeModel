---
type: ops
status: active
related: [[402-database-schema]]
created: 2026-05-29
updated: 2026-06-20
---
# ⚙️ Настройка проекта

> Источники параметров, порядок запуска, структура данных.

---

## Источники параметров

| Источник | Для чего | Как обновить |
|---|---|---|
| `docs/201-selection-criteria.md` | Параметры фильтрации опционов | Руками → `python gen_config.py` |
| `config.toml` | Готовый конфиг для скриптов | Автоматически из `gen_config.py` |
| `hedge_model.db` | SQLite-база данных (positions, options, greeks_history) | Автоматически через скрипты |
| `tools/optionboard.py` | Excel-дамп чейна (для чтения человеком) | `python tools/optionboard.py` |

## Порядок запуска

### Первый запуск

```bash
cd /home/maks/projects/hedgeModel

# 1. Генерация конфига
python gen_config.py

# 2. Загрузка опционного чейна (Excel)
python tools/optionboard.py
```

### Повседневный запуск

```bash
python src/pipeline.py run       # Полный цикл: fetch → select → monitor
python src/pipeline.py fetch     # Только загрузка чейна в БД
python src/pipeline.py prices    # Только обновление цен
python src/pipeline.py monitor   # Только мониторинг + рекомендации
```

### Покупка SOL

```bash
python src/buy_sol.py --qty 10 --price 72.50 --notes "покупка 20 июня"
```

### Покупка опциона

```bash
python src/buy_option.py --symbol "SOL-31JUL26-54-P-USDT" --qty 1 --layer anchor
python src/buy_option.py --strike 54 --expiry 2026-07-31 --qty 1 --layer active
python src/buy_option.py --auto  # Автоподбор
```

## Обновление параметров стратегии

1. Редактируешь `docs/201-selection-criteria.md` (меняешь числа в таблицах)
2. Запускаешь `python gen_config.py`
3. Проверяешь что `config.toml` обновился
4. Запускаешь `python src/pipeline.py run` — скрипт использует новые параметры

## Структура файлов

```
hedgeModel/
├── config.toml              # Сгенерированный конфиг (не редактировать)
├── gen_config.py            # Генератор конфига из документации
├── schema.sql               # SQLite схема (7 таблиц)
├── tools/
│   └── optionboard.py       # Excel-дамп чейна (для чтения)
├── docs/
│   ├── 201-selection-criteria.md  # ИСТОЧНИК ПАРАМЕТРОВ (ручной ввод)
│   └── 402-database-schema.md     # Описание БД
├── src/
│   ├── db.py                # Обёртка SQLite (CRUD, query)
│   ├── bybit_api.py         # Загрузка данных с Bybit
│   ├── buy_sol.py           # Покупка SOL → БД
│   ├── buy_option.py        # Покупка опциона → БД
│   ├── pipeline.py          # Оркестратор
│   ├── anchor_picker.py     # Подбор Anchor Layer
│   └── monitor_options.py   # Мониторинг + рекомендации → БД
├── data/                    # CSV для обратной совместимости
└── hedge_model.db           # SQLite-база (источник истины)
```

## Важные правила

- **Параметры стратегии** → только в `docs/201-selection-criteria.md`
- **Конфиг** → всегда генерируй через `gen_config.py`, не правь руками
- **Данные** → все изменения через скрипты, не редактируй CSV вручную
- **Бэкап БД** → `cp hedge_model.db hedge_model.db.bak`

## SQLite — источник истины

Все данные теперь хранятся в `hedge_model.db` (7 таблиц):
- `positions` — SOL-позиции
- `options` — реестр опционов
- `option_chain_snapshot` — снимки рынка
- `option_greeks_history` — история Greeks
- `closed_positions` — закрытые опционы
- `buy_history` — покупки SOL
- `recommendations` — рекомендации LLM

CSV-файлы остаются для обратной совместимости, но чтение/запись идёт через БД.

---

*Создано: 2026-05-29 | Обновлено: 2026-06-20*
