import json
import pickle
from itertools import product
from pathlib import Path
from typing import List
from typing import Optional

import numpy as np
import pandas as pd

from .coingecko import CoinGecko
from .constants import DRAWDOWN_PKL_PATH
from .constants import PRICE_IMPACT_JSON_PATH
from .logger import get_logger
from .price_impact import price_impact_size
from .tokens import Token
from .tokens import Tokens

log = get_logger(__name__)
CG = CoinGecko()


def get_prices(
    tokens: List[Token], start_date="2022-07-01", update_cache=False
) -> dict[Token, pd.DataFrame]:
    """
    Queries the CoinGecko api for the historical price data of the
    input tokens. If the `update_cache` flag is toggled on, this will also
    saves the resulting price DataFrames to csvs.

    Returns: a dict mapping Token objects to dataframes of its historical
        daily prices, starting from the input start_date
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


def calc_drawdown(window: pd.Series) -> float:
    """
    Computes the max drawdown (largest value vs the final value)
    of a time series.
    This is generally to be used via:
        pd.DataFrame.rolling(window_size).apply(calc_drawdown)
    """
    return (max(window) - window[-1]) / max(window)


def compute_pair_drawdown(
    t1: Token,
    t2: Token,
    hist_prices: Optional[dict[Token, pd.DataFrame]] = None,
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
    if hist_prices and t1 in hist_prices and t2 in hist_prices:
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
    tokens: List[Token], update_cache: bool = False, use_cache: bool = False
) -> dict[Token, dict[int, dict[float, float]]]:
    """
    tokens: list of tokens
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

    # If update_cache or tokens are missing from cache, calculate drawdowns
    if update_cache or any(
        (t1.symbol, t2.symbol) not in dd_dict
        for (t1, t2) in product(tokens, repeat=2)
        if t1 != t2
    ):
        hist_prices = {t: CG.market_chart(t.address) for t in tokens}
        dd_dict.update(
            {
                (t1.symbol, t2.symbol): compute_pair_drawdown(
                    t1, t2, hist_prices
                )
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
    tokens: List[Token],
    impacts: list[float] = [0.005, 0.25],
    update_cache: bool = False,
    use_cache: bool = False,
) -> dict[Token, dict[float, float]]:
    """
    Computes the swap sizes necessary to incur the given price impacts
    from the input impacts list.

    tokens: list of Tokens to compute price impacts for
    impacts: list of floats of price impacts that we want to compute
        the corresponding price swaps for
    update_cache: bool, whether or not to update the price impact cache file
    use_cache: bool, whether or not to just return the cache of impact sizes

    Returns: dict mapping Tokens to a dict of
        price impact -> size of swap necessary to incur the given price impact

    Example return:
    {
        tokenA: {0.005: 1000, 0.25: 100000}
        tokenB: {0.005: 300, 0.25: 50000}
    }
    This return indicates that swapping 1000 tokens of tokenA for USDC will
    incur 0.5% slippage.
    """
    impact_sizes = {}

    if use_cache:
        with open(PRICE_IMPACT_JSON_PATH, "r") as json_file:
            impact_sizes = json.load(json_file)

    # If update_cache or tokens are missing, calculate impacts
    if update_cache or any(tok.symbol not in impact_sizes for tok in tokens):
        log.info("Computing price impacts. This may take 1-2 minutes.")
        for tok in tokens:
            impact_sizes[tok.symbol] = {}
            tgt = Tokens.USDT if tok == Tokens.USDC else Tokens.USDC

            for i in impacts:
                impact_sizes[tok.symbol][str(i)] = price_impact_size(
                    tok, tgt, i
                )

        log.info("Finished computing price impacts.")

        if update_cache:
            # Write the updated data directly back to the file
            with open(PRICE_IMPACT_JSON_PATH, "r") as json_file:
                orig_impacts = json.load(json_file)

            orig_impacts.update(impact_sizes)
            with open(PRICE_IMPACT_JSON_PATH, "w") as json_file:
                json.dump(orig_impacts, json_file, indent=4)

    return impact_sizes
