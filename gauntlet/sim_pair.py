import argparse
import json
import os
import pickle
from functools import lru_cache
from typing import Tuple
from utils import compute_liquidation_incentive
from utils import current_price

import logger
import numpy as np
import plotext as plt
from coingecko import CoinGecko
from constants import STABLECOINS
from constants import SYMBOL_MAP
from tokens import Tokens

log = logger.get_logger(__name__)
TOL = 1e-4

# TODO: This set of assets can be basically be parameterized by price impact
# Ex: "Set of tokens that require incur less than 10% price impact on a $10mill swap"
# Potentially add more logic to exclude stablecoins
IMPACTS = json.load(open("../data/swap_sizes.json", "r"))
# T1 = LARGE_CAPS = {
#     t
#     for t in Tokens
#     if IMPACTS[t.symbol]["0.25"] * current_price(t.address) > 20_000_000
#     and t not in STABLECOINS
# }
T1 = LARGE_CAPS = {Tokens.WETH, Tokens.WSTETH, Tokens.RETH, Tokens.WBTC}
BLUE_CHIPS = LARGE_CAPS.union(set(STABLECOINS))
T2 = SMALL_CAPS = {t for t in Tokens if t not in STABLECOINS and t not in LARGE_CAPS}


# TODO: Abstract
def get_init_collateral_usd(tok: Tokens, tok2: Tokens) -> float:
    """
    The sim initializes one collateral position that maxes out its
    borrow power. The size of this collateral position is effectively
    a function of 25% price impact with clamping to a reasonable closest
    10mil/100mil figure..

    These numbers are subject to change but at the moment they give us reasonable results.
    """
    if tok in T1 and tok2 in T1:
        return max(200_000_000, IMPACTS[tok.symbol]["0.25"])
    elif (tok in BLUE_CHIPS and tok2 in T2) or (tok in T2 and tok2 in BLUE_CHIPS):
        return max(50_000_000, IMPACTS[tok.symbol]["0.25"])
    elif tok in T2 or tok2 in T2:
        return max(
            20_000_000, IMPACTS[tok.symbol]["0.25"], IMPACTS[tok2.symbol]["0.25"]
        )
    elif tok in STABLECOINS:  # collat stable
        return IMPACTS[tok.symbol]["0.25"]
    elif tok2 in STABLECOINS:
        return IMPACTS[tok.symbol]["0.25"]
    else:
        log.error(f"Init collateral for {tok.symbol} doesnt match existing cases")
        raise ValueError


# TODO: Abstract
def heuristic_drawdown(
    t1: Tokens, t2: Tokens, drawdowns: dict[Tuple[str, str], float]
) -> float:
    """
    t1: Token, the collateral asset of a market
    t2: Token, the borrowable asset of a market
    drawdowns: dict, dict of the collateral/borrow Tokens pair mapped to
        the time horizon max drawdowns of their price ratio.
    """
    # drawdown is a dict: symbol pair -> dict of time duration -> {percentile -> value}
    # 30 day 99th percentile drawdown in ratio change of t1/t2
    hist_dd = drawdowns[(t1.symbol, t2.symbol)][30][99]

    # Handle super low drawdown cases for LSTs, stablecoin depeg
    # TODO: better parameterize these heuristic consts
    if hist_dd < 0.1:
        return max(hist_dd, 0.02)

    if t1 in LARGE_CAPS and t2 in LARGE_CAPS:
        dd = 0.25
    elif t1 in SMALL_CAPS and t2 in SMALL_CAPS:
        dd = 0.5
    else:
        dd = 0.35

    return max(dd, hist_dd)


def simulate_insolvency(
    *,
    initial_collateral_usd: float,
    collateral_price: float,
    debt_price: float,
    ltv: float,
    repay_amount_usd: float,
    liq_bonus: float,
    max_drawdown: float,
    pct_decrease: float,
    iters: int,
) -> float:
    """
    To simulate the potential insolvencies, we do the following
    - initialize a whale collateral/borrow position, as determined by the
        `get_initial_collateral_usd` function. The borrow position is determined by
        the input `ltv` parameter - we assume that this position maxes out its allowed
        borrower power.
    - Simulate some fixed number of time steps. At each time step, we:
        - decrement the value of the collateral (effectively the same as decreasing the price
          of the collateral asset, or decreasing the ratio of the prices of the collateral
          and borrowable asset)
        - repay some debt + claim some amount of collateral if the borrow position is
          liquidateable
    The simulation ends when there is no more collateral, no more debt.
    The function returns the amount of insolvent debt that results from the simulation.

    Parameters:
    - initial_collateral_usd: float, value of the whale collateral position
    - collateral_price: float, initial price of the collateral asset
    - debt_price: float, initial price of the debt asset
    - ltv: float, loan to value parameter (technically this is the borrow power being used)
    - repay_amount_usd: float, amount of USD being repaid at each timestep if the account
        is liquidateable
    - liq_bonus: float, liquidation bonus
    - max_drawdown: float, largest collateral value decrease allowed during the simulation
    - pct_decrease: float, proportion to scale the collateral value by at each timestep
        pct_decrease \in [0, 1] so the collateral value always decreases.
    """
    # ltv * (1 + liq_bonus) represents the value at which insolvencies can start to happen.
    # If the maximum drawdown doesnt reach this point, we will not observe any insolvent debt
    # so skip the computation.
    if ltv * (1 + liq_bonus) < (1 - max_drawdown):
        return 0

    collateral_tokens = initial_collateral_usd / collateral_price
    net_collateral_usd = collateral_tokens * collateral_price

    debt_usd = initial_collateral_usd * ltv
    debt_tokens = debt_usd / debt_price
    net_debt_usd = debt_tokens * debt_price
    min_collateral_price = collateral_price * (1 - max_drawdown)
    insolvency = 0
    max_iters = int(np.ceil((initial_collateral_usd / repay_amount_usd) + 1))

    assert abs(initial_collateral_usd - net_collateral_usd) < TOL
    assert abs(debt_usd - net_debt_usd) < TOL
    collats = [net_collateral_usd]
    debts = [net_debt_usd]
    for i in range(max_iters):
        """
        To be precise, what we really do in the methodology is decrease the
        ratio of the collateral token's price to debt token's price
        at each step. In practice, it is easier to pretend that only
        the collateral token's price changes.
        The ratio of the collateral value to the debt value ends up being the
        same under both calculations, which is what ultimately is compared against
        ltv to determine liquidation eligibility, so this is fine.
        """
        # TODO: Abstract state update
        collateral_price = max(
            min_collateral_price, collateral_price * (1 - pct_decrease)
        )
        net_collateral_usd = collateral_tokens * collateral_price
        debt_to_collat = net_debt_usd / net_collateral_usd

        if i % 100 == 0:
            log.debug(
                f"{i=} | {debt_to_collat=:.3f} | {net_collateral_usd=} | {net_debt_usd=} | {ltv=}"
            )

        if debt_to_collat >= ltv:
            # Figure out the most collateral a liquidator can claim
            # then back out the necessary debt they must repay to claim that
            # amount of collateral.
            collateral_claimed_usd = min(
                min(net_debt_usd, repay_amount_usd) * (1 + liq_bonus),
                net_collateral_usd,
            )
            collateral_tokens_claimed = collateral_claimed_usd / collateral_price
            collateral_tokens -= collateral_tokens_claimed
            assert (
                (net_collateral_usd - collateral_claimed_usd)
                - (collateral_tokens * collateral_price)
            ) < TOL

            net_collateral_usd -= collateral_claimed_usd
            net_debt_usd -= collateral_claimed_usd / (1 + liq_bonus)
        collats.append(net_collateral_usd)
        debts.append(net_debt_usd)

        if net_collateral_usd < TOL:
            insolvency = net_debt_usd
            log.info(
                f"Initial collateral: {initial_collateral_usd:.2f} | Repay usd: {repay_amount_usd:.2f} | Max drawdown: {max_drawdown:.2f}"
            )
            return insolvency

        if net_debt_usd < TOL:
            insolvency = 0
            return insolvency

    assert (
        net_debt_usd / net_collateral_usd
    ) < ltv, "Simulation finished with d2c > ltv: {net_debt_usd/net_collateral_usd:.3f}, {ltv=}"
    return 0


def main(args: argparse.Namespace):
    """
    This main function will compute the optimal LTVs (highest LTV) with 0
    insolvencies for all token pair markets.
    The resulting dict of LTV results (pair of tokens -> LTV value) will
    be saved in the save path specified by the input args.
    """
    lltvs = [0.01 * x for x in range(40, 100)]
    stable_lltvs = [0.005 * x for x in range(90 * 2, int(99.5 * 2))]
    opt_ltvs = {}
    insolvencies = []

    tokens = [SYMBOL_MAP[args.collateral], SYMBOL_MAP[args.borrow]]
    # tokens = [t for t in Tokens]
    # tokens = [Tokens.WETH, Tokens.WBTC]
    # tokens = [t for t in Tokens]

    cg = CoinGecko()
    prices = {t: cg.current_price(t.address) for t in tokens}
    # prices = {t: current_price(t.address) for t in tokens}
    # Price impact swap sizes
    impacts = json.load(open("../data/swap_sizes.json", "r"))
    # Historical drawdowns between the ratio two tokens
    drawdowns = pickle.load(open("../data/pairwise_drawdowns.pkl", "rb"))
    # Repay amount is set to be the swap size that incurs 50bps price impact
    repay_amnts = {t: impacts[t.symbol]["0.005"] * prices[t] for t in tokens}

    tok1 = SYMBOL_MAP[args.collateral]
    tok2 = SYMBOL_MAP[args.borrow]
    _lltvs = stable_lltvs if (tok1 in STABLECOINS and tok2 in STABLECOINS) else lltvs
    # s1, s2 = tok1.symbol, tok2.symbol
    repay_amount_usd = min(repay_amnts[tok1], repay_amnts[tok2])
    max_dd = heuristic_drawdown(tok1, tok2, drawdowns)
    init_cusd = get_init_collateral_usd(tok1, tok2)
    log.debug(
        f"{tok1} / {tok2} | repay amount: {repay_amount_usd:.2f}"
        + f" | drawdown: {max_dd:.3f} | init collat usd: {init_cusd}"
        + f" | p1 = {prices[tok1]:.2f}, p2 = {prices[tok2]:.2f}"
    )
    prev_ltv = _lltvs[0] - 0.005

    for ltv in _lltvs:
        liq_bonus = max(
            compute_liquidation_incentive(args.m, args.beta, ltv), args.liq_bonus
        )
        log.debug(f"M = {args.m:.2f}, beta = {args.beta:.2f}, LI = {liq_bonus:.3f}")
        insolvency = simulate_insolvency(
            initial_collateral_usd=args.initial_collateral_usd or init_cusd,
            collateral_price=args.collateral_price or prices[tok1],
            debt_price=args.debt_price or prices[tok2],
            ltv=args.ltv or ltv,
            repay_amount_usd=args.repay_amount_usd or repay_amount_usd,
            liq_bonus=args.liq_bonus or liq_bonus,
            max_drawdown=args.max_drawdown or max_dd,
            pct_decrease=args.pct_decrease,
            iters=args.iters,
        )

        # Note: we do not actually care about the size of the insolvency.
        # For the purpose of the risk assessment, we are most interested in the lowest
        # LTV that does not realize insolvencies.
        if insolvency > TOL and opt_ltvs.get((tok1.symbol, tok2.symbol), None) is None:
            opt_ltvs[(tok1.symbol, tok2.symbol)] = prev_ltv
            break
        insolvencies.append(insolvency)
        prev_ltv = ltv

    if (tok1.symbol, tok2.symbol) not in opt_ltvs:
        opt_ltvs[(tok1.symbol, tok2.symbol)] = max(_lltvs)

    for k, _ltv in opt_ltvs.items():
        _li = max(
            compute_liquidation_incentive(args.m, args.beta, _ltv), args.liq_bonus
        )
        # log.info(
        #     "{},{},{:.3f},{:.3f},{:.3f},{:.3f}".format(*k, _ltv, args.m, args.beta, _li)
        # )
        ctok, dtok = k
        log.info(
            f"Collat: {ctok.upper():6s} | Debt: {dtok.upper():6s} | LI: {_li:.3f} | LLTV: {_ltv:.3f}"
        )

    if not args.save_path:
        return

    # Ensure the save directory exists
    directory = os.path.dirname(args.save_path)
    if not os.path.exists(directory):
        os.makedirs(directory)

    with open(args.save_path, "wb") as f:
        pickle.dump(opt_ltvs, f)


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
    parser.add_argument("--ltv", type=float, default=None)
    parser.add_argument("--repay_amount_usd", type=float, default=None)
    parser.add_argument("--max_drawdown", type=float, default=None)
    parser.add_argument(
        "--save_path", type=str, default="", help="Path to save results"
    )
    parser.add_argument(
        "--iters", type=int, default=1000, help="Number of iterations to run in the sim"
    )
    parser.add_argument("--m", type=float, default=0.15)
    parser.add_argument("--beta", type=float, default=0.4)
    parser.add_argument("--liq_bonus", type=float, default=0.01)
    args = parser.parse_args()
    main(args)
