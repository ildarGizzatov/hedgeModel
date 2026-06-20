#!/usr/bin/env python3
"""
anchor_picker.py — подбор Anchor Layer (Core + Tail).

Алгоритм по [[203-anchor-selection-algorithm]]:
  Шаг 0: Расчёт бюджета
  Шаг 1: Фильтрация кандидатов (PUT, DTE>=25, dist 8–35%)
  Шаг 2: Матрица эффективности E(S, K)
  Шаг 3: Выбор Core (K1) — max E(-20%), strike > S_target
          Выбор Tail (K2) — max Acceleration, K2 ≠ K1
  Шаг 4: Подбор (n1, n2) — DeltaRatio(-20%) >= 80%, Core <= 60% бюджета,
          минимизация отклонения от 100%
  Шаг 5: Вывод рекомендаций

Читает позицию из БД, chain из Bybit API.
"""

import math
import sys
from datetime import datetime, date
from pathlib import Path

import tomllib

# Add project to path
PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from src.db import get_position
from src.bybit_api import fetch_option_chain, fetch_spot_price
from src.chain_parser import parse_option, calc_dte


# ============================================================
# BS (r = 0)
# ============================================================

def _bs_d1(S, K, T, sigma):
    if T <= 1e-12 or S <= 0 or K <= 0:
        return 0.0
    return (math.log(S / K) + 0.5 * sigma ** 2 * T) / (sigma * math.sqrt(T))


def _bs_ndist(x):
    """Cumulative normal distribution (Abramowitz & Stegun approximation)."""
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p = 0.3275911
    sgn = 1 if x >= 0 else -1
    xa = abs(x)
    t = 1.0 / (1.0 + p * xa)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-xa ** 2 / 2)
    return 0.5 * (1.0 + sgn * y)


def bs_price_put(S, K, T, sigma):
    """Black-Scholes put price (r=0)."""
    if T <= 1e-12:
        return max(K - S, 0)
    if sigma <= 1e-12:
        return max(K - S, 0)
    d1 = _bs_d1(S, K, T, sigma)
    d2 = d1 - sigma * math.sqrt(T)
    return K * _bs_ndist(-d2) - S * _bs_ndist(-d1)


def bs_delta_put(S, K, T, sigma):
    """Black-Scholes put delta."""
    if T <= 1e-12:
        return -1.0 if S < K else 0.0
    if sigma <= 1e-12:
        return -1.0 if S < K else 0.0
    return _bs_ndist(_bs_d1(S, K, T, sigma)) - 1.0


# ============================================================
# CONFIG
# ============================================================

def load_config():
    """Load config.toml."""
    cfg_path = PROJECT_DIR / "config.toml"
    if not cfg_path.exists():
        print(f"⚠️ {cfg_path.name} не найден — запустите gen_config.py")
        return {}
    with open(cfg_path, "rb") as f:
        return tomllib.load(f)


def layer_pct(config, name):
    """Get layer allocation percentage."""
    layers = config.get("layer_allocation", {})
    if name in layers:
        return layers[name]
    for k, v in layers.items():
        if name.lower() in k.lower():
            return v
    return 50


# ============================================================
# DATA — ПОЗИЦИЯ ИЗ БД
# ============================================================

def load_positions():
    """Load SOL position from БД.
    Returns (qty, avg_price) or None on error.
    """
    pos = get_position("SOL")
    if not pos:
        print(f"⚠️ Позиция SOL не найдена в БД")
        return None

    qty = float(pos["qty"])
    avg_price = float(pos["avg_price"])

    if qty <= 0:
        print(f"⚠️ Позиция SOL: qty={qty} (нужно > 0)")
        return None

    return qty, avg_price


# ============================================================
# MAIN
# ============================================================

def main():
    # ============================================================
    # ШАГ 0: Расчёт бюджета
    # ============================================================
    config = load_config()
    positions = load_positions()
    if positions is None:
        return
    qty, avg_price = positions

    global_budget_pct = config["global_budget_pct"] / 100
    target_dd_pct = config["target_dd_pct"] / 100
    anchor_layer_pct = layer_pct(config, "Anchor") / 100

    position_size = qty * avg_price
    total_budget = position_size * global_budget_pct
    anchor_budget = total_budget * anchor_layer_pct

    # Целевой уровень (просадка от avg-цены)
    s_target = avg_price * (1 - target_dd_pct)

    # Спот и чейн из Bybit API
    print("\n[0/5] Загрузка данных с Bybit API...")
    spot = fetch_spot_price("SOL")
    if spot <= 0:
        print("⚠️ Не удалось получить spot-цену с Bybit")
        return
    print(f"   Spot SOL: ${spot:.2f}")

    chain_raw = fetch_option_chain("SOL")
    if not chain_raw:
        print("⚠️ Не удалось получить option chain с Bybit")
        return

    chain = []
    for ticker in chain_raw:
        parsed = parse_option(ticker)
        if parsed is None:
            continue
        parsed["dte"] = calc_dte(parsed["expiry_str"])
        chain.append(parsed)

    print(f"   Получено опционов: {len(chain)}")

    print("=" * 70)
    print("ANCHOR LAYER SELECTION (T006)")
    print("=" * 70)
    print(f"  SOL qty:         {qty:.2f}")
    print(f"  Avg Buy Price:   ${avg_price:.2f}")
    print(f"  Spot Price:      ${spot:.2f}")
    print(f"  S_target (−{target_dd_pct*100:.0f}%): ${s_target:.2f}")
    print(f"  Position Size:   ${position_size:,.2f}")
    print(f"  Total Budget:    {global_budget_pct*100:.1f}% = ${total_budget:,.2f}")
    print(f"  Anchor Budget:   {anchor_layer_pct*100:.1f}% = ${anchor_budget:,.2f}")
    print("=" * 70)

    # ============================================================
    # ШАГ 1: Фильтрация кандидатов
    # ============================================================

    # --- Anchor filter params (все — строго из конфига) ---
    af = config.get("anchor_filter")
    if af is None:
        print("⚠️ В config.toml нет секции [anchor_filter]")
        return

    def _af(key):
        """Read anchor_filter param or fail."""
        val = af.get(key)
        if val is None:
            print(f"⚠️ В [anchor_filter] нет ключа: {key}")
            return None
        return val

    min_dte = _af("min_dte")
    dist_min = _af("dist_min_pct")
    max_delta = _af("max_delta")
    min_delta = _af("min_delta")

    if min_dte is None:
        return

    # Фильтр PUT-опционов
    puts = [o for o in chain if o["type"] == "PUT"]
    total_puts = len(puts)
    print(f"\n  PUT-опционов всего: {total_puts}")

    # DTE >= min_dte
    puts = [o for o in puts if o["dte"] >= min_dte]
    print(f"  DTE >= {min_dte}:             {len(puts)} (убрано {total_puts - len(puts)})")

    # Distance от средней цены покупки: >= dist_min %
    for o in puts:
        o["dist"] = abs(avg_price - o["strike"]) / avg_price * 100
    puts = [o for o in puts if o["dist"] >= dist_min]
    print(f"  dist >= {dist_min}%:            {len(puts)} (убрано {total_puts - len(puts)})")

    # Максимальная delta (верхняя граница для OTM PUT)
    puts = [o for o in puts if abs(o["delta"]) <= max_delta]
    print(f"  |Delta| <= {max_delta}:         {len(puts)} (убрано {total_puts - len(puts)})")

    # Антипаттерн: |Delta| < min_delta — слишком дешёвые
    puts = [o for o in puts if abs(o["delta"]) >= min_delta]
    print(f"  |Delta| >= {min_delta}:       {len(puts)} (убрано {total_puts - len(puts)})")

    puts = sorted(puts, key=lambda o: o["strike"])

    if not puts:
        print("⚠️ Нет Put-опционов для анализа после фильтрации")
        return

    # ============================================================
    # ШАГ 2: Матрица эффективности E(S, K)
    # ============================================================
    # E(S, K) = (BS_Price(S_target, K, T, IV) - Premium) / Premium
    # Baseline Strength = E(-20%)
    # Acceleration = E(-35%) - E(-20%)

    results = []
    for c in puts:
        K = c["strike"]
        T = c["dte"] / 365.0
        sigma = c["iv"]
        premium = c["mark_price"]

        if premium <= 0:
            continue

        # E(-20%) и E(-35%)
        S20 = spot * 0.80
        S35 = spot * 0.65

        e20 = (bs_price_put(S20, K, T, sigma) - premium) / premium
        e35 = (bs_price_put(S35, K, T, sigma) - premium) / premium
        accel = e35 - e20

        results.append({
            "symbol": c["symbol"],
            "strike": K,
            "T": T,
            "IV": sigma,
            "premium": premium,
            "dte": c["dte"],
            "dist": c["dist"],
            "delta": abs(c["delta"]),
            "E20": e20,
            "E35": e35,
            "accel": accel,
        })

    print(f"\n  Кандидатов: {len(results)}")
    print(f"  {'K':>5}  {'dist':>5}  {'DTE':>4}  {'E20':>6}  {'E35':>6}  {'acc':>6}  {'prem':>7}  {'Δ':>5}")
    print("  " + "-" * 65)
    for r in results:
        print(f"  {int(r['strike']):>5}  {r['dist']:>5.1f}%  {r['dte']:>4}  "
              f"{r['E20']:>6.3f}  {r['E35']:>6.3f}  {r['accel']:>6.3f}  "
              f"${r['premium']:>6.3f}  {r['delta']:>5.3f}")

    # ============================================================
    # ШАГ 3: Выбор Core (K1) и Tail (K2)
    # ============================================================

    # Core: страйк >= S_target (ближе к ATM), max E20
    core_range = [r for r in results if r["strike"] >= s_target]

    if not core_range:
        core_range = results[:]

    k1 = max(core_range, key=lambda r: r["E20"])

    # Tail: max Acceleration, K2 ≠ K1, K2 < K1 (ниже Core)
    tail_range = [r for r in results
                  if r["strike"] != k1["strike"]
                  and r["strike"] < k1["strike"]]

    if not tail_range:
        tail_range = [r for r in results if r["strike"] != k1["strike"]]

    k2 = max(tail_range, key=lambda r: r["accel"])

    print(f"\n  ⭐ K1 (Core) = Strike ${int(k1['strike'])}")
    print(f"     dist={k1['dist']:.1f}%  E20={k1['E20']:.3f}  accel={k1['accel']:.3f}  "
          f"premium=${k1['premium']:.3f}  DTE={k1['dte']}")
    print(f"  ⭐ K2 (Tail) = Strike ${int(k2['strike'])}")
    print(f"     dist={k2['dist']:.1f}%  E20={k2['E20']:.3f}  accel={k2['accel']:.3f}  "
          f"premium=${k2['premium']:.3f}  DTE={k2['dte']}")

    # ============================================================
    # ШАГ 4: Расчёт количества контрактов (перебор)
    # ============================================================

    # Delta-профиль Core и Tail на уровнях падения
    S_level_20 = avg_price * 0.80
    d1_at_20 = abs(bs_delta_put(S_level_20, k1["strike"], k1["T"], k1["IV"]))
    d2_at_20 = abs(bs_delta_put(S_level_20, k2["strike"], k2["T"], k2["IV"]))

    # --- Anchor budget split (из конфига) ---
    afb = config.get("anchor_budget_split", {})
    core_pct = afb.get("core_pct", 60) / 100
    tail_pct = afb.get("tail_pct", 40) / 100

    # --- Коррекция бюджета по дистанции ---
    core_budget = anchor_budget * core_pct
    tail_budget = anchor_budget * tail_pct

    k1_dist_ok = k1["dist"] >= dist_min
    k2_dist_ok = k2["dist"] >= dist_min

    if not k1_dist_ok:
        core_budget *= 0.70
        print(f"  ⚠️ Core dist={k1['dist']:.1f}% < {dist_min}% → бюджет ×0.7")
    if not k2_dist_ok:
        tail_budget *= 0.70
        print(f"  ⚠️ Tail dist={k2['dist']:.1f}% < {dist_min}% → бюджет ×0.7")

    # --- Перебор (n1, n2) ---
    n1_max = int(core_budget / k1["premium"]) if k1["premium"] > 0 else 0
    n1_max = min(n1_max, 50)

    best = None
    best_score = float("inf")

    for n1 in range(1, n1_max + 1):
        cost1 = n1 * k1["premium"]
        if cost1 > core_budget:
            break
        remaining = tail_budget
        n2_max_here = int(remaining / k2["premium"]) if k2["premium"] > 0 else 0
        n2_max_here = min(n2_max_here, 50)

        for n2 in range(1, n2_max_here + 1):
            cost2 = n2 * k2["premium"]
            total_cost = cost1 + cost2
            if total_cost > anchor_budget:
                break

            # DeltaRatio при падении на 20% от avg
            delta_total = (n1 * d1_at_20 + n2 * d2_at_20) / qty
            if delta_total < 0.80:
                continue

            # Оценка отклонения от 100% delta (штраф за перекос)
            deviation = abs(delta_total - 1.0)

            # Оценка эффективности (PnL при -20% / cost)
            S20 = spot * 0.80
            p1_20 = bs_price_put(S20, k1["strike"], k1["T"], k1["IV"])
            p2_20 = bs_price_put(S20, k2["strike"], k2["T"], k2["IV"])
            pnl_20 = (p1_20 - k1["premium"]) * n1 + (p2_20 - k2["premium"]) * n2
            eff = pnl_20 / total_cost if total_cost > 0 else 0

            # Score: минимизируем отклонение delta, максимизируем eff
            score = deviation * 2 - eff * 0.1

            if score < best_score:
                best_score = score
                best = {
                    "n1": n1, "n2": n2,
                    "cost1": cost1, "cost2": cost2,
                    "total_cost": total_cost,
                    "delta_20": delta_total,
                    "eff_20": eff
                }

    if best is None:
        print("\n⚠️ Не удалось найти (n1, n2) с DeltaRatio >= 80%")
        print(f"   Пробуем минимальные n1=1, n2=1")
        best = {
            "n1": 1, "n2": 1,
            "cost1": k1["premium"], "cost2": k2["premium"],
            "total_cost": k1["premium"] + k2["premium"],
            "delta_20": (d1_at_20 + d2_at_20) / qty,
            "eff_20": 0
        }

    n1 = best["n1"]
    n2 = best["n2"]

    print(f"\n  n1={n1}, n2={n2}  delta(-20%)={best['delta_20']:.0%}  eff={best['eff_20']:.2f}x")
    print(f"  cost: ${best['cost1']:.2f} + ${best['cost2']:.2f} = ${best['total_cost']:.2f} / ${anchor_budget:.2f}")

    # ============================================================
    # ШАГ 5: Вывод рекомендаций
    # ============================================================
    print(f"\n  ⭐ K1 (Core) = Strike ${int(k1['strike'])}")
    print(f"     dist={k1['dist']:.1f}%  E20={k1['E20']:.3f}  accel={k1['accel']:.3f}  "
          f"premium=${k1['premium']:.3f}  DTE={k1['dte']}")
    print(f"  ⭐ K2 (Tail) = Strike ${int(k2['strike'])}")
    print(f"     dist={k2['dist']:.1f}%  E20={k2['E20']:.3f}  accel={k2['accel']:.3f}  "
          f"premium=${k2['premium']:.3f}  DTE={k2['dte']}")

    print("\n" + "=" * 70)
    print("РЕКОМЕНДАЦИЯ")
    print("=" * 70)

    cp1 = k1["symbol"].split("-")
    cp2 = k2["symbol"].split("-")
    print(f"  CORE: SOL-{cp1[1]}-{int(k1['strike'])}-P-USDT  x{n1}  ${best['cost1']:.2f}")
    print(f"  TAIL: SOL-{cp2[1]}-{int(k2['strike'])}-P-USDT  x{n2}  ${best['cost2']:.2f}")
    print(f"  TOTAL: {n1 + n2} contracts, ${best['total_cost']:.2f} / ${anchor_budget:.2f}")

    # Delta-профиль и PnL на уровнях
    print(f"\n  {'Level':>7}  {'S':>8}  {'Delta':>8}  {'Ratio':>7}  {'PnL':>8}  {'Eff':>5}")
    print("  " + "-" * 55)

    levels = [10, 15, 20, 25, 30]
    for l in levels:
        S_d = avg_price * (1 - l / 100)

        # Delta на уровне
        d1_l = abs(bs_delta_put(S_d, k1["strike"], k1["T"], k1["IV"]))
        d2_l = abs(bs_delta_put(S_d, k2["strike"], k2["T"], k2["IV"]))
        delta_ratio = (n1 * d1_l + n2 * d2_l) / qty

        # PnL
        p1 = bs_price_put(S_d, k1["strike"], k1["T"], k1["IV"])
        p2 = bs_price_put(S_d, k2["strike"], k2["T"], k2["IV"])
        pnl = (p1 - k1["premium"]) * n1 + (p2 - k2["premium"]) * n2

        # Efficiency
        eff = abs(pnl) / best["total_cost"] if best["total_cost"] > 0 else 0

        mark = ""
        if l == 20:
            if delta_ratio >= 0.80:
                mark = "✓ OK"
            else:
                mark = "⚠️ LOW"

        print(f"  -{l:>2}%  ${S_d:>7.2f}  {n1*d1_l+n2*d2_l:>7.1f}  {delta_ratio:>6.0%}  ${pnl:>7.2f}  {eff:>4.2f}x {mark}")

    # Delta verification
    print("\n  " + "-" * 55)
    delta_20 = best["delta_20"]
    if delta_20 >= 0.80:
        print(f"  ✓ Delta(-20%) = {delta_20:.0%} >= 80% ✅")
    else:
        print(f"  ⚠️ Delta(-20%) = {delta_20:.0%} < 80% — не хватает покрытия")

    core_pct_used = (best["cost1"] / anchor_budget * 100) if anchor_budget > 0 else 0
    if core_pct_used <= 60:
        print(f"  ✓ Core cost = {core_pct_used:.1f}% <= 60% ✅")
    else:
        print(f"  ⚠️ Core cost = {core_pct_used:.1f}% > 60% — нарушен лимит")

    print("=" * 70)


if __name__ == '__main__':
    main()
