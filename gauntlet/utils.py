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


def price_impact_size(token_in: str, token_in_decimals: int, token_out: str, token_out_decimals: int, target_price_impact: float, rtol=1e-1):
    '''
    Returns the amount of token_in required to incur a price impact of {price_impact}.

    Ex: price_impact_size(weth, usdc, 0.10) returns the amount of WETH necessary to incur 10%
    price impact (+/- 0.01).
    '''
    def kyberswap_oracle(token_in: str, token_out: str, size: float, retries=3):
        response = get_swap_route("ethereum", token_in, token_out, token_in_decimals, size)
        route = response['data']['routeSummary']
        price_impact = 1 - float(route['amountOutUsd']) / float(route['amountInUsd'])
        breakpoint()
        return price_impact

    spot = CoinGecko().current_price(token_in, "ethereum")
    print("Spot price: {}".format(spot))
    min_sz = 0
    max_sz = 1_000_000 / spot
    iters = 0
    price_impact = 1 # default start to run at least one iter

    while abs(1 - (price_impact/target_price_impact)) > rtol and iters < MAX_ITERS:
        mid = (max_sz + min_sz) / 2.
        price_impact = kyberswap_oracle(token_in, token_out, mid)

        if price_impact < target_price_impact:
            min_sz = mid
        else:
            max_sz = mid

        print(f"{iters:2d} | x = {mid:.2f} | price impact: {price_impact:.4f}")
        # TODO: Figure out exact time to avoid rate limiting
        time.sleep(0.05)
        iters += 1

    return (max_sz + mid) / 2.

# TODO: Unify interface for cow/kyber
def price_impact_size_cowswap(token_in: str, token_in_decimals: int, token_out: str, token_out_decimals: int, target_price_impact: float, rtol=1e-1):
    cg = CoinGecko()
    spot_in = cg.current_price(token_in)
    spot_out = cg.current_price(token_out)

    def cowswap_oracle(token_in, token_out, size, retries=3):
        response = get_cowswap(token_in, token_out, token_in_decimals, size, quality="optimal")
        amount_in_usd = float(response['quote']['buyAmount']) * spot_in / (10 ** token_in_decimals)
        amount_out_usd = float(response['quote']['sellAmount']) * spot_out / (10 ** token_out_decimals)
        breakpoint()
        price_impact = 1 - float(amount_out_usd / amount_in_usd)
        return price_impact

    coingecko = CoinGecko()
    spot_in = cg.current_price(token_in)
    spot_out = cg.current_price(token_out)
    print("spot in {} | spot out: {}".format(spot_in, spot_out))
    min_sz = 0
    max_sz = 1_00_000_000 / spot_in # hundred mill as a loose upper bound seems okay?
    iters = 0
    price_impact = 1

    st = time.time()
    while abs(1 - (price_impact / target_price_impact)) > rtol and iters < MAX_ITERS:
        mid = (max_sz + min_sz) / 2.
        price_impact = cowswap_oracle(token_in, token_out, mid)

        if price_impact < target_price_impact:
            min_sz = mid
        else:
            max_sz = mid

        print(f"{iters:2d} | x = {mid:.2f} | price impact: {price_impact:.4f}")
        # TODO: Figure out exact time to avoid rate limiting
        time.sleep(0.05)
        iters += 1
    print("Total time: {:.2f}s".format(time.time()))
    return (max_sz + mid) / 2.




if __name__ == '__main__':
    usdc = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    link = "0x514910771af9ca656af840dff83e8264ecf986ca"
    aave = "0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9"
    crv = "0xd533a949740bb3306d119cc777fa900ba034cd52"
    weth = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
    wbtc = "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"
    for sym in [aave]:
        print(sym, price_impact_size(sym, 18, usdc, 6, 0.02))
    # print('--')
    # print(price_impact_size(crv, 18, usdc, 6, 0.02))
    # print(price_impact_size_cowswap(crv, 18, usdc, 6, 0.02))
