import time
from typing import Any
from typing import Callable

import pandas as pd
import numpy as np

from kyberswap import get_swap_route, get_swap_route_usd
from coingecko import get_current_price


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
        return price_impact

    spot = get_current_price(token_in, "ethereum")
    min_sz = 0
    max_sz = 10_000_000 / spot
    iters = 0
    price_impact = 1 # default start to run at least one iter

    while abs(1 - (price_impact/target_price_impact)) > rtol and iters < MAX_ITERS:
        mid = (max_sz + min_sz) / 2.
        try:
            price_impact = kyberswap_oracle(token_in, token_out, mid)
        except:
            breakpoint

        if price_impact < target_price_impact:
            min_sz = mid
        else:
            max_sz = mid

        print(f"{iters:2d} | x = {mid:.2f} | price impact: {price_impact:.4f}")
        # TODO: Figure out exact time to avoid rate limiting
        time.sleep(0.05)
        iters += 1

    return (max_sz + mid) / 2.


if __name__ == '__main__':
    usdc = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    weth = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
    print(price_impact_size(weth, 18, usdc, 6, 0.02))

