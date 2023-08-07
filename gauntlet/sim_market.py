import pickle
import json
import pprint

import logger
from tokens import Tokens
from coingecko import CoinGecko
from constants import STABLECOINS
from constants import SYMBOL_MAP
from constants import AAVE_TOKENS

log = logger.get_logger(__name__)

T1 = [
    "weth",
    "wbtc",
    "wsteth",
    "reth",
    "cbeth",
]
T2 = [t.symbol for t in Tokens if (t.symbol not in STABLECOINS) and (t.symbol not in T1)]

# TODO: Abstract
def get_init_collateral_usd(sym):
    if sym in T1:
        return 200_000_000
    elif sym in T2:
        return 20_000_000
    elif sym in {"usdc", "dai", "usdt"}:
        return 500_000_000
    elif sym == "frax":
        return 250_000_000
    elif sym == "lusd":
        return 12_500_000
    else:
        log.error(f"Getting init collateral for {sym} doesnt match existing cases")
        raise ValueError


# TODO: Abstract PriceGenerator
def heuristic_drawdown(s1, s2, drawdowns):
    try:
        # drawdown is a dict: symbol pair -> dict of time duration -> {percentile -> value}
        # 30 day 99th percentile drawdown in ratio change of s1/s2
        hist_dd = drawdowns[(s1, s2)][30][99]
    except:
        # default hist dd
        hist_dd = 0.25

    # Handle super low drawdown cases for LSTs, stablecoin depeg
    # TODO: better parameterize these heuristic consts
    if hist_dd < 0.1:
        return max(hist_dd * 1.5, 0.02)

    if s1 in T1 and s2 in T1:
        dd =  0.25
    elif s1 in T2 and s2 in T2:
        dd =  0.5
    elif s1 in T1 and s2 in T2:
        dd =  0.35
    elif s1 in T2 and s2 in T1:
        dd = 0.35
    else:
        dd = 0.3 # TODO: double check cases

    return max(dd, hist_dd)


def simulate_insolvency(
    *,
    initial_collateral_usd,
    initial_collateral_price,
    initial_debt_price,
    ltv,
    repay_amount_usd,
    liq_bonus,
    max_drawdown,
    decr_scale,
):
    if 1 - ltv > max_drawdown:
        return 0

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
        We dont want to explicitly update the collateral asset price
        (or the debt asset's price). What actually matters is that
        the collateral to debt value has decreased:

        collat to debt = (collat tokens * collat price) / (debt tokens * debt price)
        Decreasing the {collat price / debt price} by 0.005% is the same as
        multiplying it by (1 - 0.005%), hence the scaling by decr_scale
        """
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
    liq_bonus = 0.05
    lltvs = [0.01 * x for x in range(40, 100)]
    stable_lltvs = [0.005 * x for x in range(90 * 2, int(99.5 * 2))]
    opt_ltvs = {}

    # symbols = [tok.symbol for tok in AAVE_TOKENS]
    symbols = ['usdc', 'usdt', 'dai', 'lusd', 'frax']

    cg = CoinGecko()
    impacts = json.load(open("../data/swap_sizes.json", "r"))
    prices = {s: cg.current_price(SYMBOL_MAP[s].address) for s in symbols}
    drawdowns = pickle.load(open("../data/pairwise_drawdowns.pkl", 'rb'))
    repay_amnts = {s: impacts[s]["0.005"] * prices[s] for s in symbols}
    log.info(f"repay amounts: {repay_amnts}")

    for sym1 in symbols:
        for sym2 in symbols:
            if sym1 == sym2:
                continue

            _lltvs = stable_lltvs if (sym1 in STABLECOINS and sym2 in STABLECOINS) else lltvs
            repay_amount_usd = min(repay_amnts[sym1], repay_amnts[sym2])
            max_dd = heuristic_drawdown(sym1, sym2, drawdowns)
            init_cusd = get_init_collateral_usd(sym1)
            log.debug(f"{sym1} / {sym2} | repay amount: {repay_amount_usd:.2f} | drawdown: {max_dd:.3f} | init collat usd: {init_cusd}")
            for ltv in _lltvs:
                insolvency = simulate_insolvency(
                    initial_collateral_usd=init_cusd,
                    initial_collateral_price=prices[sym1],
                    initial_debt_price=prices[sym2],
                    ltv=ltv,
                    repay_amount_usd=repay_amount_usd,
                    liq_bonus=liq_bonus,
                    max_drawdown=max_dd,
                    decr_scale=decr_scale,
                )

                if insolvency > 0:
                    opt_ltvs[(sym1, sym2)] = ltv
                    break

    for k, v in opt_ltvs.items():
        log.info("{:6s} / {:6s}: opt LTV: {:.3f}".format(*k, v))

    # pprint.pp(opt_ltvs)


if __name__ == "__main__":
    main()
