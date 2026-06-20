#!/usr/bin/env python3
"""Генерация config.toml из документации.

Запуск: python gen_config.py

Читает docs/200-budget-allocation.md и docs/201-selection-criteria.md,
извлекает все параметры и перезаписывает config.toml.
"""

import re
import sys
from datetime import datetime
from pathlib import Path


def extract_section(text, section_name):
    pattern = rf"##\s+{re.escape(section_name)}.*?(?=##\s+|$)"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(0) if match else ""


def parse_budget(doc_path):
    """Парсит docs/200-budget-allocation.md."""
    if not doc_path.exists():
        return {}

    text = doc_path.read_text()
    result = {}

    # Параметры бюджета: `global_budget_pct` | 5% | ...
    for key in ("global_budget_pct", "target_dd_pct"):
        m = re.search(rf"`{re.escape(key)}`\s+\|\s+(\d+)%", text)
        if m:
            result[key] = int(m.group(1))

    # Распределение по слоям: Anchor | 50% | ...
    section = extract_section(text, "Распределение по слоям")
    for layer in ("Anchor", "Adaptation", "Active"):
        m = re.search(rf"{layer}\s+\|\s+(\d+)%", section)
        if m:
            result[f"{layer.lower()}_pct"] = int(m.group(1))

    return result


def parse_anchor_split(doc_path):
    """Парсит docs/200-budget-allocation.md — Распределение Anchor бюджета."""
    if not doc_path.exists():
        return {}

    text = doc_path.read_text()
    section = extract_section(text, "Распределение Anchor бюджета")
    if not section:
        return {}

    result = {}
    # Core | 60% | ...
    core_m = re.search(r"Core\s+\|\s+(\d+)%", section)
    if core_m:
        result["core_pct"] = int(core_m.group(1))
    # Tail | 40% | ...
    tail_m = re.search(r"Tail\s+\|\s+(\d+)%", section)
    if tail_m:
        result["tail_pct"] = int(tail_m.group(1))

    return result


def parse_filter(doc_path):
    """Парсит docs/201-selection-criteria.md — Anchor Layer."""
    if not doc_path.exists():
        return {}

    text = doc_path.read_text()
    anchor = extract_section(text, "Anchor Layer")
    if not anchor:
        return {}

    result = {}

    # Delta: "0.05 – 0.20"
    delta_m = re.search(r"Delta\s+\|\s+([\d.]+)\s*–\s*([\d.]+)", anchor)
    if delta_m:
        result["min_delta"] = float(delta_m.group(1))
        result["max_delta"] = float(delta_m.group(2))

    # DTE: ">= 25"
    dte_m = re.search(r"DTE\s+\|\s+>=?\s*(\d+)", anchor)
    if dte_m:
        result["min_dte"] = int(dte_m.group(1))

    # Distance: "≥ 15%" или "10–20%"
    single = re.search(r"[≥>]+\s*(\d+)%", anchor)
    if single:
        result["dist_min_pct"] = int(single.group(1))
    else:
        pair = re.search(r"(\d+)\s*[–\-]\s*(\d+)%", anchor)
        if pair:
            result["dist_min_pct"] = int(pair.group(1))

    return result


def main():
    base = Path(__file__).resolve().parent
    budget_path = base / "docs" / "200-budget-allocation.md"
    filter_path = base / "docs" / "201-selection-criteria.md"
    cfg_path = base / "config.toml"

    budget = parse_budget(budget_path)
    filter_ = parse_filter(filter_path)
    anchor_split = parse_anchor_split(budget_path)

    if not budget or not filter_ or not anchor_split:
        print("Не удалось извлечь параметры из документации")
        sys.exit(1)

    config = f"""# Генерируется: gen_config.py
# Источники: docs/200-budget-allocation.md, docs/201-selection-criteria.md
# Обновлено: {datetime.now().strftime('%Y-%m-%d %H:%M')}

# Процент от суммы покупки SOL, который можно потратить на весь хедж
global_budget_pct = {budget['global_budget_pct']}

# Целевая просадка от Avg Buy Price, при которой хедж начинает защищать
target_dd_pct = {budget['target_dd_pct']}

# Распределение глобального бюджета по слоям (в %)
[layer_allocation]
Anchor = {budget['anchor_pct']}       # Дальний слой — Tail Risk, структурная защита
Adaptation = {budget['adaptation_pct']}   # Средний слой — стабилизация PnL
Active = {budget['active_pct']}       # Ближний слой — монетизация движения

[anchor_filter]
# Минимальный DTE (дни)
min_dte = {filter_['min_dte']}
# Минимальная дистанция от спота (%, ниже — опцион слишком близко к споту)
dist_min_pct = {filter_['dist_min_pct']}
# Максимальный |Delta| — ограничение сверху
max_delta = {filter_['max_delta']}
# Минимальный |Delta| (антипаттерн: меньше — слишком дешёвый)
min_delta = {filter_['min_delta']}

[anchor_budget_split]
# Core = {anchor_split['core_pct']}% бюджета Anchor Layer (ядро)
core_pct = {anchor_split['core_pct']}
# Tail = {anchor_split['tail_pct']}% бюджета Anchor Layer (усиление)
tail_pct = {anchor_split['tail_pct']}
"""

    cfg_path.write_text(config)
    print(f"Обновлён: {cfg_path}")


if __name__ == "__main__":
    main()
