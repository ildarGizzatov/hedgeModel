---
type: ops
status: active
related: [[301-optionboard-script]], [[302-lastprice-script]]
created: 2026-05-28
updated: 2026-06-16
---
# Пайплайн обработки данных

> Единая точка входа через `src/pipeline.py`. Все модули подключены, логика не дублируется.

---

## Архитектура

```
pipeline.py  ← orchestrator (импортирует модули, управляет порядком)
├── OptionBoard.py    — fetch чейна SOL с Bybit → Excel
├── anchor_picker.py  — подбор Core/Tail (чтёт конфиг + позицию + Excel)
├── monitor_options.py — анализ позиций + рекомендации
└── LastPrice.py      — обновление цен (опционально)
```

Каждый модуль — самостоятельная единица. Pipelineorchestrator только вызывает.

---

## Команды

### `pipeline.py status`

Показать дату и размер всех ключевых файлов:

```bash
./venv/bin/python src/pipeline.py status
```

### `pipeline.py fetch`

Загрузить актуальный опционный чейн SOL с Bybit API → `excel/sol_options_chain.xlsx`. Обновить `data/open_positions.csv`.

```bash
./venv/bin/python src/pipeline.py fetch
```

### `pipeline.py select`

Подобрать Anchor Layer — Core + Tail. Чтение параметров из `docs/001-input-parameters.md`, позиция из `data/open_positions.csv`, данные из Excel.

```bash
./venv/bin/python src/pipeline.py select
```

### `pipeline.py monitor`

Сводка портфеля SOL + опционных позиций. Анализ Greeks, PnL, генерация рекомендаций (закрыть / роллировать / мониторить / держать).

```bash
./venv/bin/python src/pipeline.py monitor
```

### `pipeline.py run`

Полный цикл: fetch → select → monitor. Вывод статуса каждого шага.

```bash
./venv/bin/python src/pipeline.py run
```

---

## Модули

### 1. OptionBoard.py — Data Ingestion

См. [[301-optionboard-script]]

### 2. anchor_picker.py — Option Selection

См. [[203-anchor-selection-algorithm]]

### 3. monitor_options.py — Portfolio Monitoring

См. [[T004-monitor-open-options]]

### 4. LastPrice.py — Price Enrichment

См. [[302-lastprice-script]]

---

## Схема данных

```
Bybit API → OptionBoard.py → excel/sol_options_chain.xlsx
                                      ↓
                              anchor_picker.py (config + position + excel)
                                      ↓
                              monitor_options.py (registry + excel)
                                      ↓
                          Рекомендации → пользователь
```

---

*Создано: 2026-05-28 | Обновлено: 2026-06-16*
