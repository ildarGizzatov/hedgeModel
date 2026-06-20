# HedgeModel

> Система многослойного хеджирования SOL через Put-опционы

Адаптивная система хеджирования, выстраивающая защитный барьер от экстремального падения до текущей цены. Три слоя защиты с разным бюджетом, разными Greeks-профилями и разными правилами управления.

## Архитектура

```
hedgeModel/
├── src/                      # Ядро системы
│   ├── pipeline.py           # Оркестратор: fetch → select → monitor
│   ├── OptionBoard.py        # Загрузка опционного чейна с Bybit → Excel
│   ├── LastPrice.py          # Обновление текущих цен опционов
│   ├── anchor_picker.py      # Подбор Anchor Layer (Core + Tail)
│   ├── monitor_options.py    # Мониторинг позиций + рекомендации
│   ├── buy_option.py         # Покупка опционов с записью в registry
│   └── black_scholes.py      # BS-расчёт цены и Greeks (r=0)
├── dashboard/                 # Web-дашборд
│   ├── server.py             # FastAPI backend (/api/positions, /api/options...)
│   ├── app.js                # Frontend (таблицы, графики, табы)
│   └── index.html            # UI
├── data/                      # Данные (CSV)
│   ├── open_positions.csv    # Текущая позиция SOL
│   ├── buy_history.csv       # История покупок SOL
│   ├── closed_positions.csv  # Закрытые опционы
│   ├── options_registry.csv  # Реестр купленных опционов
│   └── options_tracking.csv  # Текущие Greeks и цены опционов
├── excel/                     # Опционный чейн (Excel)
├── docs/                      # Zettelkasten-база знаний (Obsidian)
├── config.toml                # Параметры стратегии (генерируется из docs)
└── gen_config.py              # Генератор config.toml из документации
```

## Стратегия

Три слоя хеджа с распределением бюджета:

| Слой | Бюджет | Роль | DTE | Delta |
|------|--------|------|-----|-------|
| **Anchor** | 50% | Tail Risk, структурная защита | ≥ 25 | 0.05–0.20 |
| **Adaptation** | 30% | Стабилизация PnL | — | — |
| **Active** | 20% | Монетизация движения | — | — |

- **Глобальный бюджет:** 5% от суммы покупки SOL
- **Целевая просадка:** 20% от Avg Buy Price

## Быстрый старт

### 1. Виртуальное окружение

```bash
python -m venv venv
source venv/bin/activate
pip install requests pandas openpyxl fastapi uvicorn toml
```

### 2. Генерация конфига

```bash
python gen_config.py
```

### 3. Запуск пайплайна

```bash
python src/pipeline.py status    # статус файлов
python src/pipeline.py fetch     # загрузить опционный чейн с Bybit
python src/pipeline.py select    # подобрать Anchor Layer
python src/pipeline.py monitor   # анализ позиций + рекомендации
python src/pipeline.py run       # полный цикл (fetch → select → monitor)
python src/pipeline.py prices    # обновить только цены
```

### 4. Запуск дашборда

```bash
cd dashboard
python server.py
# Открываем: http://localhost:8083
```

### 5. Покупка опциона

```bash
python src/buy_option.py --strike 70 --expiry 2026-07-25 --qty 1 --layer active
python src/buy_option.py --symbol "SOL-25JUL25-70-P-USDT"
```

## API дашборда

| Эндпоинт | Описание |
|----------|----------|
| `GET /api/positions` | Позиции по активам + PnL-лестница |
| `GET /api/options` | Опционные позиции с Greeks |
| `GET /api/layers` | Бюджеты и затраты по слоям |
| `GET /api/recommendations` | Рекомендации модели |
| `GET /api/summary` | Общая сводка портфеля |
| `GET /api/blackscholes` | BS PnL ladder |
| `POST /api/update-options` | Обновить Greeks через monitor_options |
| `POST /api/refresh-prices` | Обновить текущие цены |
| `POST /api/close-option` | Закрыть опцион по правилу |

## Документация

Все методологические заметки в `docs/` (Obsidian Zettelkasten):

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
| 400 | Деплой |
| T001–T007 | Технические заметки |

## Зависимости

- **Python 3.12+**
- `requests` — Bybit API
- `pandas`, `openpyxl` — Excel
- `fastapi`, `uvicorn` — дашборд
- `toml` — парсинг config.toml
