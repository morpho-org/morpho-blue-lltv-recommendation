import pickle
import time
import numpy as np
import pandas as pd
from constants import SYMBOL_MAP
from coingecko import CoinGecko

def load_ohlcs():
    ohlcs = {}
    for sym in SYMBOL_MAP.keys():
        ohlcs[sym] = pd.read_csv(f"../ohlc/{sym}.csv")
    return ohlcs

def save_prices(start_date="2022-07-01"):
    cg = CoinGecko()
    prices = {}
    for sym, tok in SYMBOL_MAP.items():
        df = cg.market_chart(tok.address)
        df = df[start_date:]
        df.to_csv(f"../prices/{sym}.csv")
        prices[sym] = df

    return prices

def load_prices():
    prices = {}

    for sym in SYMBOL_MAP.keys():
        prices[sym] = pd.read_csv(f"../prices/{sym}.csv")
        prices[sym].set_index("date", inplace=True)
        prices[sym] = prices[sym]['prices']["2022-07-01":]

    return prices

def calc_drawdown(window):
    return (max(window) - window[-1]) / max(window)

def get_drawdowns(df, drawdowns=[90, 95, 99, 99.9], days=[2, 7, 14, 30]):
    vals = {
        d: {
            p: np.percentile(df.rolling(d).apply(calc_drawdown)[d-1:], p)
            for p in drawdowns
        }
        for  d in days
    }
    return vals

def compute_window_drawdowns():
    '''
    Output is a dict:
    - output[symbol][num drawdown window][percentile]
    Ex: output['weth'][7][90]
    '''
    prices = load_prices()
    drawdowns = {}

    for sym, tok in SYMBOL_MAP.items():
        df = prices[sym]
        drawdowns[sym] =  get_drawdowns(df, [90, 95, 99, 99.9], [2, 7, 14, 30])

    return drawdowns

def compute_pairwise_window_drawdowns():
    prices = load_prices()
    drawdowns = {}

    for x, t1 in SYMBOL_MAP.items():
        for y, t2 in SYMBOL_MAP.items():
            if x == y:
                continue

            n = min(len(prices[x]), len(prices[y]))
            df = prices[x][-n:] / prices[y][-n:]
            drawdowns[(x, y)] =  get_drawdowns(df, [90, 95, 99, 99.9], [2, 7, 14, 30])

    return drawdowns


def compute_drawdowns():
    prices = load_prices()
    ohlcs = load_ohlcs()
    drawdowns = {
        sym: (o['high'] - o['low']) / o['open'] for sym, o in ohlcs.items()
    }

    drawdown_pctiles = {
        sym: np.percentile(drawdowns[sym], [90, 95, 99])
        for sym in SYMBOL_MAP
    }
    drawdowns_99 = {sym: x[2] for sym, x in drawdown_pctiles.items()}
    drawdowns_95 = {sym: x[1] for sym, x in drawdown_pctiles.items()}
    drawdowns_90 = {sym: x[0] for sym, x in drawdown_pctiles.items()}

    # TODO: this is gross
    drawdowns = {
        sym: {90: drawdowns_90[sym], 95: drawdowns_95[sym], 99: drawdowns_99[sym]}
        for sym in SYMBOL_MAP
    }
    return drawdowns

def get_price_ratios():
    prices = load_prices()
    ratios = {}

    for a in SYMBOL_MAP:
        for b in SYMBOL_MAP:
            if a == b:
                continue

            ratios[(a, b)] = prices[a] / prices[b]
    return ratios


if __name__ == '__main__':
    save_prices()
    st = time.time()
    dd = compute_window_drawdowns()
    pickle.dump(dd, open("../data/drawdowns.pkl", "wb"))
    end = time.time()
    print("Elapsed: {:.2f}s".format(end - st))

    st = time.time()
    ps = compute_pairwise_window_drawdowns()
    pickle.dump(ps, open("../data/pairwise_drawdowns.pkl", "wb"))
    end = time.time()
    print("Pairwise Elapsed: {:.2f}s".format(end - st))
