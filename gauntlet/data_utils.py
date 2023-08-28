import json
import pickle
from itertools import product
from pathlib import Path
from typing import Any
from typing import List
from typing import Optional

import numpy as np
import pandas as pd

from .coingecko import CoinGecko
from .constants import DRAWDOWN_PKL_PATH
from .constants import PRICE_IMPACT_JSON_PATH
from .tokens import TokenInfo
from .tokens import Tokens
from .utils import price_impact_size_cowswap

CG = CoinGecko()


def get_prices(
    tokens: List[TokenInfo], start_date="2022-07-01", update_cache=False
) -> dict[TokenInfo, pd.DataFrame]:
    """
    Queries the CoinGecko api for the historical price data of the
    input tokens. If the `update_cache` flag is toggled on, this will also
    saves the resulting price DataFrames to csvs.
    """
    prices = {}
    for t in tokens:
        path = Path(__file__).parent.parent / f"prices/{t.symbol}.csv"
        df = CG.market_chart(t.address)
        df = df[start_date:]
        prices[t] = df

        if update_cache:
            df.to_csv(path)

    return prices


def calc_drawdown(window: pd.Series):
    return (max(window) - window[-1]) / max(window)


def compute_pairwise_drawdown(t1: TokenInfo, t2: TokenInfo) -> dict[Any]:
    p1 = CG.market_chart(t1.address)
    p2 = CG.market_chart(t1.address)
    n = min(len(p1), len(p2))
    df = p1[-n:] / p2[-n:1]
    drawdowns = get_drawdowns(df, [90, 95, 99], [2, 7, 14, 30])
    return drawdowns


def compute_pair_drawdown(
    t1: TokenInfo,
    t2: TokenInfo,
    hist_prices: Optional[dict[TokenInfo, pd.DataFrame]] = None,
    percentile_drawdowns: list[float] = [90, 95, 99],
    days: list[int] = [1, 7, 14, 30],
    start_date="2022-07-01",
) -> dict[dict[int, dict[int, float]]]:
    """
    Computes various percentile drawdowns over a time horizon of some number
    of days, as specified by the input drawdowns, days lists.

    df: pd.DataFrame, dataframe of prices of a given token
    percentile_drawdowns: list[int], percentile of drawdowns to compute
    days: list[int], time horizon to consider for the drawdowns (in days)
    """
    if hist_prices:
        t1_prices = hist_prices[t1]["prices"][start_date:]
        t2_prices = hist_prices[t2]["prices"][start_date:]
    else:
        t1_prices = CG.market_chart(t1)["prices"][start_date:]
        t2_prices = CG.market_chart(t2)["prices"][start_date:]

    n = min(len(t1_prices), len(t2_prices))
    ratio = (t1_prices[-n:] / t2_prices[-n:]).dropna()

    dds = {
        d: {
            p: np.percentile(ratio.rolling(d + 1).apply(calc_drawdown)[d:], p)
            for p in percentile_drawdowns
        }
        for d in days
    }
    return dds


def get_drawdowns(
    tokens: List[TokenInfo], update_cache: bool = False, use_cache: bool = False
) -> dict[TokenInfo, dict[int, dict[float, float]]]:
    """
    tokens: list of Tokens or TokenData instances
    update_cache: bool, if true, this function will update the cached drawdown
        file with the new drawdown numbers.

    Computes historical drawdown numbers between all pairs of tokens within the
    input tokens list.
    """
    dd_dict = {}

    # Load cache if use_cache is True
    if use_cache:
        with open(DRAWDOWN_PKL_PATH, "rb") as f:
            dd_dict = pickle.load(f)

    # If update_cache is True or tokens are missing from cache, calculate drawdowns
    if update_cache or any(
        (t1.symbol, t2.symbol) not in dd_dict
        for (t1, t2) in product(tokens, repeat=2)
        if t1 != t2
    ):
        hist_prices = {t: CG.market_chart(t.address) for t in tokens}
        dd_dict.update(
            {
                (t1.symbol, t2.symbol): compute_pair_drawdown(t1, t2, hist_prices)
                for (t1, t2) in product(tokens, repeat=2)
                if t1 != t2
            }
        )

        if update_cache:
            with open(DRAWDOWN_PKL_PATH, "rb") as f:
                orig_dds = pickle.load(f)

            orig_dds.update(dd_dict)

            # Write the updated data directly back to the file
            with open(DRAWDOWN_PKL_PATH, "wb") as f:
                pickle.dump(dd_dict, f)

    return dd_dict


def get_price_impacts(
    tokens: List[TokenInfo],
    impacts: list[float] = [0.005, 0.25],
    update_cache: bool = False,
    use_cache: bool = False,
) -> dict[TokenInfo, dict[float, float]]:
    impact_sizes = {}

    if use_cache:
        with open(PRICE_IMPACT_JSON_PATH, "r") as json_file:
            impact_sizes = json.load(json_file)

    # If update_cache is True or tokens are missing, calculate impacts
    if update_cache or any(tok.symbol not in impact_sizes for tok in tokens):
        for tok in tokens:
            impact_sizes[tok.symbol] = {}
            tgt = Tokens.USDT if tok == Tokens.USDC else Tokens.USDC

            for i in impacts:
                impact_sizes[tok.symbol][str(i)] = price_impact_size_cowswap(
                    tok.address, tok.decimals, tgt.address, tgt.decimals, i
                )

        if update_cache:
            # Write the updated data directly back to the file
            with open(PRICE_IMPACT_JSON_PATH, "r") as json_file:
                orig_impacts = json.load(json_file)

            orig_impacts.update(impact_sizes)
            with open(PRICE_IMPACT_JSON_PATH, "w") as json_file:
                json.dump(orig_impacts, json_file, indent=4)

    return impact_sizes
