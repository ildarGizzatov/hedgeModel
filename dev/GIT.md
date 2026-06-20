# Git — как работать

## Подключение (один раз)
Репозиторий уже подключён: `git@github.com:ildarGizzatov/hedgeModel.git`, ветка `main`.

## Команды

### Закоммитить изменения
```bash
cd /home/maks/projects/hedgeModel
git add -A
git commit -m "описание что сделал"
```

### Отправить на GitHub
```bash
git push origin main
```

### Получить обновления с GitHub
```bash
git pull origin main
```

### Посмотреть что изменилось
```bash
git status
```

### Посмотреть историю коммитов
```bash
git log --oneline -10
```

## Что обычно коммитим
- `src/` — код
- `data/` — CSV с позициями
- `excel/` — Excel-файлы (по согласованию)
- `docs/` — документация
- `config.toml` — конфиг

## Не коммитим
- `.obsidian/` — заметки Obsidian
- `venv/` — виртуальное окружение
