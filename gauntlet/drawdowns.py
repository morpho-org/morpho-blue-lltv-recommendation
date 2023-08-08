from typing import Tuple
import pickle

import numpy as np
import pandas as pd
from coingecko import CoinGecko
from constants import SYMBOL_MAP


def load_ohlcs() -> dict[str, pd.DataFrame]:
    """
    Loads the cached OHLC data.
    The OHLC csvs are assumed to be in:
    "morpho/ohlc/{token symbol}.csv"
    """
    ohlcs = {}
    for sym in SYMBOL_MAP:
        ohlcs[sym] = pd.read_csv(f"../ohlc/{sym}.csv")
    return ohlcs


def save_prices(start_date="2022-07-01"):
    """
    Queries CoinGecko api for the historical price data of all
    tokens in SYMBOL_MAP and saves the resulting price dataframes
    to csvs.
    """
    cg = CoinGecko()
    prices = {}
    for sym, tok in SYMBOL_MAP.items():
        df = cg.market_chart(tok.address)
        df = df[start_date:]
        df.to_csv(f"../prices/{sym}.csv")
        prices[sym] = df

    return prices


def load_prices() -> dict[str, pd.DataFrame]:
    """
    Loads the cached price data for all symbols/tokens.
    This assumes that the token price data is saved in the
    following format:
    "morpho/prices/{token_symbol}.csv"
    """
    prices = {}

    for sym in SYMBOL_MAP.keys():
        prices[sym] = pd.read_csv(f"../prices/{sym}.csv")
        prices[sym].set_index("date", inplace=True)
        prices[sym] = prices[sym]["prices"]["2022-07-01":]

    return prices


def calc_drawdown(window):
    return (max(window) - window[-1]) / max(window)


def get_drawdowns(
    df: pd.DataFrame,
    drawdowns: list[int] = [90, 95, 99, 99.9],
    days: list[int] = [2, 7, 14, 30],
) -> dict[dict[]]:
    '''
    Computes various percentile drawdowns over a time horizon of some number
    of days, as specified by the input drawdowns, days lists.

    df: pd.DataFrame, dataframe of prices of a given token
    drawdowns: list[int], percentile of drawdowns to compute
    days: list[int], time horizon to consider for the drawdowns (in days)
    '''
    vals = {
        d: {
            p: np.percentile(df.rolling(d).apply(calc_drawdown)[d - 1 :], p)
            for p in drawdowns
        }
        for d in days
    }
    return vals


def compute_pairwise_window_drawdowns() -> dict[Any]:
    '''
    Computes drawdowns over ratios of prices of tokens. Token price
    data is loaded from the stored cache to be able to compute
    these drawdowns. 
    '''
    prices = load_prices()
    drawdowns = {}

    for x, t1 in SYMBOL_MAP.items():
        for y, t2 in SYMBOL_MAP.items():
            if x == y:
                continue

            n = min(len(prices[x]), len(prices[y]))
            df = prices[x][-n:] / prices[y][-n:]
            drawdowns[(x, y)] = get_drawdowns(df, [90, 95, 99, 99.9], [2, 7, 14, 30])
        log.info("Done with", y)

    return drawdowns


def get_price_ratios() -> dict[Tuple[str, str], pd.DataFrame]:
    '''
    Returns a dict of tuple of token symbols (str) to a dataframe of
    the ratio of the two tokens' prices.
    '''
    prices = load_prices()
    ratios = {}

    for a in SYMBOL_MAP:
        for b in SYMBOL_MAP:
            if a == b:
                continue

            ratios[(a, b)] = prices[a] / prices[b]
    return ratios


if __name__ == "__main__":
    start_date = "2022-07-01"
    save_prices(start_date)
    ps = compute_pairwise_window_drawdowns()
    pickle.dump(ps, open("../data/pairwise_drawdowns.pkl", "wb"))
