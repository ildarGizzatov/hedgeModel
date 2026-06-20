#!/usr/bin/env python3
"""
T007 — Dashboard FastAPI backend.

Читает CSV-файлы проекта и отдаёт JSON для 4 эндпоинтов:
  /api/positions    — позиции по активам
  /api/options      — опционные позиции
  /api/recommendations — рекомендации модели
  /api/summary      — сводка портфеля

Запуск:
  pip install fastapi uvicorn pandas
  cd dashboard && python server.py
"""

import os
import csv
import math
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# ==========================================
# CONFIG
# ==========================================

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"

PORT = int(os.environ.get("DASHBOARD_PORT", "8083"))

app = FastAPI(title="HedgeModel Dashboard", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# УТИЛИТЫ
# ==========================================

def read_csv(filename: str) -> list[dict]:
    """Read CSV file, return list of dicts."""
    path = DATA_DIR / filename
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def calc_dte(expiry_str: str) -> int:
    """Days to expiry."""
    try:
        expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        return max((expiry - date.today()).days, 0)
    except Exception:
        return 0


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ЭНДПОИНТЫ
# ==========================================

import subprocess


@app.post("/api/update-options")
def api_update_options() -> dict:
    """Запускает monitor_options.py для обновления опционов и цен."""
    try:
        cmd = [
            sys.executable, str(PROJECT_DIR / "src" / "monitor_options.py"),
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            output += "\n" + result.stderr.strip()
        return {"status": "ok", "output": output}
    except subprocess.TimeoutExpired:
        return {"status": "error", "output": "Timeout after 120s"}
    except Exception as e:
        return {"status": "error", "output": str(e)}


@app.post("/api/refresh-prices")
def api_refresh_prices() -> dict:
    """Обновляет текущие цены через pipeline."""
    try:
        cmd = [
            sys.executable, str(PROJECT_DIR / "src" / "pipeline.py"), "prices",
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            output += "\n" + result.stderr.strip()
        # Перечитываем данные
        rows = read_csv("open_positions.csv")
        tracking = read_csv("options_tracking.csv")
        return {
            "status": "ok",
            "output": output,
            "positions": rows,
            "options": tracking,
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "output": "Timeout after 60s"}
    except Exception as e:
        return {"status": "error", "output": str(e)}


@app.post("/api/close-option")
def api_close_option() -> dict:
    """Закрывает опцион: переводит его из open в closed, переносит в closed_positions."""
    import shutil
    try:
        import tomllib
        cfg_path = PROJECT_DIR / "config.toml"
        if cfg_path.exists():
            with open(cfg_path, "rb") as f:
                config = tomllib.load(f)
        else:
            config = {}
        
        target_dd = config.get("target_dd_pct", 20) / 100
        close_pct = config.get("close_pct", 100) / 100
        
        registry = read_csv("options_registry.csv")
        tracking = read_csv("options_tracking.csv")
        closed = read_csv("closed_positions.csv")
        
        # Найти open опционы с PnL < -close_pct
        to_close = []
        new_registry = []
        
        for r in registry:
            if r.get("status", "").strip() != "open":
                new_registry.append(r)
                continue
            
            symbol = r.get("symbol", "")
            t = next((x for x in tracking if x.get("symbol")==symbol), {})
            entry_price = float(r.get("entry_price", 0))
            current_price = float(t.get("current_price", entry_price))
            qty = int(r.get("qty", 1))
            pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
            
            if pnl_pct < -close_pct:
                to_close.append({
                    "symbol": symbol,
                    "pnl_pct": round(pnl_pct, 2),
                    "entry_price": entry_price,
                    "current_price": round(current_price, 4),
                    "qty": qty,
                    "pnl": round((current_price - entry_price) * qty, 2),
                    "strike": r.get("strike", ""),
                    "expiry": r.get("expiry", ""),
                })
            else:
                new_registry.append(r)
        
        # Записать в closed_positions
        for item in to_close:
            closed.append({
                "date": date.today().strftime("%Y-%m-%d"),
                "qty": item["qty"],
                "price_closed": item["current_price"],
                "avg_price": item["entry_price"],
                "pnl": item["pnl"],
                "symbol": item["symbol"],
                "notes": f"Автозакрытие: PnL={item['pnl_pct']}% < -{int(close_pct*100)}%",
            })
        
        # Сохранить
        closed_path = DATA_DIR / "closed_positions.csv"
        with open(closed_path, "w", newline="", encoding="utf-8") as f:
            if closed:
                writer = csv.DictWriter(f, fieldnames=closed[0].keys())
                writer.writeheader()
                writer.writerows(closed)
        
        reg_path = DATA_DIR / "options_registry.csv"
        with open(reg_path, "w", newline="", encoding="utf-8") as f:
            if new_registry:
                writer = csv.DictWriter(f, fieldnames=new_registry[0].keys())
                writer.writeheader()
                writer.writerows(new_registry)
        
        return {
            "status": "ok",
            "closed": to_close,
            "count": len(to_close),
            "message": f"Закрыто {len(to_close)} опционов",
        }
    except Exception as e:
        return {"status": "error", "output": str(e)}


# ==========================================
# ЭНДПОИНТ 1: ПОЗИЦИИ ПО АКТИВАМ
# ==========================================

@app.get("/api/positions")
def api_positions() -> dict[str, Any]:
    """Позиции по активам (акции/крипта)."""
    rows = read_csv("open_positions.csv")
    
    positions = []
    total_cost = 0.0
    total_value = 0.0
    total_pnl = 0.0
    
    for r in rows:
        try:
            qty = float(r.get("qty", 0))
            avg_price = float(r.get("avg_price", 0))
            total_cost_val = float(r.get("total_cost", 0))
            current_price = float(r.get("current_price", 0))
            value = float(r.get("total_value", 0))
            pnl = float(r.get("pnl", 0))
        except (ValueError, TypeError):
            continue
        
        if qty <= 0:
            continue
        
        total_cost += total_cost_val
        total_value += value
        total_pnl += pnl
        
        positions.append({
            "symbol": r.get("symbol", ""),
            "qty": qty,
            "avg_price": avg_price,
            "total_cost": total_cost_val,
            "current_price": current_price,
            "total_value": value,
            "pnl": pnl,
            "pnl_pct": (pnl / total_cost_val * 100) if total_cost_val > 0 else 0,
        })
    
    # === История покупок (из buy_history.csv) ===
    buy_history = read_csv("buy_history.csv")
    buy_records = []
    if positions:
        current_price = positions[0]["current_price"]
        for b in buy_history:
            try:
                b_qty = float(b.get("qty", 0))
                b_price = float(b.get("price", 0))
                b_total = float(b.get("total", 0))
                b_pnl = (current_price - b_price) * b_qty
                b_pnl_pct = ((current_price - b_price) / b_price * 100) if b_price > 0 else 0
                buy_records.append({
                    "date": b.get("date", ""),
                    "qty": b_qty,
                    "price": b_price,
                    "total": b_total,
                    "pnl": round(b_pnl, 2),
                    "pnl_pct": round(b_pnl_pct, 2),
                    "notes": b.get("notes", ""),
                })
            except (ValueError, TypeError):
                continue
    
    # === PnL-лестница по шагу $1 (от avg-цены ± 20%) ===
    for p in positions:
        qty = p["qty"]
        avg = p["avg_price"]
        current = p["current_price"]
        
        # Диапазон: avg ± 20%, шаг $1
        low = round(avg * 0.80)
        high = round(avg * 1.20)
        
        ladder = []
        for price in range(low, high + 1):
            pnl = (price - avg) * qty
            pnl_pct = ((price - avg) / avg * 100) if avg > 0 else 0
            is_current = price == round(current)
            is_avg = price == round(avg)
            ladder.append({
                "price": price,
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "is_current": is_current,
                "is_avg": is_avg,
            })
        
        p["pnl_ladder"] = ladder
        p["buy_history"] = buy_records
    
    return {
        "positions": positions,
        "totals": {
            "total_cost": round(total_cost, 2),
            "total_value": round(total_value, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": (total_pnl / total_cost * 100) if total_cost > 0 else 0,
        },
        "updated": date.today().strftime("%Y-%m-%d"),
    }


# ==========================================
# ЭНДПОИНТ 2: ОПЦИОННЫЕ ПОЗИЦИИ
# ==========================================

@app.get("/api/options")
def api_options() -> dict[str, Any]:
    """Опционные позиции с Greeks и метриками."""
    registry = read_csv("options_registry.csv")
    tracking = read_csv("options_tracking.csv")
    
    # Индекс из tracking
    tracking_idx = {}
    for t in tracking:
        tracking_idx[t.get("symbol", "")] = t
    
    options = []
    total_opt_cost = 0.0
    total_opt_value = 0.0
    total_opt_pnl = 0.0
    
    for r in registry:
        if r.get("status", "").strip() != "open":
            continue
        
        symbol = r.get("symbol", "").strip()
        entry_price = float(r.get("entry_price", 0))
        qty = int(r.get("qty", 1))
        total_cost_val = float(r.get("total_cost", 0))
        strike = float(r.get("strike", 0))
        expiry = r.get("expiry", "")
        layer = r.get("layer", "").strip()
        
        t = tracking_idx.get(symbol, {})
        
        current_price = float(t.get("current_price", entry_price))
        pnl = (current_price - entry_price) * qty
        delta = float(t.get("delta", 0))
        gamma = float(t.get("gamma", 0))
        theta = float(t.get("theta", 0))
        vega = float(t.get("vega", 0))
        dte = int(t.get("dte", calc_dte(expiry)))
        iv = float(t.get("iv", 0))
        iv_atm = float(t.get("iv_atm", 0))
        intrinsic = float(t.get("intrinsic_value", 0))
        
        entry_delta = float(r.get("delta_entry", 0))
        entry_gamma = float(r.get("gamma_entry", 0))
        entry_theta = float(r.get("theta_entry", 0))
        entry_vega = float(r.get("vega_entry", 0))
        iv_entry = float(r.get("iv_entry", 0))
        
        total_cost_val_r = float(r.get("total_cost", 0))
        total_opt_cost += total_cost_val_r
        total_opt_value += current_price * qty
        total_opt_pnl += pnl
        
        # Theta decay за день (absolute value)
        theta_per_day = theta * qty
        
        # Cost of carry — сколько стоит держать опцион день
        cost_per_day = abs(theta_per_day)
        
        options.append({
            "symbol": symbol,
            "type": r.get("type", ""),
            "strike": strike,
            "expiry": expiry,
            "qty": qty,
            "layer": layer,
            "entry_price": entry_price,
            "current_price": round(current_price, 4),
            "pnl": round(pnl, 2),
            "pnl_pct": ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0,
            "delta": round(delta, 4),
            "delta_entry": round(entry_delta, 4),
            "delta_change": round(delta - entry_delta, 4),
            "gamma": round(gamma, 4),
            "gamma_entry": round(entry_gamma, 4),
            "gamma_change": round(gamma - entry_gamma, 4),
            "theta": round(theta, 4),
            "theta_entry": round(entry_theta, 4),
            "theta_per_day": round(theta_per_day, 4),
            "vega": round(vega, 4),
            "vega_entry": round(entry_vega, 4),
            "dte": dte,
            "iv": round(iv, 4),
            "iv_entry": round(iv_entry, 4),
            "iv_change": round(iv - iv_entry, 4),
            "iv_atm": round(iv_atm, 4),
            "intrinsic_value": round(intrinsic, 4),
            "cost_per_day": round(cost_per_day, 4),
        })
    
    return {
        "options": options,
        "totals": {
            "total_cost": round(total_opt_cost, 2),
            "total_value": round(total_opt_value, 2),
            "total_pnl": round(total_opt_pnl, 2),
            "total_pnl_pct": (total_opt_pnl / total_opt_cost * 100) if total_opt_cost > 0 else 0,
            "total_theta_per_day": round(sum(o["theta_per_day"] for o in options), 4),
            "net_delta": round(sum(o["delta"] * o["qty"] for o in options), 4),
            "net_gamma": round(sum(o["gamma"] * o["qty"] for o in options), 4),
            "net_theta": round(sum(o["theta"] * o["qty"] for o in options), 4),
            "net_vega": round(sum(o["vega"] * o["qty"] for o in options), 4),
        },
        "updated": date.today().strftime("%Y-%m-%d"),
    }


# ==========================================

# ==========================================
# ЭНДПОИНТ: СЛОИ (LAYER BUDGETS)
# ==========================================

@app.get("/api/layers")
def api_layers() -> dict:
    """Бюджеты и затраты по слоям."""
    import tomllib
    
    config_path = PROJECT_DIR / "config.toml"
    with open(config_path, "rb") as f:
        config = tomllib.load(f)
    
    # Позиции для расчёта бюджета
    pos_data = api_positions()
    positions = pos_data["positions"]
    
    if not positions:
        return {"layers": [], "position_size": 0, "total_budget": 0, "free_budget": 0, "updated": date.today().strftime("%Y-%m-%d")}
    
    sol_qty = sum(p["qty"] for p in positions if p["symbol"].upper().startswith("SOL"))
    sol_avg = sum(p.get("avg_price", 0) for p in positions if p["symbol"].upper().startswith("SOL"))
    
    if sol_qty <= 0:
        return {"layers": [], "position_size": 0, "total_budget": 0, "free_budget": 0, "updated": date.today().strftime("%Y-%m-%d")}
    
    position_size = sol_qty * sol_avg
    global_budget_pct = config.get("global_budget_pct", 5)
    total_budget = position_size * global_budget_pct / 100
    
    layers_alloc = config.get("layer_allocation", {})
    
    # Факт по слоям
    spent = {}
    opts_by_layer = {}
    try:
        with open(DATA_DIR / "options_registry.csv") as f:
            for r in csv.DictReader(f):
                if r.get("status", "").strip().lower() != "open":
                    continue
                layer = r.get("layer", "").strip().lower()
                cost = float(r.get("total_cost", 0))
                spent[layer] = spent.get(layer, 0) + cost
                opts_by_layer.setdefault(layer, []).append({
                    "symbol": r.get("symbol", ""),
                    "strike": r.get("strike", ""),
                    "expiry": r.get("expiry", ""),
                    "qty": int(r.get("qty", 1)),
                    "entry_price": float(r.get("entry_price", 0)),
                    "total_cost": cost,
                })
    except FileNotFoundError:
        pass
    
    # Трекинг для PnL
    tracking = {}
    try:
        with open(DATA_DIR / "options_tracking.csv") as f:
            for r in csv.DictReader(f):
                tracking[r.get("symbol", "")] = r
    except FileNotFoundError:
        pass
    
    layer_names = ["Anchor", "Adaptation", "Active"]
    layers_data = []
    
    for name in layer_names:
        budget = total_budget * layers_alloc.get(name, 0) / 100
        fact = spent.get(name.lower(), 0)
        opts = opts_by_layer.get(name.lower(), [])
        
        # PnL по слоям
        layer_pnl = 0
        for o in opts:
            sym = o["symbol"]
            t = tracking.get(sym, {})
            cur = float(t.get("current_price", o["entry_price"]))
            qty = o["qty"]
            layer_pnl += (cur - o["entry_price"]) * qty
        
        layers_data.append({
            "name": name,
            "budget": round(budget, 2),
            "spent": round(fact, 2),
            "pnl": round(layer_pnl, 2),
            "count": len(opts),
            "opts": opts,
        })
    
    total_spent = sum(l["spent"] for l in layers_data)
    
    return {
        "layers": layers_data,
        "position_size": round(position_size, 2),
        "total_budget": round(total_budget, 2),
        "free_budget": round(total_budget - total_spent, 2),
        "updated": date.today().strftime("%Y-%m-%d"),
    }


# ЭНДПОИНТ 3: РЕКОМЕНДАЦИИ МОДЕЛИ
# ==========================================

@app.get("/api/recommendations")
def api_recommendations() -> dict[str, Any]:
    """Рекомендации от anchor_picker (T006) и monitor_options."""
    
    recommendations = []
    suggestions = []
    
    # --- T006: Anchor Selection ---
    try:
        import tomllib
        cfg_path = PROJECT_DIR / "config.toml"
        if cfg_path.exists():
            with open(cfg_path, "rb") as f:
                config = tomllib.load(f)
        else:
            config = {}
        
        # Читаем текущие данные
        chain_path = PROJECT_DIR / "excel" / "sol_options_chain.xlsx"
        positions = read_csv("open_positions.csv")
        
        if chain_path.exists() and positions:
            chain = pd.read_excel(chain_path, sheet_name="OptionBoard")
            if "spot_price" in chain.columns:
                spot = chain["spot_price"].iloc[0]
            else:
                spot = 0
            
            sol_pos = None
            for p in positions:
                if p.get("symbol", "").upper().startswith("SOL"):
                    sol_pos = p
                    break
            
            if sol_pos and spot > 0:
                qty = float(sol_pos.get("qty", 0))
                avg_price = float(sol_pos.get("avg_price", 0))
                
                if qty > 0 and avg_price > 0:
                    target_dd = config.get("target_dd_pct", 20) / 100
                    global_budget = config.get("global_budget_pct", 15) / 100
                    anchor_layer_pct = config.get("layer_allocation", {}).get("Anchor", 50) / 100
                    
                    position_size = qty * avg_price
                    total_budget = position_size * global_budget
                    anchor_budget = total_budget * anchor_layer_pct
                    s_target = avg_price * (1 - target_dd)
                    
                    recommendations.append({
                        "type": "anchor_selection",
                        "title": "Anchor Layer Selection (T006)",
                        "spot": round(spot, 2),
                        "avg_price": avg_price,
                        "s_target": round(s_target, 2),
                        "position_size": round(position_size, 2),
                        "total_budget": round(total_budget, 2),
                        "anchor_budget": round(anchor_budget, 2),
                        "qty": qty,
                        "message": f"Anchor budget: ${anchor_budget:.2f} | Target level: ${s_target:.2f} | Spot: ${spot:.2f}",
                    })
    except Exception as e:
        recommendations.append({
            "type": "error",
            "title": "Anchor Selection",
            "message": f"Ошибка расчёта: {e}",
        })
    
    # --- Рекомендации от monitor_options ---
    registry = read_csv("options_registry.csv")
    tracking = read_csv("options_tracking.csv")
    
    for r in registry:
        if r.get("status", "").strip() != "open":
            continue
        
        symbol = r.get("symbol", "").strip()
        layer = r.get("layer", "").strip()
        entry_price = float(r.get("entry_price", 0))
        qty = int(r.get("qty", 1))
        
        t = {}
        for tr in tracking:
            if tr.get("symbol", "") == symbol:
                t = tr
                break
        
        current_price = float(t.get("current_price", entry_price))
        pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        dte = int(t.get("dte", calc_dte(r.get("expiry", ""))))
        delta = abs(float(t.get("delta", 0)))
        gamma = float(t.get("gamma", 0))
        gamma_entry = float(r.get("gamma_entry", 0))
        
        suggestion = None
        
        if layer == "active":
            if pnl_pct >= 30:
                suggestion = {"action": "CLOSE", "reason": f"Цель достигнута, +{pnl_pct:.1f}%", "priority": "high"}
            elif dte < 3 and pnl_pct < 0:
                suggestion = {"action": "CLOSE", "reason": f"DTE < 3, убыток", "priority": "high"}
            elif dte < 3 and pnl_pct >= 0:
                suggestion = {"action": "ROLL", "reason": f"DTE < 3, прибыль", "priority": "medium"}
            elif gamma < gamma_entry * 0.5:
                suggestion = {"action": "CLOSE", "reason": f"Gamma упала в 2x ({gamma_entry:.3f} → {gamma:.3f})", "priority": "high"}
            else:
                suggestion = {"action": "HOLD", "reason": "Мониторинг", "priority": "low"}
        
        elif layer == "adaptation":
            if gamma < gamma_entry * 0.3:
                suggestion = {"action": "CLOSE", "reason": f"Импульс исчерпан, gamma = {gamma_entry:.3f} → {gamma:.3f}", "priority": "high"}
            elif dte < 7 and pnl_pct < -20:
                suggestion = {"action": "CLOSE", "reason": f"DTE < 7, убыток > 20%", "priority": "high"}
            elif dte < 7:
                suggestion = {"action": "ROLL", "reason": f"DTE < 7, рынок в зоне", "priority": "medium"}
            else:
                suggestion = {"action": "HOLD", "reason": "Мониторинг theta-распада", "priority": "low"}
        
        elif layer == "anchor":
            if delta < 0.1 and dte < 7:
                suggestion = {"action": "ROLL", "reason": f"Delta < 0.1, DTE < 7", "priority": "medium"}
            elif pnl_pct >= 20:
                suggestion = {"action": "CLOSE", "reason": f"Цель достигнута, +{pnl_pct:.1f}%", "priority": "high"}
            elif dte > 60:
                suggestion = {"action": "HOLD", "reason": "Дальняя защита", "priority": "low"}
            else:
                suggestion = {"action": "HOLD", "reason": "Tail-хедж", "priority": "low"}
        
        if suggestion:
            suggestions.append({
                "symbol": symbol,
                "layer": layer,
                "strike": float(r.get("strike", 0)),
                "expiry": r.get("expiry", ""),
                "dte": dte,
                "pnl_pct": round(pnl_pct, 2),
                "recommendation": suggestion,
            })
    
    return {
        "anchor": recommendations,
        "suggestions": suggestions,
        "updated": date.today().strftime("%Y-%m-%d"),
    }


# ==========================================
# ЭНДПОИНТ 4: СВОДКА ПОРТФЕЛЯ
# ==========================================

@app.get("/api/summary")
def api_summary() -> dict[str, Any]:
    """Общая сводка портфеля."""
    
    # Позиции по активам
    pos_data = api_positions()
    positions = pos_data["positions"]
    pos_totals = pos_data["totals"]
    
    # Опционы
    opt_data = api_options()
    options = opt_data["options"]
    opt_totals = opt_data["totals"]
    
    # Net Greeks
    net_delta = sum(o["delta"] * o["qty"] for o in options)
    net_gamma = sum(o["gamma"] * o["qty"] for o in options)
    net_theta = sum(o["theta"] * o["qty"] for o in options)
    net_vega = sum(o["vega"] * o["qty"] for o in options)
    
    # SOL позиция для перевода delta в SOL
    sol_qty = sum(p["qty"] for p in positions if p["symbol"].upper().startswith("SOL"))
    
    # Общий PnL
    total_asset_pnl = pos_totals["total_pnl"]
    total_opt_pnl = opt_totals["total_pnl"]
    total_pnl = total_asset_pnl + total_opt_pnl
    total_cost_all = pos_totals["total_cost"] + opt_totals["total_cost"]
    total_value_all = pos_totals["total_value"] + opt_totals["total_value"]
    
    # Прогноз на день
    daily_theta = opt_totals["total_theta_per_day"]
    
    return {
        "assets": {
            "total_cost": pos_totals["total_cost"],
            "total_value": pos_totals["total_value"],
            "total_pnl": pos_totals["total_pnl"],
            "total_pnl_pct": pos_totals["total_pnl_pct"],
        },
        "options": {
            "total_cost": opt_totals["total_cost"],
            "total_value": opt_totals["total_value"],
            "total_pnl": opt_totals["total_pnl"],
            "total_pnl_pct": opt_totals["total_pnl_pct"],
            "total_theta_per_day": opt_totals["total_theta_per_day"],
        },
        "total": {
            "total_cost": round(total_cost_all, 2),
            "total_value": round(total_value_all, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": (total_pnl / total_cost_all * 100) if total_cost_all > 0 else 0,
        },
        "greeks": {
            "net_delta": round(net_delta, 4),
            "net_gamma": round(net_gamma, 4),
            "net_theta": round(net_theta, 4),
            "net_vega": round(net_vega, 4),
            "sol_qty": sol_qty,
        },
        "forecast": {
            "daily_theta": round(daily_theta, 4),
            "monthly_theta_estimate": round(daily_theta * 30, 4),
            "note": f"Theta: ${daily_theta:.2f}/день (≈ ${daily_theta*30:.2f}/месяц)",
        },
        "updated": date.today().strftime("%Y-%m-%d"),
    }


# ==========================================
# BLACK-SCHOLES PnL LADDER
# ==========================================

def _norm_cdf(x: float) -> float:
    """Нормальное распределение."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def _bs_put_price(S: float, K: float, T: float, sigma: float, r: float) -> float:
    """BS Price для Put опциона."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return max(K - S, 0)
    d1 = (math.log(S / K) + (r + sigma ** 2 / 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


@app.get("/api/blackscholes")
def api_black_scholes() -> dict[str, Any]:
    """BS PnL ladder для опционной позиции."""
    # Опции
    registry = read_csv("options_registry.csv")
    tracking = read_csv("options_tracking.csv")
    
    # Открытый опцион
    opt = None
    for r in registry:
        if r.get("status", "").strip() == "open":
            opt = r
            break
    
    if not opt:
        return {"symbol": "", "ladder": []}
    
    strike = float(opt.get("strike", 0))
    expiry = opt.get("expiry", "")
    entry_price = float(opt.get("entry_price", 0))
    qty = int(opt.get("qty", 1))
    dte = calc_dte(expiry)
    
    # Текущая цена актива
    spot = 0
    for t in tracking:
        spot = float(t.get("current_price", 0))
        break
    
    # IV
    iv = float(opt.get("iv", 0))
    if iv == 0:
        for t in tracking:
            iv = float(t.get("iv", 0))
            break
    
    # Avg entry спота
    avg_entry = spot
    pos_data = api_positions()
    for p in pos_data["positions"]:
        avg_entry = float(p.get("avg_price", spot))
        break
    
    # Диапазон: от avg_entry до -35%
    start_price = int(math.ceil(avg_entry))
    end_price = int(math.floor(avg_entry * 0.65))
    
    # BS params
    r_rf = 0.05  # risk-free rate
    T_years = max(dte / 365.0, 1 / 365.0)
    
    ladder = []
    for price in range(start_price, end_price - 1, -1):
        if price <= 0:
            continue
        bs_price = _bs_put_price(price, strike, T_years, iv, r_rf)
        pnl = (bs_price - entry_price) * qty
        pnl_pct = (pnl / (entry_price * qty) * 100) if entry_price > 0 else 0
        delta_pnl = round(pnl - (ladder[-1]["pnl"] if ladder else pnl), 2)
        ladder.append({
            "price": price,
            "bs_price": round(bs_price, 4),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "delta_pnl": delta_pnl,
            "is_current": price == spot,
            "is_avg": price == avg_entry,
        })
    
    return {
        "symbol": opt.get("symbol", ""),
        "spot": spot,
        "avg_entry": avg_entry,
        "strike": strike,
        "ladder": ladder,
    }


# ==========================================
# STATIC FILES
# ==========================================

DASH_DIR = Path(__file__).resolve().parent
app.mount("/", StaticFiles(directory=str(DASH_DIR), html=True), name="static")


# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Dashboard starting on http://0.0.0.0:{PORT}")
    print(f"   Data dir: {DATA_DIR}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
