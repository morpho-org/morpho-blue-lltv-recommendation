import numpy as np
import argparse
import json
import os
import pickle
from typing import Tuple

import logger
from coingecko import CoinGecko
from constants import STABLECOINS
from tokens import Tokens
from utils import compute_liquidation_incentive

log = logger.get_logger(__name__)
TOL = 1e-4

# TODO: This set of assets can be basically be parameterized by price impact
# Ex: "Set of tokens that require incur less than 10% price impact on a $10mill swap"
# Potentially add more logic to exclude stablecoins
T1 = {
    Tokens.WETH,
    Tokens.WBTC,
    Tokens.WSTETH,
    Tokens.RETH,
    Tokens.CBETH,
}
T2 = {t for t in Tokens if (t not in STABLECOINS) and (t not in T1)}


# TODO: Abstract
def get_init_collateral_usd(tok: Tokens) -> float:
    """
    The sim initializes one collateral position that maxes out its
    borrow power. The size of this collateral position is effectively
    a function of 25% price impact with clamping to a reasonable closest
    10mil/100mil figure..

    These numbers are subject to change but at the moment they give us reasonable results.
    """
    if tok in T1:
        return 200_000_000
    elif tok in T2:
        return 20_000_000
    # TODO: stablecoins can use 25% price impact instead probably
    elif tok in {Tokens.USDC, Tokens.DAI, Tokens.USDT}:
        return 300_000_000
    elif tok == Tokens.FRAX:
        return 250_000_000
    elif tok == Tokens.LUSD:
        return 12_500_000
    else:
        log.error(
            f"Init collateral for {tok.symbol} doesnt match existing cases"
        )
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
    try:
        # drawdown is a dict: symbol pair -> dict of time duration -> {percentile -> value}
        # 30 day 99th percentile drawdown in ratio change of t1/t2
        hist_dd = drawdowns[(t1.symbol, t2.symbol)][30][99]
    except:
        # default hist dd
        hist_dd = 0.25

    # Handle super low drawdown cases for LSTs, stablecoin depeg
    # TODO: better parameterize these heuristic consts
    if hist_dd < 0.1:
        return max(hist_dd, 0.02)

    if t1 in T1 and t2 in T1:
        dd = 0.25
    elif t1 in T2 and t2 in T2:
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
    decr_scale: float,
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
    - decr_scale: float, proportion to scale the collateral value by at each timestep
        decr_scale \in [0, 1] so the collateral value always decreases.
    """
    # ltv * (1 + liq_bonus) represents the value at which insolvencies can start to happen.
    # If the maximum drawdown doesnt reach this point, we will not observe any insolvent debt
    # so skip the computation.
    if ltv * (1 + liq_bonus) < (1 - max_drawdown):
        return 0

    collateral_tokens = initial_collateral_usd / collateral_price
    collateral_price = collateral_price
    net_collateral_usd = collateral_tokens * collateral_price

    debt_price = debt_price
    debt_usd = initial_collateral_usd * ltv
    debt_tokens = debt_usd / debt_price
    net_debt_usd = debt_tokens * debt_price
    min_collateral_price = collateral_price * (1 - max_drawdown)
    insolvency = 0
    max_iters = int(np.ceil((initial_collateral_usd / repay_amount_usd) + 1))
    log.debug(f"Running for {max_iters} iters")
    assert abs(initial_collateral_usd - net_collateral_usd) < TOL
    assert abs(debt_usd - net_debt_usd) < TOL

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
        collateral_price = max(min_collateral_price, collateral_price * decr_scale)
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

        if net_collateral_usd < TOL:
            insolvency = net_debt_usd
            return insolvency

        if net_debt_usd < TOL:
            insolvency = 0
            return insolvency

    assert (net_debt_usd / net_collateral_usd) < ltv, "Simulation finished with d2c > ltv: {net_debt_usd/net_collateral_usd:.3f}, {ltv=}"
    return 0
    insolvency = net_debt_usd if (net_debt_usd / net_collateral_usd) >= ltv else 0
    return insolvency


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

    # tokens = [Tokens.WETH, Tokens.WBTC, Tokens.WSTETH, Tokens.USDC, Tokens.LINK, Tokens.UNI]
    tokens = [t for t in Tokens]

    cg = CoinGecko()
    prices = {t: cg.current_price(t.address) for t in tokens}
    # Price impact swap sizes
    impacts = json.load(open("../data/swap_sizes.json", "r"))
    # Historical drawdowns between the ratio two tokens
    drawdowns = pickle.load(open("../data/pairwise_drawdowns.pkl", "rb"))
    # Repay amount is set to be the swap size that incurs 50bps price impact
    repay_amnts = {t: impacts[t.symbol]["0.005"] * prices[t] for t in tokens}

    for tok1 in tokens:
        for tok2 in tokens:
            if tok1 == tok2:
                continue

            _lltvs = (
                stable_lltvs if (tok1 in STABLECOINS and tok2 in STABLECOINS) else lltvs
            )
            repay_amount_usd = min(repay_amnts[tok1], repay_amnts[tok2])
            max_dd = heuristic_drawdown(tok1, tok2, drawdowns)
            init_cusd = get_init_collateral_usd(tok1)
            log.debug(
                f"{tok1} / {tok2} | repay amount: {repay_amount_usd:.2f}"
                + f" | drawdown: {max_dd:.3f} | init collat usd: {init_cusd}"
                + f" | p1 = {prices[tok1]:.2f}, p2 = {prices[tok2]:.2f}"
            )
            prev_ltv = _lltvs[0] - 0.005
            for ltv in _lltvs:
                liq_bonus = compute_liquidation_incentive(args.m, args.beta, ltv)
                log.debug(f"M = {args.m:.2f}, beta = {args.beta:.2f}, LI = {liq_bonus:.3f}")
                insolvency = simulate_insolvency(
                    initial_collateral_usd=init_cusd,
                    collateral_price=prices[tok1],
                    debt_price=prices[tok2],
                    ltv=ltv,
                    repay_amount_usd=repay_amount_usd,
                    liq_bonus=liq_bonus,
                    max_drawdown=max_dd,
                    decr_scale=args.decr_scale,
                    iters=args.iters,
                )

                # Note: we do not actually care about the size of the insolvency.
                # For the purpose of the risk assessment, we are most interested in the lowest
                # LTV that does not realize insolvencies.
                if insolvency > TOL:
                    opt_ltvs[(tok1.symbol, tok2.symbol)] = prev_ltv
                    break
                prev_ltv = ltv

            if (tok1.symbol, tok2.symbol) not in opt_ltvs:
                opt_ltvs[(tok1.symbol, tok2.symbol)] = max(_lltvs)

    for k, _ltv in opt_ltvs.items():
        _li = compute_liquidation_incentive(args.m, args.beta, _ltv)
        log.info("{},{},{:.3f},{:.3f},{:.3f},{:.3f}".format(*k, _ltv, args.m, args.beta, _li))

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
    parser.add_argument(
        "--decr_scale",
        type=float,
        default=0.995,
        help="Per iter scaling factor of the collateral to debt price ratio",
    )
    parser.add_argument(
        "--save_path", type=str, default="", help="Path to save results"
    )
    parser.add_argument(
        "--iters", type=int, default=1000, help="Number of iterations to run in the sim"
    )
    parser.add_argument(
        "--m", type=float, default=0.15
    )
    parser.add_argument(
        "--beta", type=float, default=0.2
    )
    args = parser.parse_args()
    main(args)
