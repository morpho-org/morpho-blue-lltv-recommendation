import json
import time
from utils import price_impact_size_cowswap

from constants import SYMBOL_MAP
from cowswap import get_impact
from tokens import Tokens


def compute_impacts(impacts: list[float]) -> dict[str, dict[int, dict[float, float]]]:
    '''
    Compute the price impact of various swap sizes for each token in
    our token universe.

    Sample outputput for one token:
    {'aave': {0.005: 1052.97, 0.02: 8891.79, 0.25: 134780.90}
    '''
    impact_sizes = {}

    for tok in Tokens:
        impact_sizes[tok.symbol] = {}
        tgt = Tokens.USDT if tok == Tokens.USDC else Tokens.USDC

        for i in impacts:
            impact_sizes[tok.symbol][i] = price_impact_size_cowswap(
                tok.address, tok.decimals, tgt.address, tgt.decimals, i
            )

    return impact_sizes


if __name__ == "__main__":
    impacts = [0.005, 0.02, 0.25]
    price_impacts = compute_impacts(impacts)
    with open("../data/swap_sizes_small.json", "w") as json_file:
        json.dumps(price_impacts, json_file)
