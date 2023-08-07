from logger import Logger
import os
import pprint
import time
from typing import Any
from typing import Callable

from tokens import Tokens
from coingecko import CoinGecko
from cowswap import get_cowswap
from kyberswap import get_swap_route
from kyberswap import get_swap_route_usd


log = Logger().get_logger()
MAX_ITERS = 20


def calculate_max_drawdown(prices, period_length):
    rolling_max = prices.rolling(period_length, min_periods=1).max()
    daily_drawdown = prices / rolling_max - 1.0
    max_drawdown = daily_drawdown.rolling(period_length, min_periods=1).min()
    return max_drawdown


def price_impact_size(
    token_in: str,
    token_in_decimals: int,
    token_out: str,
    token_out_decimals: int,
    target_price_impact: float,
    rtol=5e-2,
):
    """
    Returns the amount of token_in required to incur a price impact of {price_impact}.

    Ex: price_impact_size(weth, usdc, 0.10) returns the amount of WETH necessary to incur 10%
    price impact (+/- 0.01).
    """

    def kyberswap_oracle(token_in: str, token_out: str, size: float, retries=3):
        response = get_swap_route(
            "ethereum", token_in, token_out, token_in_decimals, size
        )
        route = response["data"]["routeSummary"]
        price_impact = 1 - float(route["amountOutUsd"]) / float(route["amountInUsd"])
        return price_impact

    spot = CoinGecko().current_price(token_in, "ethereum")
    min_sz = 0
    max_sz = 100_000_000 / spot
    iters = 0
    price_impact = 1  # default start to run at least one iter

    st = time.time()
    while abs(1 - (price_impact / target_price_impact)) > rtol and iters < MAX_ITERS:
        _st = time.time()
        mid = (max_sz + min_sz) / 2.0
        price_impact = kyberswap_oracle(token_in, token_out, mid)

        if price_impact < target_price_impact:
            min_sz = mid
        else:
            max_sz = mid

        # print(f"{iters:2d} | x = {mid:.2f} | price impact: {price_impact:.4f} | elapsed: {time.time() - st:.2f}s | per query: {time.time() - _st:.3f}s")
        # TODO: Figure out exact time to avoid rate limiting
        time.sleep(0.05)
        iters += 1

    return (max_sz + mid) / 2.0


# TODO: Unify interface for cow/kyber
def price_impact_size_cowswap(
    token_in: str,
    token_in_decimals: int,
    token_out: str,
    token_out_decimals: int,
    target_price_impact: float,
    rtol=5e-2,
    max_sz_usd=500_000_000,
):
    cg = CoinGecko()
    spot_in = cg.current_price(token_in)
    spot_out = cg.current_price(token_out)

    def cowswap_oracle(token_in, token_out, size, retries=3):
        response = get_cowswap(
            token_in, token_out, token_in_decimals, size, quality="fast"
        )
        amount_in_usd = (
            float(response["quote"]["sellAmount"]) / (10**token_in_decimals) * spot_in
        )
        amount_out_usd = (
            float(response["quote"]["buyAmount"])
            / (10**token_out_decimals)
            * spot_out
        )
        price_impact = 1 - float(amount_out_usd / amount_in_usd)
        return price_impact

    coingecko = CoinGecko()
    spot_in = cg.current_price(token_in)
    spot_out = cg.current_price(token_out)
    min_sz = 0
    max_sz = max_sz_usd / spot_in  # hundred mill as a loose upper bound seems okay?
    iters = 0
    price_impact = 1

    st = time.time()
    while abs(1 - (price_impact / target_price_impact)) > rtol and iters < MAX_ITERS:
        _st = time.time()
        mid = (max_sz + min_sz) / 2.0
        price_impact = cowswap_oracle(token_in, token_out, mid)

        if price_impact < target_price_impact:
            min_sz = mid
        else:
            max_sz = mid

        log.info(
            f"{iters:2d} | x = {mid:.2f} | price impact: {price_impact:.4f} | elapsed: {time.time() - st:.2f}s | per query: {time.time() - _st:.3f}s"
        )
        iters += 1
    return (max_sz + mid) / 2.0


if __name__ == "__main__":
    pis = {}

    for tok in [Tokens.USDC, Tokens.WETH]:
        pis[tok.symbol] = {}
        tok_out = Tokens.USDT if tok == Tokens.USDC else Tokens.USDC

        for p in [0.005, 0.25]:
            pis[tok.symbol][p] = price_impact_size_cowswap(
                tok.address,
                tok.decimals,
                tok_out.address,
                tok_out.decimals,
                p,
                max_sz_usd=1_000_000_000,
            )
            print(tok, p, pis[tok.symbol][p])
        log.info("-" * 20)

    pprint.pp(pis)
