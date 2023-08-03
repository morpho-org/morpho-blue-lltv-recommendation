import json
import pickle
import pprint

from coingecko import CoinGecko
from constants import SYMBOL_MAP
from sim import AAVE_LIQ_BONUS
from sim import init_collaterals
from sim import init_prices_sym

T2 = {"link", "bal", "mkr", "ldo", "uni"}

T1 = BCHIPS = BLUE_CHIP = {
    "weth",
    "wbtc",
    "wsteth",
    "reth",
    "cbeth",
    "usdc",
    "usdt",
}


def get_init_collateral_usd(sym1, sym2):
    if sym1 in BLUE_CHIP:
        return 200_000_000
    elif sym1 in T2:
        return 20_000_000
    else:
        breakpoint()


def simulate_insolvency(
    *,
    initial_collateral_usd,
    initial_collateral_price,
    initial_debt_price,
    ltv,
    repay_amount_usd,
    liq_bonus,
    max_drawdown=0.3,
    decr_scale=0.995,
    symbol1="",
    symbol2="",
):
    drawdown_buffer = 0.02
    if 1 - ltv > max_drawdown:
        return 0

    collateral_usd = initial_collateral_usd
    collateral_tokens = initial_collateral_usd / initial_collateral_price
    debt_usd = initial_collateral_usd * ltv
    debt_tokens = debt_usd / initial_debt_price
    ctd = initial_ctd = (
        collateral_usd / debt_usd
    )  # decreasing ctd --> increasing dtc
    min_price = initial_ctd * (1 - max_drawdown - drawdown_buffer)
    insolvency = 0
    max_iters = 100000  # this should be a function of the

    net_collateral = collateral_tokens * initial_collateral_price
    net_debt = debt_tokens * initial_debt_price

    for i in range(1000):
        net_collateral *= decr_scale
        ctd = (net_collateral / net_debt) * decr_scale

        dtc = 1 / ctd
        if dtc >= ltv:
            collateral_claimed_usd = min(
                min(net_debt, repay_amount_usd) * (1 + liq_bonus),
                net_collateral,
            )
            # now givenn the collateral amount repaid, back out the debt repaid

            net_collateral -= collateral_claimed_usd
            net_debt -= collateral_claimed_usd / (
                1 + liq_bonus
            )  # should be clearing out more collateral than debt due to LB

        if net_collateral == 0:
            insolvency = net_debt
            return insolvency

        if net_debt == 0:
            insolvency = 0
            return insolvency

    return insolvency


def heuristic_drawdown(s1, s2):
    if s1 in T2 and s2 in T2:
        return 0.5
    elif s1 in T1 and s2 in T2:
        return 0.35
    elif s1 in T2 and s2 in T1:
        return 0.35
    elif s1 in T1 and s2 in T1:
        return 0.25
    else:
        breakpoint()


def main():
    decr_scale = 0.995
    threshold = 0
    drawdown_scalar = 1
    lltvs = [0.01 * x for x in range(50, 100)]
    sym_ltvs = {}
    opt_ltvs = {}

    symbols = [
        # 'wsteth'
        "weth",
        "usdc",
        "wbtc",
        "link",
        "uni",
        "bal",
    ]

    cg = CoinGecko()
    impacts = json.load(open("../data/swap_sizes.json", "r"))
    prices = {s: cg.current_price(SYMBOL_MAP[s].address) for s in symbols}
    repay_amnts = {
        s: impacts[s]["0.005"] * prices[s] for s in symbols if s != "usdc"
    }
    repay_amnts["usdc"] = repay_amnts["usdt"] = 100_000_000
    print("repay amounts:")
    print(repay_amnts)

    # for idx, sym in enumerate(symbols):
    for idx, sym in enumerate(symbols):
        # for j, sym2 in enumerate(symbols):
        for j, sym2 in enumerate(symbols):
            # for j, sym2 in enumerate(['uni', 'link', 'bal']):
            if sym == sym2:
                continue

            opt_ltvs[(sym, sym2)] = []
            sym_ltvs[(sym, sym2)] = {}
            for p in [95]:
                print("-" * 90)

                sym_ltvs[(sym, sym2)][p] = {}
                ltvs = sym_ltvs[(sym, sym2)][p]
                repay_amount_usd = min(repay_amnts[sym], repay_amnts[sym2])

                for l in lltvs:
                    initial_collateral_usd = get_init_collateral_usd(sym, sym2)
                    ins = simulate_insolvency(
                        initial_collateral_usd=initial_collateral_usd,
                        initial_collateral_price=prices[sym],
                        initial_debt_price=prices[sym2],
                        ltv=l,
                        repay_amount_usd=repay_amount_usd,
                        liq_bonus=0.08,
                        max_drawdown=heuristic_drawdown(sym, sym2),
                        decr_scale=0.995,
                        symbol1=sym,
                        symbol2=sym2,
                    )

                    ltvs[l] = ins / initial_collateral_usd
                    if ltvs[l] > 0:
                        print(
                            f"First nonzero ltv for {sym}, {sym2}: {l} | Repay: {repay_amount_usd} | {ltvs[l]}"
                        )
                        opt_ltvs[(sym, sym2)] = l
                        break

    pprint.pp(opt_ltvs)


if __name__ == "__main__":
    main()
