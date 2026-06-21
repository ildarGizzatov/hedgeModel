# HedgeModel

> Система многослойного хеджирования SOL через Put-опционы

Адаптивная система хеджирования, выстраивающая защитный барьер от экстремального падения до текущей цены. Три слоя защиты с разным бюджетом, разными Greeks-профилями и разными правилами управления.

## Архитектура

```
hedgeModel/
├── src/                      # Ядро системы
│   ├── pipeline.py           # Оркестратор: fetch → select → monitor
│   ├── fetch_step.py         # Шаг 1: загрузка чейна с Bybit → БД
│   ├── prices_step.py        # Шаг: обновление цен (spot + позиции)
│   ├── run_step.py           # Полный цикл (fetch → select → monitor)
│   ├── status_step.py        # Статус БД и файлов
│   ├── anchor_picker.py      # Подбор Anchor Layer (Core + Tail)
│   ├── monitor_options.py    # Мониторинг позиций + рекомендации
│   ├── buy_option.py         # Покупка опционов с записью в БД
│   ├── buy_sol.py            # Покупка SOL с усреднением cost basis
│   ├── bybit_api.py          # Bybit REST API (spot + options)
│   ├── chain_fetcher.py      # Fetch + парсинг + фильтрация чейна
│   ├── chain_parser.py       # Парсинг Bybit ticker → опцион
│   ├── db.py                 # Обёртка SQLite: CRUD, query-хелперы
│   ├── black_scholes.py      # BS-расчёт цены и Greeks (r=0)
│   └── OptionBoard.py        # Загрузка чейна → Excel (legacy)
├── dashboard/                # Web-дашборд
│   ├── server.py             # FastAPI backend (/api/positions, /api/options...)
│   ├── app.js                # Frontend (таблицы, графики, табы)
│   └── index.html            # UI
├── tools/                    # Вспомогательные утилиты
│   └── optionboard.py        # Опционный чейн → Excel (альтернативный путь)
├── data/                     # Бэкап CSV (быстрое чтение, не основной источник)
│   ├── open_positions.csv    # Бэкап позиции SOL
│   ├── buy_history.csv       # Бэкап истории покупок
│   ├── closed_positions.csv  # Бэкап закрытых опционов
│   ├── options_registry.csv  # Бэкап реестра опционов
│   └── options_tracking.csv  # Бэкап Greeks-трекинга
├── excel/                    # Опционный чейн (Excel)
│   └── sol_options_chain.xlsx
├── hedge_model.db            # SQLite-база (источник истины)
├── schema.sql                # DDL-схема БД (7 таблиц)
├── config.toml               # Параметры стратегии (генерируется из docs)
├── gen_config.py             # Генератор config.toml из документации
├── docs/                     # Zettelkasten-база знаний (Obsidian)
└── dev/                      # Технические заметки и планирование
```

## Стратегия

Три слоя хеджа с распределением бюджета:

| Слой | Бюджет | Роль | DTE | Delta |
|------|--------|------|-----|-------|
| **Anchor** | 50% | Tail Risk, структурная защита | ≥ 25 | 0.05–0.20 |
| **Adaptation** | 30% | Стабилизация PnL | — | — |
| **Active** | 20% | Монетизация движения | — | — |

**Anchor Budget Split:**

| Подслой | Доля | Роль |
|---------|------|------|
| Core | 60% Anchor | Ядро защиты, ближе к ATM |
| Tail | 40% Anchor | Усиление, дальний OTM |

- **Глобальный бюджет:** 5% от суммы покупки SOL
- **Целевая просадка:** 20% от Avg Buy Price

## SQLite-схема

Источник истины — `hedge_model.db` (7 таблиц):

| Таблица | Назначение |
|---------|-----------|
| `positions` | Текущие позиции SOL (qty, avg_price, PnL) |
| `options` | Реестр купленных опционов (layer, entry Greeks) |
| `option_chain_snapshot` | Снимки полного опционного чейна по каждому fetch |
| `option_greeks_history` | Инкрементная история Greeks + IV для каждого опциона |
| `closed_positions` | Закрытые опционы (close_price, PnL, причина) |
| `buy_history` | История покупок SOL (усреднение cost basis) |
| `recommendations` | Рекомендации модели (action, reason, confidence, статус) |

Индексы: `option_greeks_history(option_id, timestamp)`, `option_chain_snapshot(timestamp, symbol)`, `recommendations(option_id, timestamp)`.

## Быстрый старт

### 1. Установка

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

или через pyproject:

```bash
pip install -e .
```

### 2. Генерация конфига

```bash
python gen_config.py
```

Считывает параметры из `docs/200-budget-allocation.md` и `docs/201-selection-criteria.md`, записывает `config.toml`.

### 3. Инициализация БД

```bash
python -c "from src.db import init_db; init_db()"
```

Создаёт таблицы из `schema.sql`.

### 4. Запуск пайплайна

```bash
python src/pipeline.py status    # статус БД
python src/pipeline.py fetch     # загрузить опционный чейн с Bybit → БД
python src/pipeline.py select    # подобрать Anchor Layer (Core + Tail)
python src/pipeline.py monitor   # анализ позиций + рекомендации
python src/pipeline.py prices    # обновить только цены
python src/pipeline.py run       # полный цикл (fetch → select → monitor)
```

или через entry point:

```bash
hedge-pipeline fetch
hedge-pipeline run
```

### 5. Запуск дашборда

```bash
source venv/bin/activate
python dashboard/server.py
# или: hedge-dashboard
# Открываем: http://localhost:8083
```

### 6. Покупка SOL

```bash
python src/buy_sol.py --qty 10 --price 72.50 --notes "покупка 20 июня"
```

Записывает покупку в БД (buy_history + positions), усредняет avg_price позиции SOL.

### 7. Покупка опциона

```bash
python src/buy_option.py --strike 70 --expiry 2026-07-25 --qty 1 --layer active
python src/buy_option.py --symbol "SOL-25JUL25-70-P-USDT"
```

Записывает опцион в БД (options + option_greeks_history), фиксирует entry Greeks и IV.

### 8. Опционный чейн → Excel

```bash
python tools/optionboard.py
# или
python src/OptionBoard.py
```

Загружает полный чейн SOL-опционов с Bybit, сохраняет в `excel/sol_options_chain.xlsx`.

## API дашборда

| Эндпоинт | Метод | Описание |
|----------|-------|----------|
| `/api/positions` | GET | Позиции по активам + PnL-лестница |
| `/api/options` | GET | Опционные позиции с Greeks |
| `/api/layers` | GET | Бюджеты и затраты по слоям |
| `/api/recommendations` | GET | Рекомендации модели |
| `/api/summary` | GET | Общая сводка портфеля |
| `/api/blackscholes` | GET | BS PnL ladder для опциона |
| `/api/update-options` | POST | Обновить Greeks через monitor_options |
| `/api/refresh-prices` | POST | Обновить текущие цены |
| `/api/close-option` | POST | Закрыть опцион по правилу убытка |

## Документация

### Методология (docs/ — Obsidian Zettelkasten)

| № | Тема |
|---|------|
| 100 | Стратегия Адаптивного Хеджа |
| 101 | Anchor Layer |
| 102 | Adaptation Layer |
| 103 | Active Layer |
| 200 | Распределение бюджета |
| 201 | Критерии отбора опционов |
| 202 | Формулы |
| 203 | Алгоритм выбора Anchor |
| 300 | Pipeline |
| 402 | SQLite-схема |
| 501 | Option Selection Diagnostics |
| 600 | Greeks Guide |

### Технические заметки (dev/)

| Файл | Тема |
|------|------|
| T001 | Условия закрытия позиций |
| T002 | Theta-мониторинг |
| T003 | Roll-экономика |
| T004 | Мониторинг открытых опционов |
| T005 | Выбор стратегии Adaptation |
| T006 | Anchor Selection |
| T007 | Dashboard |
| 301 | OptionBoard Script |
| 400 | Deployment |
| 500 | Debug Log |
| 900 | Идеи / TODO |
| 901 | Project Setup |
| GIT | Git-протокол |
| Kanban | Kanban-доска |

## Зависимости

| Пакет | Версия | Назначение |
|-------|--------|-----------|
| fastapi | 0.137.1 | Web-фреймворк для дашборда |
| uvicorn | 0.49.0 | ASGI-сервер |
| pandas | 3.0.3 | Таблицы, Excel |
| numpy | 2.4.6 | Математические расчёты |
| openpyxl | 3.1.5 | Excel (read/write) |
| requests | 2.34.2 | Bybit API |

**Dev:** ruff, pytest

## Зависимости системы

- **Python 3.12+**
- **SQLite** — встроен в Python (hedge_model.db)
