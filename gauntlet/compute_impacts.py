import json
import time
from utils import price_impact_size_cowswap

from constants import SYMBOL_MAP
from cowswap import get_impact
from logger import get_logger
from tokens import Tokens

log = get_logger(__name__)


def compute_impacts(impacts: list[float]) -> dict[str, dict[int, dict[float, float]]]:
    """
    Compute the price impact of various swap sizes for each token in
    our token universe.

    Sample outputput for one token:
    {'aave': {0.005: 1052.97, 0.25: 134780.90}
    """
    impact_sizes = {}
    log.info("Starting to compute price impacts ...")
    for tok in Tokens:
        impact_sizes[tok.symbol] = {}
        tgt = Tokens.USDT if tok == Tokens.USDC else Tokens.USDC

        for i in impacts:
            impact_sizes[tok.symbol][i] = price_impact_size_cowswap(
                tok.address, tok.decimals, tgt.address, tgt.decimals, i
            )
        log.info(f"{tok.symbol:6s} done")
    return impact_sizes


if __name__ == "__main__":
    impacts = [0.005, 0.25]
    price_impacts = compute_impacts(impacts)
    with open("../data/swap_sizes.json", "w") as json_file:
        json.dump(price_impacts, json_file)
