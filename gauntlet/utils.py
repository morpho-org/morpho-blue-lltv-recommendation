import time
from typing import Any
from typing import Callable

import pandas as pd
import numpy as np

from kyberswap import get_swap_route, get_swap_route_usd
from coingecko import CoinGecko
from cowswap import get_cowswap

MAX_ITERS = 20

def calculate_max_drawdown(prices, period_length):
    rolling_max = prices.rolling(period_length, min_periods=1).max()
    daily_drawdown = prices / rolling_max - 1.0
    max_drawdown = daily_drawdown.rolling(period_length, min_periods=1).min()
    return max_drawdown


def price_impact_size(token_in: str, token_in_decimals: int, token_out: str, token_out_decimals: int, target_price_impact: float, rtol=5e-2):
    '''
    Returns the amount of token_in required to incur a price impact of {price_impact}.

    Ex: price_impact_size(weth, usdc, 0.10) returns the amount of WETH necessary to incur 10%
    price impact (+/- 0.01).
    '''
    def kyberswap_oracle(token_in: str, token_out: str, size: float, retries=3):
        response = get_swap_route("ethereum", token_in, token_out, token_in_decimals, size)
        route = response['data']['routeSummary']
        price_impact = 1 - float(route['amountOutUsd']) / float(route['amountInUsd'])
        return price_impact

    spot = CoinGecko().current_price(token_in, "ethereum")
    min_sz = 0
    max_sz = 100_000_000 / spot
    iters = 0
    price_impact = 1 # default start to run at least one iter

    st = time.time()
    while abs(1 - (price_impact/target_price_impact)) > rtol and iters < MAX_ITERS:
        _st = time.time()
        mid = (max_sz + min_sz) / 2.
        price_impact = kyberswap_oracle(token_in, token_out, mid)

        if price_impact < target_price_impact:
            min_sz = mid
        else:
            max_sz = mid

        # print(f"{iters:2d} | x = {mid:.2f} | price impact: {price_impact:.4f} | elapsed: {time.time() - st:.2f}s | per query: {time.time() - _st:.3f}s")
        # TODO: Figure out exact time to avoid rate limiting
        time.sleep(0.05)
        iters += 1

    return (max_sz + mid) / 2.

# TODO: Unify interface for cow/kyber
def price_impact_size_cowswap(token_in: str, token_in_decimals: int, token_out: str, token_out_decimals: int, target_price_impact: float, rtol=5e-2, max_sz_usd=500_000_000):
    cg = CoinGecko()
    spot_in = cg.current_price(token_in)
    spot_out = cg.current_price(token_out)

    def cowswap_oracle(token_in, token_out, size, retries=3):
        response = get_cowswap(token_in, token_out, token_in_decimals, size, quality="fast")
        amount_in_usd = float(response['quote']['sellAmount']) / (10 ** token_in_decimals) * spot_in
        amount_out_usd = float(response['quote']['buyAmount']) / (10 ** token_out_decimals) * spot_out
        price_impact = 1 - float(amount_out_usd / amount_in_usd)
        return price_impact

    coingecko = CoinGecko()
    spot_in = cg.current_price(token_in)
    spot_out = cg.current_price(token_out)
    min_sz = 0
    max_sz = max_sz_usd / spot_in # hundred mill as a loose upper bound seems okay?
    iters = 0
    price_impact = 1

    st = time.time()
    while abs(1 - (price_impact / target_price_impact)) > rtol and iters < MAX_ITERS:
        _st = time.time()
        mid = (max_sz + min_sz) / 2.
        price_impact = cowswap_oracle(token_in, token_out, mid)

        if price_impact < target_price_impact:
            min_sz = mid
        else:
            max_sz = mid

        print(f"{iters:2d} | x = {mid:.2f} | price impact: {price_impact:.4f} | elapsed: {time.time() - st:.2f}s | per query: {time.time() - _st:.3f}s")
        iters += 1
    return (max_sz + mid) / 2.




if __name__ == '__main__':
    # TODO: use the token mapping instead
    usdc = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    link = "0x514910771af9ca656af840dff83e8264ecf986ca"
    aave = "0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9"
    crv = "0xd533a949740bb3306d119cc777fa900ba034cd52"
    weth = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
    wsteth = "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0"
    wbtc = "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"
    decimals = {
        'usdc': 6,
        'wbtc': 8,
        'link': 18,
        'crv': 18,
        'aave': 18,
        'weth': 18,
        'wsteth': 18,
    }
    addr_to_sym = {
        usdc: "usdc", link: "link", aave: "aave", crv: "crv", weth: "weth", wbtc: "wbtc", wsteth: 'wsteth'
    }
    # for sym in [link, crv, aave, weth, wbtc]:
    for sym in [wsteth]:
        print('kyber')
        print(sym, price_impact_size(sym, decimals[addr_to_sym[sym]], usdc, decimals['usdc'], 0.02))
        print('cow')
        print(sym, price_impact_size_cowswap(sym, decimals[addr_to_sym[sym]], usdc, decimals['usdc'], 0.02))
        print('-' * 20)
