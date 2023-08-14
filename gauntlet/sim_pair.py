import argparse
import json
import pickle
from typing import Tuple
from utils import compute_liquidation_incentive
from utils import current_price

import logger
import numpy as np
from coingecko import CoinGecko

from constants import STABLECOINS
from constants import SYMBOL_MAP
from sim import get_init_collateral_usd
from sim import heuristic_drawdown
from sim import simulate_insolvency
from tokens import Tokens

log = logger.get_logger(__name__)


def main(args: argparse.Namespace):
    """
    This main function will compute the optimal LTVs (highest LTV) with 0
    insolvencies for all token pair markets.
    The resulting dict of LTV results (pair of tokens -> LTV value) will
    be saved in the save path specified by the input args.
    """
    lltvs = np.arange(0.01, 1.0, 0.01)
    stable_lltvs = np.arange(0.9, 1, 0.01)
    tokens = [SYMBOL_MAP[args.collateral], SYMBOL_MAP[args.borrow]]
    opt_lltv = None
    opt_li = None

    cg = CoinGecko()
    prices = {t: cg.current_price(t.address) for t in tokens}
    # Price impact swap sizes
    impacts = json.load(open("../data/swap_sizes.json", "r"))
    # Historical drawdowns between the ratio two tokens
    drawdowns = pickle.load(open("../data/pairwise_drawdowns.pkl", "rb"))
    # Repay amount is set to be the swap size that incurs 50bps price impact
    repay_amnts = {t: impacts[t.symbol]["0.005"] * prices[t] for t in tokens}

    collateral_token = SYMBOL_MAP.get(args.collateral)
    debt_token = SYMBOL_MAP.get(args.borrow)
    if (collateral_token in Tokens) and (debt_token in Tokens):
        repay_amount_usd = min(repay_amnts[collateral_token], repay_amnts[debt_token])
        max_drawdown = heuristic_drawdown(collateral_token, debt_token, drawdowns)
        init_collateral_usd = get_init_collateral_usd(collateral_token, debt_token)
    else:
        log.debug(
            "Input tokens were not given or are not part of"
            + " the token universe in constants.py."
            + " Using command line parameterization instead."
        )
    _lltvs = (
        stable_lltvs  # stablecoins do not need to search the entire range
        if (collateral_token in STABLECOINS and debt_token in STABLECOINS)
        else lltvs
    )
    log.info(
        f"{collateral_token} / {debt_token} | repay amount: {repay_amount_usd:.2f}"
        + f" | drawdown: {max_drawdown:.3f} | init collat usd: {init_collateral_usd}"
        + f" | p1 = {prices[collateral_token]:.2f}, p2 = {prices[debt_token]:.2f}"
    )

    for ltv in _lltvs:
        liq_bonus = max(
            compute_liquidation_incentive(args.m, args.beta, ltv), args.min_liq_bonus
        )
        insolvency = simulate_insolvency(
            initial_collateral_usd=args.initial_collateral_usd or init_collateral_usd,
            collateral_price=prices.get(collateral_token) or args.collateral_price,
            debt_price=prices.get(debt_token) or args.debt_price,
            ltv=ltv,
            repay_amount_usd=args.repay_amount_usd or repay_amount_usd,
            liq_bonus=liq_bonus,
            max_drawdown=args.max_drawdown or max_drawdown,
            pct_decrease=args.pct_decrease,
        )

        # Note: for the purpose of this tool, we are just interested in the largest
        # LLTV that results in 0 insolvent debt.
        if insolvency > 0:
            break

        opt_lltv = ltv
        opt_li = liq_bonus

    if opt_lltv is None:
        raise ValueError(
            "Did not observe an optimal LLTV for "
            + f"{collateral_token.symbol} / {debt_token.symbol}"
        )

    log.info(
        f"Collat: {collateral_token} | Debt: {debt_token}"
        + f" | LI: {opt_li:.3f} | LLTV: {opt_lltv:.3f}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-b", "--borrow", type=str)  # borrow
    parser.add_argument("-c", "--collateral", type=str)  # collateral
    parser.add_argument(
        "--pct_decrease",
        type=float,
        default=0.005,
        help="Per iter percent drop of the collateral price to debt price",
    )
    parser.add_argument(
        "--initial_collateral_usd",
        type=int,
        default=None,
    )
    parser.add_argument("--collateral_price", type=float, default=None)
    parser.add_argument("--debt_price", type=float, default=None)
    parser.add_argument("--repay_amount_usd", type=float, default=None)
    parser.add_argument("--max_drawdown", type=float, default=None)
    parser.add_argument("--m", type=float, default=0.15)
    parser.add_argument("--beta", type=float, default=0.4)
    parser.add_argument(
        "--min_liq_bonus", type=float, default=0.01, help="Liquidation bonus minimum"
    )
    args = parser.parse_args()
    main(args)
