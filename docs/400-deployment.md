---
type: ops
status: active
related: [[300-pipeline]], [[301-optionboard-script]], [[302-lastprice-script]]
created: 2026-05-29
updated: 2026-05-29
---
# Деплой и запуск

> Инструкции по запуску, cron-задачам и поддержке окружения.

---

## Окружение

| Параметр | Значение |
|----------|----------|
| Рабочая директория | `/home/maks/projects/hedgeModel` |
| Python venv | `/home/maks/projects/hedgeModel/venv` |
| Интерпретатор | `/home/maks/projects/hedgeModel/venv/bin/python` |

## Запуск

### OptionBoard.py

```bash
cd /home/maks/projects/hedgeModel
./venv/bin/python src/OptionBoard.py
```

### LastPrice.py

```bash
cd /home/maks/projects/hedgeModel
./venv/bin/python src/LastPrice.py
```


## Логирование

```bash
mkdir -p /home/maks/projects/hedgeModel/logs
```

- `logs/optionboard.log` — вывод OptionBoard
- `logs/lastprice.log` — вывод LastPrice

## Мониторинг

```bash
# Проверить, что Excel обновлён
stat excel/sol_options_chain.xlsx

# Проверить логи
tail -f logs/optionboard.log
tail -f logs/lastprice.log

# Проверить данные
./venv/bin/python -c "import pandas as pd; df = pd.read_excel('excel/sol_options_chain.xlsx', 'OptionBoard'); print(f'Records: {len(df)}')"
```

---

*Создано: 2026-05-29 | Обновлено: 2026-05-29*
