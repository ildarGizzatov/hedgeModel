"""
Black-Scholes расчёт цены и греков опциона.
r = 0% (стандарт для криптоопционов).
"""
import math
from dataclasses import dataclass


def d1(S: float, K: float, T: float, sigma: float) -> float:
    return (math.log(S / K) + (sigma ** 2 / 2) * T) / (sigma * math.sqrt(T))


def d2(S: float, K: float, T: float, sigma: float) -> float:
    return d1(S, K, T, sigma) - sigma * math.sqrt(T)


def normal_cdf(x: float) -> float:
    """Стандартная нормальная КФФ через math.erf."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


@dataclass
class Greeks:
    """Цена и греки для Put-опциона."""
    price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float  # всегда ~0 при r=0


@dataclass
class CallGreeks:
    """Цена и греки для Call-опциона."""
    price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


def put(S: float, K: float, T: float, sigma: float) -> Greeks:
    """Black-Scholes Put."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        price = max(K - S, 0) if T <= 0 else 0
        return Greeks(price=price, delta=-1 if T <= 0 and S < K else 0,
                      gamma=0, theta=0, vega=0, rho=0)

    sT = sigma * math.sqrt(T)
    d = d1(S, K, T, sigma)
    d_ = d2(S, K, T, sigma)

    N_d1 = normal_cdf(d)
    N_d2 = normal_cdf(d_)
    phi_d = 1.0 / math.sqrt(2.0 * math.pi) * math.exp(-d ** 2 / 2)

    # Put
    price = K * math.exp(0) * (1 - N_d2) - S * (1 - N_d1)
    price = max(price, 0)  # price не может быть < 0

    delta = N_d1 - 1  # put delta: -N(-d1) = N(d1) - 1
    gamma = phi_d / (S * sT)
    theta = -(S * phi_d * sigma) / (2 * math.sqrt(T)) + 0  # r=0
    # theta put: theta = -S*phi*d*sigma/(2*sqrt(T)) + K*r*e^(-rT)*N(d2)
    # при r=0: theta = -S*phi*d*sigma/(2*sqrt(T))
    vega = S * phi_d * math.sqrt(T)
    rho = -K * T * math.exp(0) * N_d2  # отрицательный

    return Greeks(
        price=price,
        delta=round(delta, 4),
        gamma=round(gamma, 6),
        theta=round(theta, 4),
        vega=round(vega, 4),
        rho=round(rho, 4),
    )


def call(S: float, K: float, T: float, sigma: float) -> CallGreeks:
    """Black-Scholes Call."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        price = max(S - K, 0) if T <= 0 else 0
        return CallGreeks(price=price, delta=1 if T <= 0 and S > K else 0,
                          gamma=0, theta=0, vega=0, rho=0)

    sT = sigma * math.sqrt(T)
    d = d1(S, K, T, sigma)
    d_ = d2(S, K, T, sigma)

    phi_d = 1.0 / math.sqrt(2.0 * math.pi) * math.exp(-d ** 2 / 2)
    N_d1 = normal_cdf(d)
    N_d2 = normal_cdf(d_)

    price = S * N_d1 - K * math.exp(0) * N_d2
    price = max(price, 0)

    delta = N_d1
    gamma = phi_d / (S * sT)
    theta = -(S * phi_d * sigma) / (2 * math.sqrt(T))
    vega = S * phi_d * math.sqrt(T)
    rho = K * T * math.exp(0) * N_d2

    return CallGreeks(
        price=price,
        delta=round(delta, 4),
        gamma=round(gamma, 6),
        theta=round(theta, 4),
        vega=round(vega, 4),
        rho=round(rho, 4),
    )


if __name__ == "__main__":
    # Тест: пример с известными данными
    S = 79.82
    K = 80.0
    T = 10 / 365  # 10 дней
    sigma = 0.80  # 80% IV

    p = put(S, K, T, sigma)
    c = call(S, K, T, sigma)
    print(f"Spot: ${S}, Strike: ${K}, TTE: {T:.4f} ({T*365:.1f} дн.), IV: {sigma:.1%}")
    print(f"\nPut:")
    print(f"  Price:  ${p.price:.4f}")
    print(f"  Delta:  {p.delta:.4f}")
    print(f"  Gamma:  {p.gamma:.6f}")
    print(f"  Theta:  {p.theta:.4f}")
    print(f"  Vega:   {p.vega:.4f}")
    print(f"\nCall:")
    print(f"  Price:  ${c.price:.4f}")
    print(f"  Delta:  {c.delta:.4f}")
    print(f"  Gamma:  {c.gamma:.6f}")
    print(f"  Theta:  {c.theta:.4f}")
    print(f"  Vega:   {c.vega:.4f}")
