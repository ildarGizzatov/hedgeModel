#!/usr/bin/env python3
"""
edit_option.py — CLI для редактирования опционов в БД.

Использование:
    python src/edit_option.py              # интерактивный режим
    python src/edit_option.py --list       # показать все опционы
    python src/edit_option.py --list --all # показать все (вкл. закрытые)
    python src/edit_option.py --edit 5     # редактировать option id=5
    python src/edit_option.py --edit 5 --field entry_price --value 2.50  # быстрое обновление
"""

import argparse
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.db import get_all_options, get_option_by_id, update_option

# ============================================================
# ЦВЕТОВАЯ ПАЛИТРА
# ============================================================
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"

# ============================================================
# УТИЛИТЫ
# ============================================================

def print_table(rows: list[dict], fields: list[str]) -> None:
    """Печать таблицы в стиле SQLite."""
    if not rows:
        print("  (пусто)")
        return

    # Вычисляем ширину колонок
    col_widths = {f: len(f) for f in fields}
    for row in rows:
        for f in fields:
            val = str(row.get(f, ""))
            col_widths[f] = max(col_widths[f], len(val))

    # Header
    header = "  ".join(f"{f:<{col_widths[f]}}" for f in fields)
    print(header)
    print("  ".join("-" * col_widths[f] for f in fields))

    # Rows
    for row in rows:
        vals = []
        for f in fields:
            val = row.get(f, "")
            if val is None:
                val = "NULL"
            vals.append(str(val))
        print("  ".join(f"{v:<{col_widths[f]}}" for v, f in zip(vals, fields)))


# ============================================================
# ФОРМАТИРОВАНИЕ
# ============================================================

LAYER_COLORS = {
    "anchor": CYAN,
    "adaptation": YELLOW,
    "active": GREEN,
}


def fmt_option(row: dict) -> dict:
    """Добавляем цветовую разметку и удобный формат."""
    r = dict(row)
    layer = r.get("layer", "")
    color = LAYER_COLORS.get(layer, "")
    r["_layer_fmt"] = f"{color}{layer}{RESET}" if layer else "—"
    return r


# ============================================================
# ОТОБРАЖЕНИЕ
# ============================================================

def show_options(filter_status: str = "open", layer: str = None):
    """Показать список опционов."""
    rows = get_all_options(layer=layer, status=filter_status)
    if not rows:
        print("  (нет опционов)")
        return

    print(f"\n{BOLD}Опционы{' (' + filter_status + ')' if filter_status else ''}{' | layer=' + layer if layer else ''}{RESET}\n")

    # Добавляем форматированный слой
    for r in rows:
        layer = r.get("layer", "")
        color = LAYER_COLORS.get(layer, "")
        r["layer_fmt"] = f"{color}{layer}{RESET}" if layer else "—"

    fields = ["id", "symbol", "type", "strike", "expiry", "qty", "entry_price", "layer_fmt", "status", "entry_date"]
    print_table(rows, fields)


def show_single_option(option_id: int):
    """Показать один опцион с полями для редактирования."""
    row = get_option_by_id(option_id)
    if not row:
        print(f"{RED}❌ Опцион id={option_id} не найден{RESET}")
        return False

    print(f"\n{BOLD}Опцион id={row['id']} — {row['symbol']}{RESET}\n")
    print_table([dict(row)], ["id", "symbol", "type", "strike", "expiry",
                              "qty", "entry_price", "iv_entry", "delta_entry",
                              "gamma_entry", "theta_entry", "vega_entry",
                              "layer", "status", "entry_date", "notes"])
    return True


# ============================================================
# РЕДАКТИРОВАНИЕ
# ============================================================

EDITABLE_FIELDS = {
    "entry_price":  ("Цена покупки",      "float",  None),
    "qty":          ("Количество (лоты)", "int",    1),
    "notes":        ("Заметки",           "str",    ""),
    "layer":        ("Слой",              "str",    None),
    "iv_entry":     ("IV при покупке",    "float",  None),
    "delta_entry":  ("Delta при покупке", "float",  None),
    "gamma_entry":  ("Gamma при покупке", "float",  None),
    "theta_entry":  ("Theta при покупке", "float",  None),
    "vega_entry":   ("Vega при покупке",  "float",  None),
    "status":       ("Статус",            "str",    None),
}


def edit_option(option_id: int) -> bool:
    """Интерактивное редактирование одного опциона."""
    row = get_option_by_id(option_id)
    if not row:
        print(f"{RED}❌ Опцион id={option_id} не найден{RESET}")
        return False

    # Если опцион закрыт — только notes
    if row["status"] == "closed":
        print(f"{YELLOW}⚠️ Опцион закрыт. Редактируются только заметки.{RESET}\n")

    print(f"{BOLD}Редактирование: {row['symbol']} (id={option_id}){RESET}\n")

    # Показываем текущее значение
    print(f"  Текущие данные:")
    print(f"    entry_price = {row['entry_price']}")
    print(f"    qty         = {row['qty']}")
    print(f"    layer       = {row['layer']}")
    print(f"    notes       = {row['notes']}")
    print()

    # Показываем доступные поля
    print(f"{BOLD}Доступные поля:{RESET}")
    for i, (key, (label, ftype, _)) in enumerate(EDITABLE_FIELDS.items(), 1):
        current = row.get(key, "—")
        if row["status"] == "closed" and key != "notes":
            print(f"  {i:2d}. {label:<25s} {current:<10s} (закрыт, только notes)")
        else:
            print(f"  {i:2d}. {label:<25s} {str(current):<10s}")
    print(f"  99. Сохранить и выйти")
    print()

    # Собираем изменения
    changes = {}
    while True:
        choice = input(f"{CYAN}>> {RESET}Номер поля (или 0 для отмены, 99 для сохранения): ").strip()

        if choice == "99":
            if not changes:
                print("  Нет изменений. Выход.")
                return True
            break
        elif choice == "0":
            return False
        elif not choice.isdigit():
            print(f"  {RED}Введите число{RESET}")
            continue

        choice = int(choice)

        if choice == 0:
            return False
        elif choice == 99:
            if not changes:
                print("  Нет изменений. Выход.")
                return True
            break
        elif choice not in range(1, len(EDITABLE_FIELDS) + 1):
            print(f"  {RED}Нет такого поля{RESET}")
            continue

        field_key = list(EDITABLE_FIELDS.keys())[choice - 1]
        _, (label, ftype, default) = EDITABLE_FIELDS[field_key]

        if row["status"] == "closed" and field_key != "notes":
            print(f"  {RED}❌ Поле доступно только для опционов со статусом 'open'{RESET}")
            continue

        current = row.get(field_key, "")
        if current is None:
            current = ""
        prompt = f"  {label} [{current}]:" if current else f"  {label} [{default}]:"
        val = input(prompt).strip()

        if val == "":
            if default is not None:
                val = default
            else:
                print(f"  {YELLOW}  Отмена для этого поля{RESET}")
                continue

        # Приведение типов
        try:
            if ftype == "float":
                val = float(val)
            elif ftype == "int":
                val = int(val)
            # str — без изменений
        except ValueError:
            print(f"  {RED}❌ Ошибка: не могу привести к {ftype}{RESET}")
            continue

        changes[field_key] = val
        print(f"  {GREEN}  ✅ {label} = {val}{RESET}")

    # Подтверждение
    if changes:
        print(f"\n{BOLD}Изменения:{RESET}")
        for field, val in changes.items():
            old = row.get(field, "—")
            color = GREEN if val != old else YELLOW
            print(f"  {field}: {old} → {color}{val}{RESET}")

        confirm = input(f"\n{GREEN}Применить? (y/n): {RESET}").strip().lower()
        if confirm != "y":
            print("  Отменено.")
            return False

        # Применяем
        try:
            updated = update_option(option_id, **changes)
            if updated:
                print(f"\n  {GREEN}✅ Опцион id={option_id} обновлён ({updated} строк){RESET}")
            else:
                print(f"  {YELLOW}⚠️ Изменений нет{RESET}")
            return True
        except ValueError as e:
            print(f"  {RED}❌ {e}{RESET}")
            return False

    return True


def quick_edit(option_id: int, field: str, value: str):
    """Быстрое обновление одного поля."""
    if field not in EDITABLE_FIELDS:
        print(f"{RED}❌ Неизвестное поле: {field}{RESET}")
        print(f"   Доступные: {', '.join(EDITABLE_FIELDS.keys())}")
        return False

    label, ftype, _ = EDITABLE_FIELDS[field]
    try:
        if ftype == "float":
            value = float(value)
        elif ftype == "int":
            value = int(value)
    except ValueError:
        print(f"{RED}❌ Не могу привести '{value}' к {ftype}{RESET}")
        return False

    row = get_option_by_id(option_id)
    if not row:
        print(f"{RED}❌ Опцион id={option_id} не найден{RESET}")
        return False

    if row["status"] == "closed" and field != "notes":
        print(f"{RED}❌ Опцион закрыт. Доступно только поле 'notes'.{RESET}")
        return False

    old = row.get(field)
    try:
        update_option(option_id, **{field: value})
        print(f"  {GREEN}✅ {field}: {old} → {value}{RESET}")
        return True
    except ValueError as e:
        print(f"  {RED}❌ {e}{RESET}")
        return False


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Редактирование опционов в HedgeModel БД")
    parser.add_argument("--list", action="store_true", help="Показать открытые опционы")
    parser.add_argument("--all", action="store_true", help="Показать все опционы (вкл. закрытые)")
    parser.add_argument("--layer", type=str, help="Фильтр по слою (anchor/adaptation/active)")
    parser.add_argument("--show", type=int, metavar="ID", help="Показать опцион по ID")
    parser.add_argument("--edit", type=int, metavar="ID", help="Редактировать опцион по ID")
    parser.add_argument("--field", type=str, help="Поле для --quick-edit")
    parser.add_argument("--value", type=str, help="Новое значение для --quick-edit")

    args = parser.parse_args()

    # --list
    if args.list or (not args.list and not args.all and not args.show and not args.edit):
        show_options(filter_status="open", layer=args.layer)

    # --all
    if args.all:
        show_options(filter_status=None, layer=args.layer)

    # --show
    if args.show is not None:
        show_single_option(args.show)

    # --edit (интерактивный)
    if args.edit is not None and not args.field:
        edit_option(args.edit)

    # --edit + --field (быстрое)
    if args.edit is not None and args.field and args.value:
        quick_edit(args.edit, args.field, args.value)

    # --edit + --field без --value
    if args.edit is not None and args.field and not args.value:
        print(f"{RED}❌ Укажите --value для быстрого редактирования{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
