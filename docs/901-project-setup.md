# Настройка проекта

## Источники параметров

| Источник | Для чего | Как обновить |
|---|---|---|
| `docs/201-selection-criteria.md` | Параметры фильтрации опционов | Руками → `python gen_config.py` |
| `config.toml` | Готовый конфиг для скриптов | Автоматически из `gen_config.py` |
| `data/open_positions.csv` | Текущая позиция SOL | Обновляешь при покупке/продаже |
| `excel/sol_options_chain.xlsx` | Данные опционов | Скачиваешь через `src/OptionBoard.py` |

## Порядок запуска

1. `python gen_config.py` — генерирует `config.toml` из `docs/201-selection-criteria.md`
2. `python src/anchor_picker.py` — подбирает Anchor Layer (Core + Tail)
3. `python src/OptionBoard.py` — скачивает данные опционов в Excel
4. ...

## Обновление параметров стратегии

1. Редактируешь `docs/201-selection-criteria.md` (меняешь числа в таблицах)
2. Запускаешь `python gen_config.py`
3. Проверяешь что `config.toml` обновился
4. Запускаешь `src/anchor_picker.py` — скрипт использует новые параметры

## Структура файлов

```
hedgeModel/
├── config.toml              # Сгенерированный конфиг (не редактировать)
├── gen_config.py            # Генератор конфига из документации
├── docs/
│   └── 201-selection-criteria.md  # ИСТОЧНИК ПАРАМЕТРОВ (ручной ввод)
├── src/
│   ├── anchor_picker.py     # Подбор Anchor Layer
│   └── OptionBoard.py       # Скачивание данных опционов
├── data/
│   └── open_positions.csv   # Текущая позиция SOL
└── excel/
    └── sol_options_chain.xlsx  # Данные опционов от Bybit
```

## Важные правила

- **Параметры стратегии** → только в `docs/201-selection-criteria.md`
- **Конфиг** → всегда генерируй через `gen_config.py`, не правь руками
- **Данные** → `open_positions.csv` и `sol_options_chain.xlsx` — рабочие файлы, обновляй регулярно
