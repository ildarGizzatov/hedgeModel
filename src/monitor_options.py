"""
monitor_options.py — Мониторинг открытых опционных позиций.

Заменяет CSV:
  - Чтение registry → БД (get_all_open_options)
  - Чтение portfolio → БД (get_position)
  - Запись tracking → БД (record_greeks)
  - Рекомендации → БД (add_recommendation)

Использование:
    python src/monitor_options.py
"""

import os
import sys
from datetime import datetime, date
from pathlib import Path

# Add project to path
PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from src.bybit_api import fetch_option_chain, fetch_spot_price
from src.chain_parser import calc_dte, calc_intrinsic
from src.db import (
    get_all_open_options, get_position, get_latest_greeks,
    update_position_prices, record_greeks, add_recommendation,
    get_all_latest_greeks, execute_query
)

BASE_COIN = "SOL"

# Триггеры по слоям
LAYER_RULES = {
    "anchor": {"delta_hold_threshold": 0.10},
    "adaptation": {"dte_roll_threshold": 7},
    "active": {"dte_close_threshold": 3},
}


def parse_option(ticker):
    """Обёртка над chain_parser.parse_option."""
    return __import__("src.chain_parser", fromlist=["parse_option"]).parse_option(ticker)


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


def fetch_spot_price_local() -> float:
    """Обёртка для fetch_spot_price с BASE_COIN."""
    return fetch_spot_price(BASE_COIN)


def generate_portfolio_summary(positions: list, chain: list) -> str:
    """Формирует сводку по портфелю + опционам."""
    # === Портфель SOL ===
    sol_pos = get_position("SOL")
    sol_line = ""
    if sol_pos:
        total_sol_qty = float(sol_pos["qty"])
        avg_price = float(sol_pos["avg_price"])
        total_cost = float(sol_pos["total_cost"])
        current_price = float(sol_pos["current_price"])
        total_value = float(sol_pos["total_value"])
        pnl = float(sol_pos["pnl"])
        pnl_pct = (pnl / total_cost * 100) if total_cost > 0 else 0
        
        sol_line = (
            f"📊 ПОРТФЕЛЬ SOL\n"
            f"   Количество: {total_sol_qty:.2f} SOL\n"
            f"   Avg Price: ${avg_price:.2f}\n"
            f"   Current: ${current_price:.2f}\n"
            f"   PnL: ${pnl:+.2f} ({pnl_pct:+.1f}%)\n"
        )
    
    # === Опционы ===
    opt_line = ""
    if positions:
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
            entry_cost = float(pos["total_cost"]) if pos["total_cost"] is not None else float(pos["entry_price"]) * int(pos["qty"])
            qty = int(pos["qty"])
            entry_price = float(pos["entry_price"])
            
            # Текущая цена из API
            ticker_data = chain_idx.get(symbol)
            if ticker_data:
                current_price = ticker_data["mark_price"]
                opt_pnl = (current_price - entry_price) * qty
            else:
                current_price = entry_price
                opt_pnl = 0
            
            opt_total_cost += entry_cost
            opt_total_value += current_price * qty
            opt_total_pnl += opt_pnl
        
        opt_pnl_pct = (opt_total_pnl / opt_total_cost * 100) if opt_total_cost > 0 else 0
        
        opt_line = (
            f"📊 ОПЦИОНЫ ({len(positions)} позиций)\n"
            f"   Total Cost: ${opt_total_cost:.2f}\n"
            f"   Current Value: ${opt_total_value:.2f}\n"
            f"   PnL: ${opt_total_pnl:+.2f} ({opt_pnl_pct:+.1f}%)\n"
        )
    
    # === Delta-coverage ===
    greeks = calc_portfolio_greeks(positions, chain)
    greeks_line = (
        f"📊 GREEKS ПОРТФЕЛЯ\n"
        f"   Net Delta: {greeks['net_delta_sols']:+.2f} SOL\n"
        f"   Theta: ${greeks['portfolio_theta']:.2f}/день\n"
    )
    
    return sol_line + opt_line + greeks_line


def calc_portfolio_greeks(positions: list, chain: list) -> dict:
    """
    Считает совокупные Greeks портфеля с учётом опционов.
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
    spot_qty = 0
    sol_pos = get_position("SOL")
    if sol_pos:
        spot_qty = float(sol_pos["qty"])
    
    net_delta_sols = spot_qty + opt_delta_sols
    
    return {
        "portfolio_delta": round(net_delta_sols, 2),
        "portfolio_theta": round(opt_theta, 2),
        "net_delta_sols": round(net_delta_sols, 2),
    }


def record_greeks_to_db(positions: list, chain: list, iv_atm: dict) -> None:
    """Записывает/обновляет Greeks в БД (option_greeks_history)."""
    # Строим индекс из чейна
    chain_idx = {}
    for ticker in chain:
        parsed = parse_option(ticker)
        if parsed:
            chain_idx[parsed["symbol"]] = parsed
    
    for pos in positions:
        symbol = pos["symbol"].strip()
        ticker_data = chain_idx.get(symbol)
        
        if not ticker_data:
            print(f"   ⚠️ {symbol} — нет данных в API")
            continue
        
        # Ищем option_id по symbol
        option = execute_query(
            "SELECT id FROM options WHERE symbol=?", (symbol,)
        )
        if not option:
            print(f"   ⚠️ {symbol} — не найден в options")
            continue
        
        option_id = option[0]["id"]
        
        entry_price = float(pos["entry_price"])
        qty = int(pos["qty"])
        current_price = ticker_data["mark_price"]
        strike = float(pos["strike"])
        option_type = pos["type"]
        spot = ticker_data["underlying_price"]
        
        # PnL
        pnl = (current_price - entry_price) * qty
        
        # DTE
        dte = calc_dte(pos["expiry"])
        
        # IV ATM
        iv_atm_val = iv_atm.get(pos["expiry"], 0)
        
        # Внутренняя стоимость
        intrinsic = calc_intrinsic(strike, option_type, spot)
        
        # Запись в БД
        record_greeks(
            option_id=option_id,
            option_symbol=symbol,
            current_price=current_price,
            delta=ticker_data["delta"],
            gamma=ticker_data["gamma"],
            theta=ticker_data["theta"],
            vega=ticker_data["vega"],
            iv=ticker_data["iv"],
            iv_atm=iv_atm_val,
            dte=dte,
            intrinsic_value=intrinsic,
            unrealized_pnl=pnl,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )


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
        ticker_data = chain_idx.get(symbol)
        
        if not ticker_data:
            lines.append(f"⚠️ {symbol} — нет данных API")
            continue
        
        entry_price = float(pos["entry_price"])
        qty = int(pos["qty"])
        current_price = ticker_data["mark_price"]
        pnl = (current_price - entry_price) * qty
        pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        dte = calc_dte(pos["expiry"])
        layer = pos["layer"].strip()
        delta_abs = abs(ticker_data["delta"])
        gamma = ticker_data["gamma"]
        gamma_entry = float(pos["gamma_entry"])
        iv = ticker_data["iv"]
        iv_entry = float(pos["iv_entry"])
        
        base = f"{symbol} | {layer.title()} | DTE={dte} | PnL={pnl_pct:+.1f}%"
        
        # === ACTIVE LAYER ===
        if layer == "active":
            if pnl_pct >= 30:
                rec = f"🔴 {base} → Закрыть (цель достигнута, +{pnl_pct:.1f}%)"
                action = "sell"
            elif dte < 3 and pnl_pct < 0:
                rec = f"🔴 {base} → Закрыть (DTE < 3, импульс не сработал)"
                action = "sell"
            elif dte < 3 and pnl_pct >= 0:
                rec = f"🟡 {base} → Роллировать или закрыть (DTE < 3)"
                action = "roll"
            elif gamma < gamma_entry * 0.5:
                rec = f"🔴 {base} → Закрыть (gamma упала в 2x: {gamma_entry:.3f} → {gamma:.3f})"
                action = "sell"
            else:
                rec = f"🟢 {base} → Мониторить"
                action = "hold"
        
        # === ADAPTATION LAYER ===
        elif layer == "adaptation":
            if gamma < gamma_entry * 0.3:
                rec = f"🔴 {base} → Закрыть (импульс исчерпан, gamma = {gamma_entry:.3f} → {gamma:.3f})"
                action = "sell"
            elif dte < 7 and pnl_pct < -20:
                rec = f"🔴 {base} → Закрыть (DTE < 7, убыток > 20%)"
                action = "sell"
            elif dte < 7:
                rec = f"🟡 {base} → Роллировать (DTE < 7, рынок ещё в зоне)"
                action = "roll"
            else:
                rec = f"🟢 {base} → Мониторить theta-распад"
                action = "hold"
        
        # === ANCHOR LAYER ===
        elif layer == "anchor":
            if delta_abs < 0.1 and dte < 7:
                rec = f"🟡 {base} → Роллировать (delta < 0.1, DTE < 7)"
                action = "roll"
            elif pnl_pct >= 20:
                rec = f"🔴 {base} → Закрыть (цель достигнута, +{pnl_pct:.1f}%)"
                action = "sell"
            elif dte > 60:
                rec = f"🟢 {base} → Мониторить (дальняя защита)"
                action = "hold"
            else:
                rec = f"🟣 {base} → Держать (tail-хедж)"
                action = "hold"
        
        lines.append(rec)
        
        # Запись рекомендации в БД
        try:
            option_id = execute_query(
                "SELECT id FROM options WHERE symbol=?", (symbol,)
            )[0]["id"]
            add_recommendation(
                option_id=option_id,
                option_symbol=symbol,
                action=action,
                reason=f"{layer}: PnL={pnl_pct:+.1f}%, DTE={dte}, gamma={gamma:.3f}",
                confidence=0.8,
                llm_model="rule-based",
            )
        except Exception:
            pass
    
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
        chain_data = fetch_option_chain(BASE_COIN)
        print(f"   Получено тикеров: {len(chain_data)}")
    except Exception as e:
        print(f"❌ Ошибка API: {e}")
        return
    
    # 2. Парсинг
    parsed_chain = [parse_option(t) for t in chain_data]
    parsed_chain = [p for p in parsed_chain if p is not None]
    
    # 3. Расчёт IV ATM
    iv_atm = calc_iv_atm(chain_data)
    
    # 4. Чтение реестра опционов из БД
    positions = get_all_open_options()
    print(f"\n📁 Открытых опционов (БД): {len(positions)}")
    
    # 5. Обновление портфеля (актуальный spot price из API)
    spot_price = fetch_spot_price_local()
    if spot_price > 0:
        update_position_prices("SOL", spot_price)
        print(f"   ✅ SOL обновлён: ${spot_price:.2f}")
    else:
        print("   ⚠️ Spot price не получен")
    
    # 6. Запись Greeks в БД
    if positions:
        print(f"\n💾 Запись Greeks в БД...")
        record_greeks_to_db(positions, chain_data, iv_atm)
        print("   ✅ Готово")
    
    # 7. Сводка портфеля
    print("\n" + "=" * 70)
    print(generate_portfolio_summary(positions, chain_data))
    print("=" * 70)
    
    # 8. Рекомендации по опционам
    if positions:
        print("\n🎯 РЕКОМЕНДАЦИИ")
        print("=" * 70)
        recs = generate_recommendations(positions, chain_data)
        print(recs)
        print("=" * 70)
    
    print(f"\n✅ Обновлено: {len(positions)} опционных позиций (БД)")


if __name__ == "__main__":
    main()
