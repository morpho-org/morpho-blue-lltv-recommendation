import json
import time
import pickle
from cowswap import get_impact
from utils import price_impact_size_cowswap
from constants import TOKENS, STABLES, SYMBOL_MAP

def compute_impacts():
    impact_sizes = {}
    max_sz_usds = {
        0.005: 10_000_0000,
        0.02: 100_000_0000,
        0.10: 200_000_0000,
        0.25: 200_000_0000,
    }
    impacts = [0.005, 0.02, 0.1, 0.25]
    usdc = SYMBOL_MAP['usdc']

    st = time.time()
    for tok in TOKENS:
        impact_sizes[tok.symbol] = {}
        if tok in STABLES:
            continue

        for i in impacts:
            impact_sizes[tok.symbol][i] = price_impact_size_cowswap(tok.address, tok.decimals, usdc.address, usdc.decimals, i)
        print("Done with {} | {} | Elapsed: {:.2f}min".format(tok.symbol, i , (time.time() - st)/60 ))
        print('-' * 40)

    # now save it somewhere
    with open("../data/swap_sizes.pkl", "wb") as f:
        pickle.dump(impact_sizes, f)

def load_impacts():
    with open("../data/swap_sizes.pkl", "rb") as f:
        return pickle.load(f)

def sanity_check():
    impacts = load_impacts()
    usdc = SYMBOL_MAP['usdc']

    for sym, vals in impacts.items():
        for p, num  in vals.items():
            tok = SYMBOL_MAP[sym]
            # do the swap of the given size, see the impact
            impact = get_impact(tok.address, usdc.address, tok.decimals, usdc.decimals, num, quality='fast')
            deviation = abs(p - impact) / p
            abs_dev = abs(p - impact)
            print("{:6s} | expected impact: {:.3f} | computed impact: {:.3f} | deviation: {:.4f} | abs dev: {:.4f}".format(tok.symbol, p, impact, deviation, abs_dev))

if __name__ == '__main__':
    compute_impacts()
    data = load_impacts()
    datajs = json.dumps(data)

    with open('../data/swap_sizes.json', 'w') as json_file:
        json.dumps(datajs, json_file)
