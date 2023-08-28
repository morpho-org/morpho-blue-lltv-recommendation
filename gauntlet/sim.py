import argparse
import json
import os
import pickle
from pathlib import Path
from typing import Tuple

import numpy as np

from .coingecko import CoinGecko
from .constants import BLUE_CHIPS
from .constants import LARGE_CAPS
from .constants import SMALL_CAPS
from .constants import STABLECOINS
from .constants import TOL
from .logger import get_logger
from .tokens import Tokens
from .utils import compute_liquidation_incentive
from .utils import current_price


# log = logger.get_logger(__name__)
log = get_logger(__name__)


# Use this over the coingecko API when testing to avoid rate limiting.
PRICES_CACHE = {
    "aave": 65.88,
    "1inch": 0.307756,
    "rpl": 27.35,
    "link": 7.47,
    "wbtc": 29450,
    "reth": 2005.78,
    "weth": 1847.87,
    "cbeth": 1932.11,
    "wsteth": 2095.09,
    "snx": 2.54,
    "bal": 4.2,
    "ens": 8.95,
    "uni": 6.18,
    "mkr": 1248.92,
    "ldo": 1.85,
    "crv": 0.595425,
    "usdc": 1.001,
    "usdt": 0.99958,
    "dai": 1.0,
    "lusd": 0.994649,
    "frax": 0.999439,
}


def get_init_collateral_usd(
    collat_token: Tokens,
    borrow_token: Tokens,
    price_impacts: dict[str, dict[str, float]],
) -> float:
    """
    The sim initializes one collateral position that maxes out its
    borrow power. The size of this collateral position is effectively
    a function of 25% price impact with some clamping to ensure
    reasonable sizes.
    """
    if collat_token in BLUE_CHIPS and borrow_token in BLUE_CHIPS:
        return max(
            200_000_000,
            price_impacts[collat_token.symbol]["0.25"]
            * current_price(collat_token.address),
        )
    elif (collat_token in BLUE_CHIPS and borrow_token in SMALL_CAPS) or (
        collat_token in SMALL_CAPS and borrow_token in BLUE_CHIPS
    ):
        return max(
            50_000_000,
            price_impacts[collat_token.symbol]["0.25"]
            * current_price(collat_token.address),
        )
    elif collat_token in SMALL_CAPS or borrow_token in SMALL_CAPS:
        return max(
            20_000_000,
            price_impacts[collat_token.symbol]["0.25"]
            * current_price(collat_token.address),
            price_impacts[borrow_token.symbol]["0.25"]
            * current_price(borrow_token.address),
        )
    elif collat_token in STABLECOINS:  # collat stable
        return price_impacts[collat_token.symbol]["0.25"]
    elif borrow_token in STABLECOINS:
        return price_impacts[borrow_token.symbol]["0.25"]
    else:
        return 20_000_000
        # raise ValueError(
        #     f"init collateral for {collat_token.symbol} doesnt match existing"
        #     + " scenarios. Please pick an initial collateral position."
        # )


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
    log.debug(f"Historical drawdown: {hist_dd:.3f}")
    # Handle super low drawdown cases for LSTs, stablecoin depeg
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
    lltv: float,
    repay_amount_usd: float,
    liq_bonus: float,
    max_drawdown: float,
    pct_decrease: float,
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
    - lltv: float, liquidation loan to value parameter
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
    if lltv * (1 + liq_bonus) < (1 - max_drawdown):
        return 0

    collateral_tokens = initial_collateral_usd / collateral_price
    debt_tokens = (initial_collateral_usd * lltv) / debt_price
    min_collateral_price = collateral_price * (1 - max_drawdown)
    max_iters = int(np.ceil((initial_collateral_usd / repay_amount_usd) + 1))
    decrement = collateral_price * pct_decrease
    for i in range(max_iters + 10):
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
            # min_collateral_price, collateral_price * (1 - pct_decrease)
            min_collateral_price, collateral_price - decrement
        )
        net_collateral_usd = collateral_tokens * collateral_price
        net_debt_usd = debt_price * debt_tokens

        if i % 1 == 0:
            log.debug(
                f"{i=} | debt to collat: {net_debt_usd/net_collateral_usd:.3f}"
                + f" | debt: {net_debt_usd:.2f} | collat: {net_collateral_usd:.2f} | {lltv=}"
            )

        if net_debt_usd / net_collateral_usd >= lltv:
            # Figure out the most collateral a liquidator can claim
            # then back out the necessary debt they must repay to claim that
            # amount of collateral.
            collateral_claimed_usd = min(
                min(net_debt_usd, repay_amount_usd) * (1 + liq_bonus),
                net_collateral_usd,
            )
            collateral_tokens -= collateral_claimed_usd / collateral_price
            debt_tokens -= collateral_claimed_usd / (debt_price * (1 + liq_bonus))

            net_collateral_usd -= collateral_claimed_usd
            net_debt_usd -= collateral_claimed_usd / (1 + liq_bonus)
            assert abs(net_collateral_usd - collateral_price * collateral_tokens) < TOL
            assert abs(net_debt_usd - debt_tokens * debt_price) < TOL

        # 0 collateral remaining. Stop simulation
        if net_collateral_usd < TOL:
            insolvency = net_debt_usd
            log.info(
                f"Initial collateral: {initial_collateral_usd/1e6:.2f}mil | Repay usd: {repay_amount_usd:.2f} | Max drawdown: {max_drawdown:.2f}"
            )
            return insolvency

        # 0 debt remaining. Stop simulation
        if net_debt_usd < TOL:
            insolvency = 0
            return insolvency

    assert (
        net_debt_usd / net_collateral_usd
    ) < lltv, (
        f"Simulation finished with ltv > lltv: {net_debt_usd/net_collateral_usd:.3f}"
    )
    return 0
