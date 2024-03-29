from __future__ import annotations

import argparse

import numpy as np

from gauntlet.coingecko import CoinGecko
from gauntlet.coingecko import current_price
from gauntlet.coingecko import token_from_symbol_or_address
from gauntlet.data_utils import get_drawdowns
from gauntlet.data_utils import get_price_impacts
from gauntlet.logger import get_logger
from gauntlet.sim import compute_liquidation_incentive
from gauntlet.sim import get_init_collateral_usd
from gauntlet.sim import heuristic_drawdown
from gauntlet.sim import simulate_insolvency


log = get_logger(__name__)

CG = CoinGecko()


def main(args: argparse.Namespace):
    """
    This main function will compute the optimal LTVs (highest LTV) with 0
    insolvencies for all token pair markets.
    The resulting dict of LTV results (pair of tokens -> LTV value) will
    be saved in the save path specified by the input args.
    """
    if args.collateral and args.borrow:
        collateral_token = token_from_symbol_or_address(args.collateral)
        debt_token = token_from_symbol_or_address(args.borrow)

        tokens = [collateral_token, debt_token]
        prices = {t: current_price(t.address) for t in tokens}
        price_impacts = get_price_impacts(
            tokens,
            impacts=[0.005, 0.25],
            update_cache=args.update_cache,
            use_cache=args.use_cache,
        )
        drawdowns = get_drawdowns(
            tokens, update_cache=args.update_cache, use_cache=args.use_cache
        )
        repay_amount_usd = min(
            price_impacts[collateral_token.symbol]["0.005"]
            * prices[collateral_token],
            price_impacts[debt_token.symbol]["0.005"] * prices[debt_token],
        )
        max_drawdown = heuristic_drawdown(
            collateral_token, debt_token, drawdowns
        )
        init_collateral_usd = get_init_collateral_usd(
            collateral_token, debt_token, price_impacts
        )
        log.debug(
            f"{collateral_token} / {debt_token} | repay amount: ${repay_amount_usd:.2f}"
            + f" | drawdown: {max_drawdown:.3f} | init collat usd: {init_collateral_usd}"
            + f" | collateral price = ${prices[collateral_token]:.2f}, debt price = ${prices[debt_token]:.2f}"
            + f" | emp drawdown: {drawdowns[(collateral_token.symbol, debt_token.symbol)]}"
        )
    else:
        debt_token = None
        collateral_token = None
        log.info("Running sim with fully parameterized values")

    lltvs = np.arange(0.01, 1.0, 0.01)
    opt_lltv = None
    opt_li = None
    for ltv in lltvs:
        liq_bonus = max(
            compute_liquidation_incentive(args.m, args.beta, ltv),
            args.min_liq_bonus,
        )
        insolvency = simulate_insolvency(
            initial_collateral_usd=args.initial_collateral_usd
            or init_collateral_usd,
            collateral_price=args.collateral_price
            or prices.get(collateral_token),
            debt_price=args.debt_price or prices.get(debt_token),
            lltv=ltv,
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
            + f"{collateral_token} / {debt_token}"
        )

    _cs = collateral_token.symbol if collateral_token else None
    _ds = debt_token.symbol if debt_token else None
    log.info(
        f"Collateral: {_cs} | Debt: {_ds} | LI: {opt_li:.3f} | LLTV: {opt_lltv:.3f}"
    )


if __name__ == "__main__":
    log.info("Starting")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-b",
        "--borrow",
        type=str,
        help="symbol or address of the borrowable asset",
    )
    parser.add_argument(
        "-c",
        "--collateral",
        type=str,
        help="symbol or address of the collateral asset",
    )
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
        help="Size of collateral position to liquidate in the simulation",
    )
    parser.add_argument(
        "--collateral_price",
        type=float,
        default=None,
        help="[Optional] Price of collateral asset. If this is not provided, the simulation uses the current price",
    )
    parser.add_argument(
        "--debt_price",
        type=float,
        default=None,
        help="[Optional] Price of the borrowable asset. If this is not provided, the simulation uses the current price.",
    )
    parser.add_argument(
        "--repay_amount_usd",
        type=float,
        default=None,
        help="[Optional] Amount of debt that is repaid during the simulation",
    )
    parser.add_argument(
        "--max_drawdown",
        type=float,
        default=None,
        help="[Optional] The maximum proportion the collateral price to debt price can drop during the simulation",
    )
    parser.add_argument(
        "--m",
        type=float,
        default=0.15,
        help="Liquidation incentive parameter that determines the largest liquidation incentive allowed",
    )
    parser.add_argument(
        "--beta",
        type=float,
        default=0.3,
        help="Liquidation incentive parameter",
    )
    parser.add_argument(
        "--min_liq_bonus",
        type=float,
        default=0.005,
        help="Minimum liquidation bonus",
    )
    parser.add_argument(
        "--update_cache",
        action="store_true",
        default=False,
        help="Update the drawdown and price impact caches with newly computed values.",
    )
    parser.add_argument(
        "--use_cache",
        action="store_true",
        default=True,
        help="If true/set, use precomputed price impact, and historical drawdown numbers",
    )
    args = parser.parse_args()

    if (args.collateral is None or args.borrow is None) and (
        args.initial_collateral_usd is None
        or args.repay_amount_usd is None
        or args.debt_price is None
        or args.collateral_price is None
        or args.max_drawdown is None
    ):
        parser.error(
            "If 'collateral' and 'borrow' are not provided, "
            + "the following arguments must be supplied: "
            + "'initial_collateral_usd', 'repay_amount_usd'"
            + "'debt_price', 'collateral_price', 'max_drawdown'."
        )
    main(args)
