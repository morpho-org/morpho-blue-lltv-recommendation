import os
import json
import pickle
import pprint
from typing import Tuple

import logger
from coingecko import CoinGecko
from constants import AAVE_TOKENS
from constants import STABLECOINS
from tokens import Tokens

log = logger.get_logger(__name__)

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
    '''
    The sim initializes one collateral position that maxes out its
    borrow power. The size of this collateral position is effectively
    a function of 25% price impact with clamping to a reasonable closest
    10mil/100mil figure..

    These numbers are subject to change but at the moment they give us reasonable results.
    '''
    if tok in T1:
        return 200_000_000
    elif tok in T2:
        return 20_000_000
    # TODO: stablecoins can use 25% price impact instead probably
    elif tok in {Tokens.USDC, Tokens.DAI, Tokens.USDT}:
        return 500_000_000
    elif tok == Tokens.FRAX:
        return 250_000_000
    elif tok == Tokens.LUSD:
        return 12_500_000
    else:
        log.error(
            f"Getting init collateral for {tok.symbol} doesnt match existing cases"
        )
        raise ValueError


# TODO: Abstract
def heuristic_drawdown(
    t1: Tokens, t2: Tokens, drawdowns: dict[Tuple[str, str], float]
) -> float:
    '''
    t1: Token, the collateral asset of a market
    t2: Token, the borrowable asset of a market
    drawdowns: dict, dict of the collateral/borrow Tokens pair mapped to
        the time horizon max drawdowns of their price ratio.
    '''
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
    elif t1 in T1 and t2 in T2:
        dd = 0.35
    elif t1 in T2 and t2 in T1:
        dd = 0.35
    else:
        dd = 0.3  # TODO: double check cases

    return max(dd, hist_dd)


def simulate_insolvency(
    *,
    initial_collateral_usd: float,
    initial_collateral_price: float,
    initial_debt_price: float,
    ltv: float,
    repay_amount_usd: float,
    liq_bonus: float,
    max_drawdown: float,
    decr_scale: float,
) -> float:
    '''
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
    - initial_collateral_price: float, initial price of the collateral asset
    - initial_debt_price: float, initial price of the debt asset
    - ltv: float, loan to value parameter (technically this is the borrow power being used)
    - repay_amount_usd: float, amount of USD being repaid at each timestep if the account
        is liquidateable
    - liq_bonus: float, liquidation bonus
    - max_drawdown: float, largest collateral value decrease allowed during the simulation
    - decr_scale: float, proportion to scale the collateral value by at each timestep
        decr_scale \in [0, 1] so the collateral value always decreases.
    '''
    collateral_usd = initial_collateral_usd
    collateral_tokens = initial_collateral_usd / initial_collateral_price
    debt_usd = initial_collateral_usd * ltv
    debt_tokens = debt_usd / initial_debt_price
    initial_ctd = collateral_usd / debt_usd

    net_collateral_usd = collateral_tokens * initial_collateral_price
    net_debt_usd = debt_tokens * initial_debt_price
    min_collat = initial_ctd * (1 - max_drawdown)
    insolvency = 0

    for i in range(1000):
        """
        We dont actually need to explicitly update the collateral asset price
        (or the debt asset's price). Decreasing the value of the collateral
        will acheive the same effect.

        collat to debt = (collat tokens * collat price) / (debt tokens * debt price)
        Decreasing the {collat price / debt price} by 0.005% is the same as
        multiplying it by (1 - 0.005), hence the scaling by {decr_scale} parameter.
        """
        # TODO: Abstract state update
        net_collateral_usd = max(min_collat, net_collateral_usd * decr_scale)
        debt_to_collat = net_debt_usd / net_collateral_usd

        if debt_to_collat >= ltv:
            collateral_claimed_usd = min(
                min(net_debt_usd, repay_amount_usd) * (1 + liq_bonus),
                net_collateral_usd,
            )

            net_collateral_usd -= collateral_claimed_usd
            net_debt_usd -= collateral_claimed_usd / (1 + liq_bonus)

        if net_collateral_usd == 0:
            insolvency = net_debt_usd
            return insolvency

        if net_debt_usd == 0:
            insolvency = 0
            return insolvency

    insolvency = net_debt_usd
    return insolvency


def main():
    # TODO: Argparse these arg (decr_scale, liq_bonus, ...)
    decr_scale = 0.995
    liq_bonus = 0.02
    lltvs = [0.01 * x for x in range(40, 100)]
    stable_lltvs = [0.005 * x for x in range(90 * 2, int(99.5 * 2))]
    opt_ltvs = {}

    # symbols =
    tokens = [Tokens.USDC, Tokens.USDT, Tokens.DAI, Tokens.LUSD, Tokens.FRAX]

    cg = CoinGecko()
    impacts = json.load(open("../data/swap_sizes.json", "r"))
    prices = {t: cg.current_price(t.address) for t in tokens}
    drawdowns = pickle.load(open("../data/pairwise_drawdowns.pkl", "rb"))
    repay_amnts = {t: impacts[t.symbol]["0.005"] * prices[t] for t in tokens}
    log.info(f"repay amounts: {repay_amnts}")

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
            )
            prev_ltv = _lltvs[0] - 0.005
            for ltv in _lltvs:
                insolvency = simulate_insolvency(
                    initial_collateral_usd=init_cusd,
                    initial_collateral_price=prices[tok1],
                    initial_debt_price=prices[tok2],
                    ltv=ltv,
                    repay_amount_usd=repay_amount_usd,
                    liq_bonus=liq_bonus,
                    max_drawdown=max_dd,
                    decr_scale=decr_scale,
                )


                # Note: we do not actually care about the size of the insolvency.
                # For the purpose of the risk assessment, we are most interested in the lowest
                # LTV that does not realize insolvencies.
                if insolvency > 0:
                    opt_ltvs[(tok1.symbol, tok2.symbol)] = prev_ltv
                    break

                prev_ltv = ltv

    for k, v in opt_ltvs.items():
        log.info("{:6s} / {:6s}: opt LTV: {:.3f}".format(*k, v))

    if not os.path.exists("results"):
        os.makedirs("../results")
    with open("../results/ltvs.pkl",'wb') as f:
        pickle.dump(opt_ltvs, f)
    # pprint.pp(opt_ltvs)


if __name__ == "__main__":
    # TODO: argparse
    main()
