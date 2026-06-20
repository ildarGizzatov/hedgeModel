"""
Мониторинг открытых опционных позиций.

Читает реестр купленных опционов, запрашивает Bybit API текущие Greeks/цены,
рассчитывает IV ATM и выдаёт рекомендации.

Использование:
    python src/monitor_options.py
"""

import os
import csv
import json
from datetime import datetime, date

import requests

# Bybit API
BYBIT_API = "https://api.bybit.com/v5/market/tickers"
BASE_COIN = "SOL"

# Путь к проекту
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(PROJECT_DIR, "data", "options_registry.csv")
TRACKING_PATH = os.path.join(PROJECT_DIR, "data", "options_tracking.csv")
PORTFOLIO_PATH = os.path.join(PROJECT_DIR, "data", "open_positions.csv")

# Триггеры по слоям
LAYER_RULES = {
    "anchor": {"delta_hold_threshold": 0.10},
    "adaptation": {"dte_roll_threshold": 7},
    "active": {"dte_close_threshold": 3},
}


def fetch_full_chain():
    """Забрает весь чейн SOL-опционов одним запросом."""
    params = {"category": "option", "baseCoin": BASE_COIN}
    r = requests.get(BYBIT_API, params=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    
    if not data.get("result") or not isinstance(data["result"].get("list"), list):
        raise RuntimeError("Unexpected API response structure")
    
    return data["result"]["list"]


def parse_option(ticker):
    """Парсит один тикер в структуру."""
    symbol = ticker.get("symbol", "")
    if "-P-" not in symbol and "-C-" not in symbol:
        return None
    
    try:
        parts = symbol.split("-")
        date_str = parts[1]
        expiry = datetime.strptime(date_str, "%d%b%y")
        expiry_str = expiry.strftime("%Y-%m-%d")
        strike = float(parts[2])
        opt_type = "PUT" if "-P-" in symbol else "CALL"
        
        return {
            "symbol": symbol,
            "expiry_str": expiry_str,
            "strike": strike,
            "type": opt_type,
            "delta": float(ticker.get("delta") or 0),
            "gamma": float(ticker.get("gamma") or 0),
            "theta": float(ticker.get("theta") or 0),
            "vega": float(ticker.get("vega") or 0),
            "mark_price": float(ticker.get("markPrice") or 0),
            "last_price": float(ticker.get("lastPrice") or 0),
            "iv": float(ticker.get("markIv") or 0),
            "underlying_price": float(ticker.get("underlyingPrice") or 0),
        }
    except Exception:
        return None


def calc_iv_atm(chain: list) -> dict:
    """
    Находит ATM-опцион (delta ≈ 0.5) для каждой экспирации.
    Returns: {expiry_str: iv_atm}
    """
    atm_by_expiry = {}
    
    for ticker in chain:
        parsed = parse_option(ticker)
        if not parsed:
            continue
        
        expiry = parsed["expiry_str"]
        delta_abs = abs(parsed["delta"])
        iv = parsed["iv"]
        
        # Считаем расстояние дельты от 0.5
        current_atm = atm_by_expiry.get(expiry)
        if current_atm is None or abs(delta_abs - 0.5) < current_atm["delta_dist"]:
            atm_by_expiry[expiry] = {
                "iv": iv,
                "delta_dist": abs(delta_abs - 0.5),
                "symbol": parsed["symbol"],
                "strike": parsed["strike"],
            }
    
    return {exp: data["iv"] for exp, data in atm_by_expiry.items()}


def find_atm_symbol_for_expiry(chain: list, expiry_str: str) -> str:
    """Возвращает символ ATM-опциона для заданной экспирации."""
    atm_by_expiry = {}
    
    for ticker in chain:
        parsed = parse_option(ticker)
        if not parsed:
            continue
        
        if parsed["expiry_str"] != expiry_str:
            continue
        
        delta_abs = abs(parsed["delta"])
        current = atm_by_expiry.get(expiry_str)
        if current is None or abs(delta_abs - 0.5) < current["delta_dist"]:
            atm_by_expiry[expiry_str] = {"symbol": parsed["symbol"], "delta_dist": abs(delta_abs - 0.5)}
    
    atm = atm_by_expiry.get(expiry_str)
    return atm["symbol"] if atm else ""


def calc_dte(expiry_str: str) -> int:
    """Дней до экспирации."""
    expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    delta = expiry - date.today()
    return max(delta.days, 0)


def calc_intrinsic(strike: float, option_type: str, spot: float) -> float:
    """Внутренняя стоимость."""
    if option_type == "PUT":
        return max(strike - spot, 0)
    return max(spot - strike, 0)


def read_registry() -> list:
    """Читает реестр, возвращает только open."""
    positions = []
    
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("status", "").strip() == "open":
                positions.append(row)
    
    return positions


def fetch_spot_price() -> float:
    """Получает актуальную цену SOL из Bybit spot."""
    try:
        params = {"category": "spot"}
        r = requests.get(BYBIT_API, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        
        for ticker in data.get("result", {}).get("list", []):
            if ticker.get("symbol") == "SOLUSDT":
                return float(ticker.get("lastPrice", 0))
    except Exception:
        pass
    return 0


def update_portfolio(spot_price: float) -> list:
    """Обновляет current_price в open_positions.csv и пересчитывает PnL."""
    if not os.path.exists(PORTFOLIO_PATH):
        return []
    
    if spot_price <= 0:
        print("   ⚠️ Spot price не получен, использую данные из CSV")
        return read_portfolio()
    
    with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    updated = 0
    for row in rows:
        symbol = row.get("symbol", "").strip().upper()
        qty = float(row.get("qty", 0))
        total_cost = float(row.get("total_cost", 0))
        
        if qty <= 0:
            continue
        
        old_price = float(row.get("current_price", 0))
        old_value = float(row.get("total_value", 0))
        old_pnl = float(row.get("pnl", 0))
        
        row["current_price"] = spot_price
        row["total_value"] = round(qty * spot_price, 2)
        row["pnl"] = round(qty * spot_price - total_cost, 2)
        row["updated"] = date.today().strftime("%Y-%m-%d")
        
        if old_price != spot_price:
            print(f"   {symbol}: {old_price} -> {spot_price}")
        
        updated += 1
    
    if updated > 0:
        with open(PORTFOLIO_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(f"   ✅ Обновлено: {updated} позиций")
    
    return read_portfolio()


def read_portfolio() -> list:
    """Читает open_positions.csv, возвращает список позиций."""
    positions = []
    
    if not os.path.exists(PORTFOLIO_PATH):
        return positions
    
    with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row.get("symbol", "").strip().upper()
            if not symbol:
                continue
            
            try:
                qty = float(row.get("qty", 0))
                avg_price = float(row.get("avg_price", 0))
                total_cost = float(row.get("total_cost", 0))
                current_price = float(row.get("current_price", 0))
                total_value = float(row.get("total_value", 0))
                pnl = float(row.get("pnl", 0))
            except (ValueError, TypeError):
                continue
            
            if qty <= 0:
                continue
            
            positions.append({
                "symbol": symbol,
                "qty": qty,
                "avg_price": avg_price,
                "total_cost": total_cost,
                "current_price": current_price,
                "total_value": total_value,
                "pnl": pnl,
                "pnl_pct": (pnl / total_cost * 100) if total_cost > 0 else 0,
            })
    
    return positions


def calc_portfolio_greeks(positions: list, chain: list) -> dict:
    """
    Считает совокупные Greeks портфеля с учётом опционов.
    
    Bybit delta — изменение цены опциона при изменении SOL на $1.
    Для перевода в SOL: option_delta_in_sols = option_delta / spot_price
    
    Portfolio Delta (SOL) = qty_sol + sum(option_delta / spot * qty_option)
    Portfolio Theta (USD/день) = sum(option_theta * qty_option)
    """
    if not positions:
        return {
            "portfolio_delta": 0,
            "portfolio_theta": 0,
            "net_delta_sols": 0,
        }
    
    # Индекс опционов
    chain_idx = {}
    for ticker in chain:
        parsed = parse_option(ticker)
        if parsed:
            chain_idx[parsed["symbol"]] = parsed
    
    # Собираем spot price
    spot = None
    for ticker in chain:
        parsed = parse_option(ticker)
        if parsed and parsed.get("underlying_price"):
            spot = parsed["underlying_price"]
            break
    
    if spot is None or spot <= 0:
        return {
            "portfolio_delta": 0,
            "portfolio_theta": 0,
            "net_delta_sols": 0,
        }
    
    # Считаем Greeks
    opt_delta_sols = 0
    opt_theta = 0
    
    for pos in positions:
        parsed = chain_idx.get(pos["symbol"])
        if not parsed:
            continue
        
        qty = int(pos.get("qty", 1))
        # Bybit delta — в USD, делим на spot чтобы перевести в SOL
        opt_delta_sols += (parsed["delta"] / spot) * qty
        opt_theta += parsed["theta"] * qty
    
    # Delta портфеля: SOL (delta=1) + опционы (переведённые в SOL)
    spot_qty = sum(p["qty"] for p in positions if p["symbol"] == "SOL")
    net_delta_sols = spot_qty + opt_delta_sols
    
    return {
        "portfolio_delta": round(net_delta_sols, 2),
        "portfolio_theta": round(opt_theta, 2),
        "net_delta_sols": round(net_delta_sols, 2),
    }


def generate_portfolio_summary(portfolio: list, positions: list, chain: list) -> str:
    """Формирует сводку по портфелю + опционам."""
    if not portfolio and not positions:
        return "Нет открытых позиций."
    
    lines = []
    
    # === Портфель SOL ===
    sol_positions = [p for p in portfolio if p["symbol"] == "SOL"]
    if sol_positions:
        total_sol_qty = sum(p["qty"] for p in sol_positions)
        total_sol_cost = sum(p["total_cost"] for p in sol_positions)
        total_sol_value = sum(p["total_value"] for p in sol_positions)
        total_sol_pnl = sum(p["pnl"] for p in sol_positions)
        total_sol_pnl_pct = (total_sol_pnl / total_sol_cost * 100) if total_sol_cost > 0 else 0
        
        spot = None
        if sol_positions:
            spot = sol_positions[0]["current_price"]
        
        lines.append("📊 ПОРТФЕЛЬ SOL")
        lines.append(f"   Количество: {total_sol_qty:.2f} SOL")
        lines.append(f"   Avg Price: ${total_sol_cost / total_sol_qty:.2f}" if total_sol_qty else "   Avg Price: -")
        lines.append(f"   Current: ${spot:.2f}" if spot else "   Current: -")
        lines.append(f"   PnL: ${total_sol_pnl:+.2f} ({total_sol_pnl_pct:+.1f}%)")
        lines.append("")
    
    # === Опционы ===
    if positions:
        # Индекс из chain для получения текущих цен опционов
        chain_idx = {}
        for ticker in chain:
            parsed = parse_option(ticker)
            if parsed:
                chain_idx[parsed["symbol"]] = parsed
        
        opt_total_cost = 0
        opt_total_value = 0
        opt_total_pnl = 0
        
        for pos in positions:
            symbol = pos["symbol"].strip()
            entry_cost = float(pos["total_cost"])
            qty = int(pos["qty"])
            entry_price = float(pos["entry_price"])
            
            # Текущая цена из API
            ticker = chain_idx.get(symbol)
            if ticker:
                current_price = ticker["mark_price"]
                opt_pnl = (current_price - entry_price) * qty
            else:
                current_price = entry_price
                opt_pnl = 0
            
            opt_total_cost += entry_cost
            opt_total_value += current_price * qty
            opt_total_pnl += opt_pnl
        
        opt_pnl_pct = (opt_total_pnl / opt_total_cost * 100) if opt_total_cost > 0 else 0
        
        lines.append(f"📊 ОПЦИОНЫ ({len(positions)} позиций)")
        lines.append(f"   Total Cost: ${opt_total_cost:.2f}")
        lines.append(f"   Current Value: ${opt_total_value:.2f}")
        lines.append(f"   PnL: ${opt_total_pnl:+.2f} ({opt_pnl_pct:+.1f}%)")
        lines.append("")
    
    # === Delta-coverage ===
    greeks = calc_portfolio_greeks(positions, chain)
    lines.append("📊 GREEKS ПОРТФЕЛЯ")
    lines.append(f"   Net Delta: {greeks['net_delta_sols']:+.2f} SOL")
    lines.append(f"   Theta: ${greeks['portfolio_theta']:.2f}/день")
    
    return "\n".join(lines)


def write_tracking(positions: list, chain: list, iv_atm: dict):
    """Записывает/обновляет tracking CSV."""
    headers = [
        "symbol", "current_price", "pnl", "delta", "gamma", "theta", "vega",
        "dte", "iv", "iv_atm", "intrinsic_value", "layer", "updated"
    ]
    
    # Строим индекс из чейна
    chain_idx = {}
    for ticker in chain:
        parsed = parse_option(ticker)
        if parsed:
            chain_idx[parsed["symbol"]] = parsed
    
    file_exists = os.path.exists(TRACKING_PATH)
    file_has_data = file_exists and os.path.getsize(TRACKING_PATH) > 30
    
    with open(TRACKING_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        
        for pos in positions:
            symbol = pos["symbol"].strip()
            ticker = chain_idx.get(symbol)
            
            if not ticker:
                print(f"   ⚠️ {symbol} — нет данных в API")
                continue
            
            entry_price = float(pos["entry_price"])
            qty = int(pos["qty"])
            current_price = ticker["mark_price"]
            strike = float(pos["strike"])
            option_type = pos["type"]
            spot = ticker["underlying_price"]
            
            # PnL
            pnl = (current_price - entry_price) * qty
            
            # DTE
            dte = calc_dte(pos["expiry"])
            
            # IV ATM
            iv_atm_val = iv_atm.get(pos["expiry"], 0)
            
            # Внутренняя стоимость
            intrinsic = calc_intrinsic(strike, option_type, spot)
            
            row = {
                "symbol": symbol,
                "current_price": round(current_price, 4),
                "pnl": round(pnl, 2),
                "delta": round(ticker["delta"], 4),
                "gamma": round(ticker["gamma"], 4),
                "theta": round(ticker["theta"], 4),
                "vega": round(ticker["vega"], 4),
                "dte": dte,
                "iv": round(ticker["iv"], 4),
                "iv_atm": round(iv_atm_val, 4),
                "intrinsic_value": round(intrinsic, 4),
                "layer": pos["layer"].strip(),
                "updated": date.today().strftime("%Y-%m-%d"),
            }
            
            writer.writerow(row)


def generate_recommendations(positions: list, chain: list) -> str:
    """Генерирует рекомендации для каждой позиции."""
    lines = []
    
    # Индекс из чейна
    chain_idx = {}
    for ticker in chain:
        parsed = parse_option(ticker)
        if parsed:
            chain_idx[parsed["symbol"]] = parsed
    
    for pos in positions:
        symbol = pos["symbol"].strip()
        ticker = chain_idx.get(symbol)
        
        if not ticker:
            lines.append(f"⚠️ {symbol} — нет данных API")
            continue
        
        entry_price = float(pos["entry_price"])
        qty = int(pos["qty"])
        current_price = ticker["mark_price"]
        pnl = (current_price - entry_price) * qty
        pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        dte = calc_dte(pos["expiry"])
        layer = pos["layer"].strip()
        delta_abs = abs(ticker["delta"])
        gamma = ticker["gamma"]
        gamma_entry = float(pos["gamma_entry"])
        iv = ticker["iv"]
        iv_entry = float(pos["iv_entry"])
        
        base = f"{symbol} | {layer.title()} | DTE={dte} | PnL={pnl_pct:+.1f}%"
        
        # === ACTIVE LAYER ===
        if layer == "active":
            if pnl_pct >= 30:
                lines.append(f"🔴 {base} → Закрыть (цель достигнута, +{pnl_pct:.1f}%)")
            elif dte < 3 and pnl_pct < 0:
                lines.append(f"🔴 {base} → Закрыть (DTE < 3, импульс не сработал)")
            elif dte < 3 and pnl_pct >= 0:
                lines.append(f"🟡 {base} → Роллировать или закрыть (DTE < 3)")
            elif gamma < gamma_entry * 0.5:
                lines.append(f"🔴 {base} → Закрыть (gamma упала в 2x: {gamma_entry:.3f} → {gamma:.3f})")
            else:
                lines.append(f"🟢 {base} → Мониторить")
        
        # === ADAPTATION LAYER ===
        elif layer == "adaptation":
            if gamma < gamma_entry * 0.3:
                lines.append(f"🔴 {base} → Закрыть (импульс исчерпан, gamma = {gamma_entry:.3f} → {gamma:.3f})")
            elif dte < 7 and pnl_pct < -20:
                lines.append(f"🔴 {base} → Закрыть (DTE < 7, убыток > 20%)")
            elif dte < 7:
                lines.append(f"🟡 {base} → Роллировать (DTE < 7, рынок ещё в зоне)")
            else:
                lines.append(f"🟢 {base} → Мониторить theta-распад")
        
        # === ANCHOR LAYER ===
        elif layer == "anchor":
            if delta_abs < 0.1 and dte < 7:
                lines.append(f"🟡 {base} → Роллировать (delta < 0.1, DTE < 7)")
            elif pnl_pct >= 20:
                lines.append(f"🔴 {base} → Закрыть (цель достигнута, +{pnl_pct:.1f}%)")
            elif dte > 60:
                lines.append(f"🟢 {base} → Мониторить (дальняя защита)")
            else:
                lines.append(f"🟣 {base} → Держать (tail-хедж)")
        
    return "\n".join(lines)


def main():
    print("=" * 70)
    print("📊 МОНИТОРИНГ ПОРТФЕЛЯ + ОПЦИОННЫХ ПОЗИЦИЙ")
    print("=" * 70)
    print(f"   Дата: {date.today().strftime('%Y-%m-%d')}")
    print("=" * 70)
    print()
    
    # 1. Загрузка API — полный чейн (нужен для опционов и Greeks)
    print("🌐 Загрузка полного чейна SOL-опционов...")
    try:
        chain_data = fetch_full_chain()
        print(f"   Получено тикеров: {len(chain_data)}")
    except Exception as e:
        print(f"❌ Ошибка API: {e}")
        return
    
    # 2. Парсинг
    parsed_chain = [parse_option(t) for t in chain_data]
    parsed_chain = [p for p in parsed_chain if p is not None]
    
    # 3. Расчёт IV ATM
    iv_atm = calc_iv_atm(chain_data)
    
    # 4. Чтение реестра опционов
    positions = read_registry()
    print(f"\n📁 Открытых опционов: {len(positions)}")
    
    # 5. Обновление портфеля (актуальный spot price из API)
    spot_price = fetch_spot_price()
    portfolio = update_portfolio(spot_price)
    print(f"📁 Позиций в портфеле: {len(portfolio)}")
    
    # 6. Запись tracking (если есть опционы)
    if positions:
        print(f"\n💾 Запись в {TRACKING_PATH}...")
        write_tracking(positions, chain_data, iv_atm)
        print("   ✅ Готово")
    
    # 7. Сводка портфеля
    print("\n" + "=" * 70)
    print(generate_portfolio_summary(portfolio, positions, chain_data))
    print("=" * 70)
    
    # 8. Рекомендации по опционам
    if positions:
        print("\n🎯 РЕКОМЕНДАЦИИ")
        print("=" * 70)
        recs = generate_recommendations(positions, chain_data)
        print(recs)
        print("=" * 70)
    
    print(f"\n✅ Обновлено: {len(positions)} опционных позиций")
    print(f"   Файл: {TRACKING_PATH}")


if __name__ == "__main__":
    main()
