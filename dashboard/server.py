#!/usr/bin/env python3
"""
T007 — Dashboard FastAPI backend.

Читает данные из SQLite-БД (hedge_model.db) и отдаёт JSON.
Эндпоинты: /api/positions, /api/options, /api/layers,
           /api/recommendations, /api/summary, /api/blackscholes

Запуск:
  cd dashboard && python server.py
  # http://localhost:8083
"""

import os
import math
import sys
import subprocess
from datetime import datetime, date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Add project to path
PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from src.db import (
    get_position, get_all_open_options, get_all_latest_greeks,
    get_buy_history, get_closed_positions, table_stats,
    get_pending_recommendations, execute_query, update_position_prices,
    get_latest_chain_snapshot, get_option_by_id, update_option,
    add_option, record_greeks,
)

# ==========================================
# CONFIG
# ==========================================

PORT = int(os.environ.get("DASHBOARD_PORT", "8083"))

# Читаем config.toml при старте (target_dd_pct для PnL-лестницы)
import tomllib
with open(PROJECT_DIR / "config.toml", "rb") as f:
    _config = tomllib.load(f)

# Просадка, которую страхуем (100 - target_dd_pct = 80 для target_dd_pct=20)
_TARGET_DD = _config.get("target_dd_pct", 20)
_LADDER_DOWN = round(_TARGET_DD / 100, 2)  # 0.20
_LADDER_UP = round(_TARGET_DD / 100, 2)   # 0.20

LAYER_DEFAULTS = {
    "distant": {"delta_min": 0.05, "delta_max": 0.20, "dte_min": 25, "dte_max": 99999, "label": "Дальний слой (Anchor / Tail Risk)"},
    "mid": {"delta_min": 0.20, "delta_max": 0.40, "dte_min": 10, "dte_max": 25, "label": "Средний слой (Adaptation)"},
    "near": {"delta_min": 0.25, "delta_max": 0.50, "dte_min": 3, "dte_max": 99, "label": "Ближний слой (Active / Hedging)"},
}

def _check_layer_match(d: float, dt: int) -> bool:
    """Проверяет, попадает ли опцион в любой слой по LAYER_DEFAULTS."""
    for ld in LAYER_DEFAULTS.values():
        if ld["delta_min"] <= d <= ld["delta_max"] and ld["dte_min"] <= dt <= ld["dte_max"]:
            return True
    return False

def _assign_layer(d: float) -> str:
    """Определяет слой по delta из LAYER_DEFAULTS."""
    for name, ld in LAYER_DEFAULTS.items():
        if ld["delta_min"] <= d <= ld["delta_max"]:
            return name
    return "distant"  # fallback

DASHBOARD_LADDER_RANGE = 20  # ±20% для PnL-лестницы

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
        return {
            "status": "ok",
            "output": output,
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "output": "Timeout after 60s"}
    except Exception as e:
        return {"status": "error", "output": str(e)}


@app.post("/api/update-option-entry")
async def api_update_option_entry(request: Request) -> dict:
    """Обновляет entry_price (и/qty) опциона."""
    try:
        data = await request.json()
        option_id = data.get("option_id")
        entry_price = data.get("entry_price")
        qty = data.get("qty")

        if option_id is None:
            return {"status": "error", "output": "Не указан option_id"}

        row = get_option_by_id(option_id)
        if not row:
            return {"status": "error", "output": f"Опцион id={option_id} не найден"}

        if row["status"] == "closed":
            return {"status": "error", "output": "Опцион закрыт, редактирование запрещено"}

        updates = {}
        if entry_price is not None:
            updates["entry_price"] = float(entry_price)
        if qty is not None:
            updates["qty"] = int(qty)

        if not updates:
            return {"status": "error", "output": "Нет данных для обновления"}

        updated = update_option(option_id, **updates)
        return {"status": "ok", "updated": updated, "option_id": option_id}
    except Exception as e:
        return {"status": "error", "output": str(e)}


@app.get("/api/buy-options")
async def api_buy_options(request: Request) -> dict:
    """Возвращает доступные PUT-опционы для покупки."""
    try:
        q = request.query_params
        layer = q.get("layer", "active")
        delta_min = float(q.get("delta_min", 0.1))
        delta_max = float(q.get("delta_max", 0.7))
        dte_min = int(q.get("dte_min", 1))
        dte_max = int(q.get("dte_max", 99999))

        import requests
        url = "https://api.bybit.com/v5/market/tickers"
        params = {"category": "option", "baseCoin": "SOL"}
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

        puts = []
        for item in data.get("result", {}).get("list", []):
            sym = item.get("symbol", "")
            if not sym.endswith("-P-USDT"):
                continue
            try:
                parts = sym.split("-")
                strike = float(parts[2])
                delta = float(item.get("delta", 0))
                if abs(delta) < delta_min or abs(delta) > delta_max:
                    continue
                date_part = parts[1]
                expiry_dt = datetime.strptime(date_part, "%d%b%y")
                dte = (expiry_dt - datetime.now()).days
                if dte < dte_min or dte > dte_max:
                    continue
                mark = float(item.get("markPrice", 0))
                last = float(item.get("lastPrice", 0))
                price = last if last > 0 else mark
                puts.append({
                    "symbol": sym,
                    "strike": strike,
                    "delta": round(delta, 4),
                    "gamma": round(float(item.get("gamma", 0)), 4),
                    "theta": round(float(item.get("theta", 0)), 4),
                    "vega": round(float(item.get("vega", 0)), 4),
                    "iv": round(float(item.get("markIv", 0)), 4),
                    "price": round(price, 4),
                    "dte": dte,
                    "expiry": expiry_dt.strftime("%Y-%m-%d"),
                })
            except (ValueError, KeyError):
                continue

        puts.sort(key=lambda x: (x["dte"], x["strike"]))
        return {"options": puts, "count": len(puts), "layer": layer}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "output": str(e)}


@app.post("/api/buy-option")
async def api_buy_option(request: Request) -> dict:
    """Покупка опциона с записью в БД."""
    try:
        data = await request.json()
        symbol = data.get("symbol")
        layer = data.get("layer", "active")
        qty = int(data.get("qty", 1))

        import requests
        url = "https://api.bybit.com/v5/market/tickers"
        r = requests.get(url, params={"category": "option", "baseCoin": "SOL"}, timeout=30)
        r.raise_for_status()
        chain = r.json().get("result", {}).get("list", [])
        opt = None
        for item in chain:
            if item.get("symbol") == symbol:
                parts = symbol.split("-")
                strike = float(parts[2])
                date_part = parts[1]
                expiry_dt = datetime.strptime(date_part, "%d%b%y")
                dte = (expiry_dt - datetime.now()).days
                delta = float(item.get("delta", 0))
                gamma = float(item.get("gamma", 0))
                theta = float(item.get("theta", 0))
                vega = float(item.get("vega", 0))
                iv = float(item.get("markIv", 0))
                mark = float(item.get("markPrice", 0))
                last = float(item.get("lastPrice", 0))
                price = last if last > 0 else mark
                opt = {
                    "symbol": symbol,
                    "strike": strike,
                    "expiry": expiry_dt.strftime("%Y-%m-%d"),
                    "dte": dte,
                    "delta": delta,
                    "gamma": gamma,
                    "theta": theta,
                    "vega": vega,
                    "iv": iv,
                    "mark_price": price,
                }
                break

        if not opt:
            return {"status": "error", "output": f"Опцион {symbol} не найден в Bybit chain"}

        new_id = add_option(
            symbol=opt["symbol"],
            opt_type="PUT",
            strike=opt["strike"],
            expiry=opt["expiry"],
            qty=qty,
            layer=layer,
            entry_date=date.today().isoformat(),
            entry_price=opt["mark_price"],
            iv_entry=opt["iv"],
            iv_atm_entry=opt["iv"],
            delta_entry=opt["delta"],
            gamma_entry=opt["gamma"],
            theta_entry=opt["theta"],
            vega_entry=opt["vega"],
            notes=f"Bought via dashboard {date.today().isoformat()}",
        )
        record_greeks(
            option_id=new_id,
            option_symbol=opt["symbol"],
            current_price=opt["mark_price"],
            delta=opt["delta"],
            gamma=opt["gamma"],
            theta=opt["theta"],
            vega=opt["vega"],
            iv=opt["iv"],
            iv_atm=opt["iv"],
            dte=opt["dte"],
            intrinsic_value=max(opt["strike"] - 66.0, 0),
            unrealized_pnl=0.0,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        return {
            "status": "ok",
            "id": new_id,
            "symbol": opt["symbol"],
            "price": opt["mark_price"],
            "total": round(opt["mark_price"] * qty, 2),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "output": str(e)}


@app.post("/api/update-option-layer")
async def api_update_option_layer(request: Request) -> dict:
    """Обновляет layer опциона (anchor / adaptation / active)."""
    try:
        data = await request.json()
        option_id = data.get("option_id")
        new_layer = data.get("layer")

        if option_id is None:
            return {"status": "error", "output": "Не указан option_id"}
        if new_layer not in ("anchor", "adaptation", "active"):
            return {"status": "error", "output": f"Недопустимый layer: {new_layer}. Доступные: anchor, adaptation, active"}

        row = get_option_by_id(option_id)
        if not row:
            return {"status": "error", "output": f"Опцион id={option_id} не найден"}

        if row["status"] == "closed":
            return {"status": "error", "output": "Опцион закрыт, редактирование запрещено"}

        old_layer = row["layer"] or "—"
        updated = update_option(option_id, layer=new_layer)
        return {"status": "ok", "updated": updated, "option_id": option_id, "old_layer": old_layer, "new_layer": new_layer}
    except Exception as e:
        return {"status": "error", "output": str(e)}


@app.post("/api/close-option")
async def api_close_option(request: Request) -> dict:
    """Закрывает конкретный опцион по ID (или автоматическое по правилу)."""
    import tomllib
    import json as json_mod
    try:
        raw = await request.body()
        if isinstance(raw, bytes):
            data = json_mod.loads(raw)
        else:
            data = json_mod.loads(raw.decode())
        option_id = data.get("option_id")
        close_reason = data.get("close_reason", "manual")

        # --- Ручное закрытие конкретного опциона ---
        if option_id is not None:
            row = get_option_by_id(option_id)
            if not row:
                return {"status": "error", "output": f"Опцион id={option_id} не найден"}

            if row["status"] == "closed":
                return {"status": "error", "output": "Опцион уже закрыт"}

            # Берём текущую цену из greeks
            all_greeks = get_all_latest_greeks()
            greeks_idx = {g["option_symbol"]: g for g in all_greeks}
            greek = greeks_idx.get(row["symbol"], {})
            current_price = float(greek.get("current_price") or row["entry_price"])
            qty = int(row["qty"])
            entry_price = float(row["entry_price"] or 0)

            from src.db import get_connection, close_option as db_close_option
            conn = get_connection()
            db_close_option(option_id, current_price, close_reason=close_reason,
                           notes=f"closed via dashboard")

            return {
                "status": "ok",
                "message": f"Опцион {row['symbol']} закрыт",
                "current_price": round(current_price, 4),
                "pnl": round((current_price - entry_price) * qty, 2),
            }

        return {"status": "error", "output": "Не указан option_id"}
    except Exception as e:
        return {"status": "error", "output": str(e)}


# ==========================================
# ЭНДПОИНТ 1: ПОЗИЦИИ ПО АКТИВАМ
# ==========================================

@app.get("/api/positions")
def api_positions() -> dict[str, Any]:
    """Позиции по активам (акции/крипта)."""
    pos = get_position("SOL")
    if not pos:
        return {
            "positions": [],
            "totals": {"total_cost": 0, "total_value": 0, "total_pnl": 0, "total_pnl_pct": 0},
            "updated": date.today().strftime("%Y-%m-%d"),
        }

    qty = float(pos["qty"])
    avg_price = float(pos["avg_price"])
    total_cost = float(pos["total_cost"])
    current_price = float(pos["current_price"] or avg_price)
    total_value = float(pos["total_value"] or total_cost)
    pnl = float(pos["pnl"] or 0)

    # === История покупок ===
    buy_rows = get_buy_history()
    buy_records = []
    for b in buy_rows:
        buy_records.append({
            "date": b.get("buy_date", ""),
            "qty": float(b["qty"]),
            "price": float(b["price"]),
            "total": float(b["total"]),
            "pnl": round((current_price - float(b["price"])) * float(b["qty"]), 2),
            "pnl_pct": round((current_price - float(b["price"])) / float(b["price"]) * 100, 2) if float(b["price"]) > 0 else 0,
            "notes": b.get("notes", ""),
        })

    # === PnL-лестница по шагу $1 (от avg-цены ± ladder_range) ===
    low = round(avg_price * (1 - DASHBOARD_LADDER_RANGE / 100))
    high = round(avg_price * (1 + DASHBOARD_LADDER_RANGE / 100))
    ladder = []
    for price in range(low, high + 1):
        pnl_step = (price - avg_price) * qty
        pnl_pct = ((price - avg_price) / avg_price * 100) if avg_price > 0 else 0
        ladder.append({
            "price": price,
            "pnl": round(pnl_step, 2),
            "pnl_pct": round(pnl_pct, 2),
            "is_current": price == round(current_price),
            "is_avg": price == round(avg_price),
        })

    return {
        "positions": [{
            "symbol": pos["symbol"],
            "qty": qty,
            "avg_price": avg_price,
            "total_cost": total_cost,
            "current_price": current_price,
            "total_value": total_value,
            "pnl": pnl,
            "pnl_pct": round(pnl / total_cost * 100, 2) if total_cost > 0 else 0,
        }],
        "totals": {
            "total_cost": round(total_cost, 2),
            "total_value": round(total_value, 2),
            "total_pnl": round(pnl, 2),
            "total_pnl_pct": round(pnl / total_cost * 100, 2) if total_cost > 0 else 0,
        },
        "buy_history": buy_records,
        "pnl_ladder": ladder,
        "updated": date.today().strftime("%Y-%m-%d"),
    }


# ==========================================
# ЭНДПОИНТ 2: ОПЦИОННЫЕ ПОЗИЦИИ
# ==========================================

@app.get("/api/purchased-options")
def api_purchased_options() -> dict[str, Any]:
    """Купленные опционы сгруппированные по слоям."""
    open_opts = get_all_open_options()
    latest_greeks = get_all_latest_greeks()
    greeks_idx = {g["option_symbol"]: g for g in latest_greeks}

    by_layer = {"distant": [], "mid": [], "near": []}

    for opt in open_opts:
        symbol = opt["symbol"].strip()
        layer = (opt["layer"] or "").strip().lower()
        greek = greeks_idx.get(symbol, {})
        current_price = float(greek.get("current_price") or 0)
        entry_price = float(opt["entry_price"] or 0)
        qty = int(opt["qty"])
        delta = float(greek.get("delta") or 0)
        gamma = float(greek.get("gamma") or 0)
        theta = float(greek.get("theta") or 0)
        vega = float(greek.get("vega") or 0)
        iv = float(greek.get("iv") or 0)
        dte = int(greek.get("dte") or calc_dte(opt["expiry"]))

        mapped_layer = None
        # First check stored layer from DB
        if layer == "anchor":
            mapped_layer = "distant"
        elif layer == "adaptation":
            mapped_layer = "mid"
        elif layer == "active":
            mapped_layer = "near"
        else:
            # Fallback to delta-based mapping (from LAYER_DEFAULTS)
            abs_delta = abs(delta)
            if (LAYER_DEFAULTS["distant"]["delta_min"] <= abs_delta <= LAYER_DEFAULTS["distant"]["delta_max"]):
                mapped_layer = "distant"
            elif (LAYER_DEFAULTS["mid"]["delta_min"] <= abs_delta <= LAYER_DEFAULTS["mid"]["delta_max"]):
                mapped_layer = "mid"
            elif (LAYER_DEFAULTS["near"]["delta_min"] <= abs_delta <= LAYER_DEFAULTS["near"]["delta_max"]):
                mapped_layer = "near"

        if mapped_layer:
            by_layer[mapped_layer].append({
                "symbol": symbol,
                "strike": float(opt["strike"]),
                "delta": round(delta, 4),
                "gamma": round(gamma, 4),
                "theta": round(theta, 4),
                "vega": round(vega, 4),
                "iv": round(iv, 4),
                "dte": dte,
                "qty": qty,
                "entry_price": entry_price,
                "current_price": round(current_price, 4),
                "pnl": round((current_price - entry_price) * qty, 2),
            })

    return {"distant": by_layer["distant"], "mid": by_layer["mid"], "near": by_layer["near"]}


@app.get("/api/options")
def api_options() -> dict[str, Any]:
    """Опционные позиции с Greeks и метриками."""
    open_opts = get_all_open_options()
    latest_greeks = get_all_latest_greeks()
    greeks_idx = {g["option_symbol"]: g for g in latest_greeks}

    options = []
    total_opt_cost = 0.0
    total_opt_value = 0.0
    total_opt_pnl = 0.0

    for opt in open_opts:
        symbol = opt["symbol"].strip()
        entry_price = float(opt["entry_price"] or 0)
        qty = int(opt["qty"])
        total_cost_val = float(opt["total_cost"] or (entry_price * qty))
        strike = float(opt["strike"])
        expiry = opt["expiry"]
        layer = (opt["layer"] or "").strip()

        greek = greeks_idx.get(symbol, {})
        current_price = float(greek.get("current_price") or entry_price)
        pnl = (current_price - entry_price) * qty
        delta = float(greek.get("delta") or 0)
        gamma = float(greek.get("gamma") or 0)
        theta = float(greek.get("theta") or 0)
        vega = float(greek.get("vega") or 0)
        dte = int(greek.get("dte") or calc_dte(expiry))
        iv = float(greek.get("iv") or 0)
        iv_atm = float(greek.get("iv_atm") or 0)
        intrinsic = float(greek.get("intrinsic_value") or 0)

        entry_delta = float(opt["delta_entry"] or 0)
        entry_gamma = float(opt["gamma_entry"] or 0)
        entry_theta = float(opt["theta_entry"] or 0)
        entry_vega = float(opt["vega_entry"] or 0)
        iv_entry = float(opt["iv_entry"] or 0)

        total_opt_cost += total_cost_val
        total_opt_value += current_price * qty
        total_opt_pnl += pnl

        theta_per_day = theta * qty

        options.append({
            "id": opt["id"],
            "symbol": symbol,
            "type": opt["type"],
            "strike": strike,
            "expiry": expiry,
            "qty": qty,
            "layer": layer,
            "entry_price": entry_price,
            "current_price": round(current_price, 4),
            "pnl": round(pnl, 2),
            "pnl_pct": round((current_price - entry_price) / entry_price * 100, 2) if entry_price > 0 else 0,
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
            "cost_per_day": round(abs(theta_per_day), 4),
        })

    # Сортировка: anchor → adaptation → active
    layer_order = {"anchor": 0, "adaptation": 1, "active": 2}
    options.sort(key=lambda o: (layer_order.get(o["layer"], 99), o["id"]))

    return {
        "options": options,
        "totals": {
            "total_cost": round(total_opt_cost, 2),
            "total_value": round(total_opt_value, 2),
            "total_pnl": round(total_opt_pnl, 2),
            "total_pnl_pct": round(total_opt_pnl / total_opt_cost * 100, 2) if total_opt_cost > 0 else 0,
            "total_theta_per_day": round(sum(o["theta_per_day"] for o in options), 4),
            "net_delta": round(sum(o["delta"] * o["qty"] for o in options), 4),
            "net_gamma": round(sum(o["gamma"] * o["qty"] for o in options), 4),
            "net_theta": round(sum(o["theta"] * o["qty"] for o in options), 4),
            "net_vega": round(sum(o["vega"] * o["qty"] for o in options), 4),
        },
        "updated": date.today().strftime("%Y-%m-%d"),
    }


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

    pos = get_position("SOL")
    if not pos:
        return {"layers": [], "position_size": 0, "total_budget": 0, "free_budget": 0, "updated": date.today().strftime("%Y-%m-%d")}

    sol_qty = float(pos["qty"])
    sol_avg = float(pos["avg_price"])
    position_size = sol_qty * sol_avg
    global_budget_pct = config.get("global_budget_pct", 5)
    total_budget = position_size * global_budget_pct / 100
    layers_alloc = config.get("layer_allocation", {})

    # Факт по слоям из БД
    open_opts = get_all_open_options()
    latest_greeks = {g["option_symbol"]: g for g in get_all_latest_greeks()}

    spent = {}
    opts_by_layer = {}
    for opt in open_opts:
        layer_key = (opt["layer"] or "").strip().lower()
        total_cost_val = float(opt["total_cost"] or (float(opt["entry_price"] or 0) * int(opt["qty"])))
        spent[layer_key] = spent.get(layer_key, 0) + total_cost_val
        opts_by_layer.setdefault(layer_key, []).append({
            "symbol": opt["symbol"],
            "strike": float(opt["strike"]),
            "expiry": opt["expiry"],
            "qty": int(opt["qty"]),
            "entry_price": float(opt["entry_price"] or 0),
            "total_cost": total_cost_val,
        })

    # PnL по слоям
    layer_names = ["Anchor", "Adaptation", "Active"]
    layers_data = []

    for name in layer_names:
        budget = total_budget * layers_alloc.get(name, 0) / 100
        fact = spent.get(name.lower(), 0)
        opts = opts_by_layer.get(name.lower(), [])

        layer_pnl = 0
        for o in opts:
            greek = latest_greeks.get(o["symbol"], {})
            cur = float(greek.get("current_price") or o["entry_price"])
            layer_pnl += (cur - o["entry_price"]) * o["qty"]

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
        with open(cfg_path, "rb") as f:
            config = tomllib.load(f)

        pos = get_position("SOL")
        if pos:
            qty = float(pos["qty"])
            avg_price = float(pos["avg_price"])
            target_dd = config.get("target_dd_pct", 20) / 100
            global_budget = config.get("global_budget_pct", 5) / 100
            anchor_layer_pct = config.get("layer_allocation", {}).get("Anchor", 50) / 100

            position_size = qty * avg_price
            total_budget = position_size * global_budget
            anchor_budget = total_budget * anchor_layer_pct
            s_target = avg_price * (1 - target_dd)

            recommendations.append({
                "type": "anchor_selection",
                "title": "Anchor Layer Selection (T006)",
                "avg_price": avg_price,
                "s_target": round(s_target, 2),
                "position_size": round(position_size, 2),
                "total_budget": round(total_budget, 2),
                "anchor_budget": round(anchor_budget, 2),
                "qty": qty,
                "message": f"Anchor budget: ${anchor_budget:.2f} | Target level: ${s_target:.2f}",
            })
    except Exception as e:
        recommendations.append({
            "type": "error",
            "title": "Anchor Selection",
            "message": f"Ошибка расчёта: {e}",
        })

    # --- Рекомендации от monitor_options логики ---
    open_opts = get_all_open_options()
    latest_greeks = {g["option_symbol"]: g for g in get_all_latest_greeks()}

    for opt in open_opts:
        symbol = opt["symbol"].strip()
        layer = (opt["layer"] or "").strip()
        entry_price = float(opt["entry_price"] or 0)
        qty = int(opt["qty"])
        greek = latest_greeks.get(symbol, {})
        current_price = float(greek.get("current_price") or entry_price)
        pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        dte = int(greek.get("dte") or calc_dte(opt["expiry"]))
        delta = abs(float(greek.get("delta") or 0))
        gamma = float(greek.get("gamma") or 0)
        gamma_entry = float(opt["gamma_entry"] or 0)

        suggestion = None

        if layer == "active":
            if pnl_pct >= 30:
                suggestion = {"action": "CLOSE", "reason": f"Цель достигнута, +{pnl_pct:.1f}%", "priority": "high"}
            elif dte < 3 and pnl_pct < 0:
                suggestion = {"action": "CLOSE", "reason": f"DTE < 3, убыток", "priority": "high"}
            elif dte < 3 and pnl_pct >= 0:
                suggestion = {"action": "ROLL", "reason": f"DTE < 3, прибыль", "priority": "medium"}
            elif gamma_entry > 0 and gamma < gamma_entry * 0.5:
                suggestion = {"action": "CLOSE", "reason": f"Gamma упала в 2x ({gamma_entry:.3f} → {gamma:.3f})", "priority": "high"}
            else:
                suggestion = {"action": "HOLD", "reason": "Мониторинг", "priority": "low"}

        elif layer == "adaptation":
            if gamma_entry > 0 and gamma < gamma_entry * 0.3:
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
                "strike": float(opt["strike"]),
                "expiry": opt["expiry"],
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
    pos_data = api_positions()
    opt_data = api_options()

    positions = pos_data["positions"]
    pos_totals = pos_data["totals"]
    options = opt_data["options"]
    opt_totals = opt_data["totals"]

    net_delta = sum(o["delta"] * o["qty"] for o in options)
    net_gamma = sum(o["gamma"] * o["qty"] for o in options)
    net_theta = sum(o["theta"] * o["qty"] for o in options)
    net_vega = sum(o["vega"] * o["qty"] for o in options)
    sol_qty = sum(p["qty"] for p in positions)

    total_asset_pnl = pos_totals["total_pnl"]
    total_opt_pnl = opt_totals["total_pnl"]
    total_pnl = total_asset_pnl + total_opt_pnl
    total_cost_all = pos_totals["total_cost"] + opt_totals["total_cost"]
    total_value_all = pos_totals["total_value"] + opt_totals["total_value"]
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
            "total_pnl_pct": round(total_pnl / total_cost_all * 100, 2) if total_cost_all > 0 else 0,
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
# COMBINED LADDER (SOL + опционы по BS)
# ==========================================

@app.get("/api/combined-ladder")
def api_combined_ladder(request: Request, min_price: int = None, max_price: int = None) -> dict[str, Any]:
    """PnL ladder: SOL + все опционы (BS-расчёт для каждого шага)."""
    pos = get_position("SOL")
    if not pos:
        return {"ladder": []}

    qty = float(pos["qty"])
    avg_price = float(pos["avg_price"])

    # Custom range from query params
    if min_price is not None and max_price is not None:
        low = min_price
        high = max_price
    else:
        low = round(avg_price * (1 - _LADDER_DOWN))
        high = round(avg_price * (1 + _LADDER_UP))

    open_opts = get_all_open_options()
    spot = float(pos.get("current_price") or avg_price)

    r_rf = 0.05
    ladder = []
    for price in range(low, high + 1):
        # SOL PnL
        sol_pnl = (price - avg_price) * qty

        # Опционы PnL и intrinsic value
        opt_pnl = 0.0
        total_intrinsic_pnl = 0.0
        for opt in open_opts:
            strike = float(opt["strike"])
            expiry = opt["expiry"]
            entry_price = float(opt["entry_price"] or 0)
            opt_qty = int(opt["qty"])
            dte = calc_dte(expiry)
            T_years = max(dte / 365.0, 1 / 365.0)

            latest_greeks = get_all_latest_greeks()
            greeks_idx = {g["option_symbol"]: g for g in latest_greeks}
            greek = greeks_idx.get(opt["symbol"], {})
            iv = float(greek.get("iv") or 0)

            if iv > 0:
                bs_price = _bs_put_price(price, strike, T_years, iv, r_rf)
            else:
                bs_price = max(strike - price, 0)

            opt_pnl += (bs_price - entry_price) * opt_qty
            # Intrinsic PnL = max(0, strike - price) * qty - premium_paid
            intrinsic_pnl = max(0, strike - price) * opt_qty - entry_price * opt_qty
            total_intrinsic_pnl += intrinsic_pnl

        total_pnl = sol_pnl + opt_pnl
        total_pnl_pct = (total_pnl / (avg_price * qty) * 100) if avg_price > 0 else 0

        ladder.append({
            "price": price,
            "sol_pnl": round(sol_pnl, 2),
            "opt_pnl": round(opt_pnl, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "intrinsic_value": round(total_intrinsic_pnl, 2),
            "is_current": price == round(spot),
            "is_avg": price == round(avg_price),
        })

    return {"ladder": ladder, "updated": date.today().strftime("%Y-%m-%d")}


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
    open_opts = get_all_open_options()
    if not open_opts:
        return {"symbol": "", "ladder": []}

    opt = open_opts[0]
    strike = float(opt["strike"])
    expiry = opt["expiry"]
    entry_price = float(opt["entry_price"] or 0)
    qty = int(opt["qty"])
    dte = calc_dte(expiry)

    latest_greeks = get_all_latest_greeks()
    greeks_idx = {g["option_symbol"]: g for g in latest_greeks}
    greek = greeks_idx.get(opt["symbol"], {})

    spot = float(greek.get("current_price") or 0)
    iv = float(greek.get("iv") or 0)

    # Avg entry спота
    pos = get_position("SOL")
    avg_entry = float(pos["avg_price"]) if pos else spot

    # Spot — из последнего chain snapshot
    spot_rows = execute_query(
        "SELECT spot_price FROM option_chain_snapshot ORDER BY timestamp DESC LIMIT 1"
    )
    if spot_rows:
        spot = float(spot_rows[0]["spot_price"])

    start_price = int(math.ceil(avg_entry))
    end_price = int(math.floor(avg_entry * 0.65))

    r_rf = 0.05
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
        "symbol": opt["symbol"],
        "spot": spot,
        "avg_entry": avg_entry,
        "strike": strike,
        "ladder": ladder,
    }


# ==========================================
# SPOT PRICE
# ==========================================

@app.get("/api/spot")
def api_spot() -> dict:
    """Текущая цена SOL."""
    row = execute_query(
        "SELECT spot_price, timestamp FROM option_chain_snapshot ORDER BY timestamp DESC LIMIT 1"
    )
    if row and row[0]:
        return {"spot": float(row[0]["spot_price"]), "ts": row[0]["timestamp"]}
    return {"spot": 0, "ts": None}


# ==========================================
# STATISTICS
# ==========================================

@app.get("/api/stats")
def api_stats() -> dict:
    """Статистика по БД."""
    return {
        "stats": table_stats(),
        "updated": date.today().strftime("%Y-%m-%d"),
    }


# ==========================================
# LAYER API
# ==========================================

def _fetch_chain_from_bybit():
    """Fetch from Bybit API. Returns (puts, spot_price, source, timestamp)."""
    try:
        from src.chain_fetcher import fetch_and_filter_chain
        rows, spot_price = fetch_and_filter_chain("SOL")
        puts = [r for r in rows if r["type"] == "PUT"]
        puts.sort(key=lambda x: (x.get("dte",0), x.get("strike",0)))
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return puts, spot_price, "live", now
    except Exception as e:
        print(f"Bybit fetch failed: {e}")
        return None, None, None, None

def _fetch_chain_from_db():
    """Fetch from DB snapshot. Returns (puts, spot_price, source, timestamp)."""
    try:
        rows = get_latest_chain_snapshot()
        if not rows:
            return None, None, None, None
        puts = [r for r in rows if r.get("type") == "PUT"]
        puts.sort(key=lambda x: (x.get("dte",0), x.get("strike",0)))
        # Берём реальный spot_price и timestamp из снапшота
        spot_price = float(rows[0].get("spot_price", 0))
        ts = rows[0].get("timestamp", "unknown")
        return puts, spot_price, "db_fallback", ts
    except Exception as e:
        print(f"DB fallback failed: {e}")
        return None, None, None, None

def _data_age_minutes(timestamp_str: str) -> int:
    """Сколько минут прошло с момента timestamp."""
    try:
        ts = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        return int((datetime.now() - ts).total_seconds() / 60)
    except Exception:
        return -1  # неизвестно

def _build_layer_response(layer, criteria, puts, spot_price, layer_defaults, data_source="live", timestamp=None):
    # Group by expiry for ATM IV lookup
    from collections import defaultdict
    expiry_strikes = defaultdict(list)
    for p in puts:
        expiry = p.get("expiry")
        strike = p.get("strike", 0)
        if expiry and strike:
            expiry_strikes[expiry].append((strike, p.get("iv", 0) or 0))
    for expiry in expiry_strikes:
        expiry_strikes[expiry].sort()

    filtered = []
    for p in puts:
        abs_delta = abs(p["delta"]) if isinstance(p["delta"], (int, float)) else 0
        dte = p.get("dte", 0)
        if abs_delta < criteria["delta_min"] or abs_delta > criteria["delta_max"]:
            continue
        dte_max = criteria["dte_max"]
        if dte < criteria["dte_min"] or (dte_max != "all" and dte > dte_max):
            continue
        is_match = (
            abs_delta >= layer_defaults["delta_min"]
            and abs_delta <= layer_defaults["delta_max"]
            and dte >= layer_defaults["dte_min"]
            and dte <= layer_defaults["dte_max"]
        )
        # IV ATM: nearest strike to spot for this expiry
        iv_atm = 0
        expiry = p.get("expiry")
        if expiry and spot_price and expiry in expiry_strikes:
            atm_strike, atm_iv = min(expiry_strikes[expiry], key=lambda x: abs(x[0] - spot_price))
            iv_atm = round(atm_iv, 4)
        filtered.append({
            "symbol": p["symbol"],
            "strike": p["strike"],
            "expiry": p["expiry"],
            "delta": round(p["delta"], 4),
            "gamma": round(p.get("gamma", 0), 4),
            "theta": round(p.get("theta", 0), 4),
            "vega": round(p.get("vega", 0), 4),
            "iv": round(p.get("iv", 0) or 0, 4),
            "iv_atm": iv_atm,
            "dte": p.get("dte", 0),
            "price": round(p.get("mark_price", 0), 4),
            "open_interest": p.get("open_interest", 0),
            "volume": p.get("volume", 0) or 0,
            "spread": round(p.get("ask", 0) - p.get("bid", 0), 4) if (p.get("ask") and p.get("bid")) else None,
            "is_layer_match": is_match,
            "spot_price": round(spot_price, 2) if spot_price else None,
        })
    return {
        "layer": layer,
        "label": layer_defaults["label"],
        "spot_price": round(spot_price, 2) if spot_price else None,
        "criteria": criteria,
        "layerDefaults": layer_defaults,
        "count": len(filtered),
        "options": filtered,
        "data_source": data_source,
        "data_age_minutes": _data_age_minutes(timestamp) if timestamp else -1,
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@app.get("/api/layer/{name}")
def api_layer(name: str, request: Request):
    """Параметризованный эндпоинт слоёв (distant, mid, near)."""
    layer_defaults = LAYER_DEFAULTS[name]
    q = request.query_params
    all_mode = q.get("all", "0") == "1"
    if all_mode:
        # Показать все опционы без фильтров
        criteria = {
            "delta_min": 0,
            "delta_max": 1,
            "dte_min": 1,
            "dte_max": 99999,
        }
        criteria["dte_max"] = "all"
    else:
        criteria = {
            "delta_min": float(q.get("delta_min", layer_defaults["delta_min"])),
            "delta_max": float(q.get("delta_max", layer_defaults["delta_max"])),
            "dte_min": int(q.get("dte_min", layer_defaults["dte_min"])),
            "dte_max": int(q.get("dte_max", layer_defaults["dte_max"])),
        }
    puts, spot_price, source, ts = _fetch_chain_from_bybit()
    if not puts:
        puts, spot_price, source, ts = _fetch_chain_from_db()
    if not puts:
        resp = _build_layer_response(name, criteria, [], None, layer_defaults, "no_data", None)
        resp["error"] = "No data"  # явный признак ошибки
        return resp
    return _build_layer_response(name, criteria, puts, spot_price, layer_defaults, source, ts)


# ==========================================
# AVAILABLE OPTIONS (ALL LAYERS)
# ==========================================

@app.get("/api/available-options")
def api_available_options(request: Request):
    """Все доступные опционы из всех слоёв с общими фильтрами."""
    q = request.query_params
    delta_min = float(q.get("delta_min", 0))
    delta_max = float(q.get("delta_max", 1))
    dte_min = int(q.get("dte_min", 0))
    dte_max = int(q.get("dte_max", 99999))
    
    puts, spot_price, source, ts = _fetch_chain_from_bybit()
    if not puts:
        puts, spot_price, source, ts = _fetch_chain_from_db()

    if not puts:
        return {"options": [], "count": 0, "spot_price": None, "data_source": "no_data", "data_age_minutes": -1}
    
    # Filter by global criteria
    filtered = []
    for p in puts:
        d = abs(p.get("delta", 0))
        dt = p.get("dte", 0)
        if d >= delta_min and d <= delta_max and dt >= dte_min and dt <= dte_max:
            filtered.append(p)
    
    # Sort by DTE then strike
    filtered.sort(key=lambda x: (x.get("dte", 0), x.get("strike", 0)))
    
    # Determine layer matches for highlighting
    def is_layer_match(option):
        d = abs(option.get("delta", 0))
        dt = option.get("dte", 0)
        return _check_layer_match(d, dt)
    
    # Assign layer
    def assign_layer(option):
        return _assign_layer(abs(option.get("delta", 0)))
    
    for opt in filtered:
        opt["is_layer_match"] = is_layer_match(opt)
        opt["layer"] = assign_layer(opt)
        # Normalize price field (mark_price → price for frontend compatibility)
        if "price" not in opt:
            opt["price"] = opt.get("mark_price", 0)
        # Add spread if available
        if "spread" not in opt:
            bid = opt.get("bid")
            ask = opt.get("ask")
            if bid and ask:
                opt["spread"] = round(ask - bid, 4)
            else:
                opt["spread"] = None
    
    return {
        "options": filtered,
        "count": len(filtered),
        "spot_price": round(spot_price, 2) if spot_price else None,
        "data_source": source or "unknown",
        "data_age_minutes": _data_age_minutes(ts) if ts else -1,
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
    uvicorn.run(app, host="0.0.0.0", port=PORT)
