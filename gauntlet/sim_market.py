import pprint
import pickle
from coingecko import CoinGecko

from sim import init_collaterals
from sim import repay_amounts_50bps
from sim import AAVE_LIQ_BONUS
from sim import init_prices_sym

def get_init_collateral_usd(sym1, sym2):
    if sym1 in ["crv", "link", "aave"] or sym2 in ["crv", "link", "aave"]:
        return 10_000_000
    elif sym1 != sym2:
        return 400_000_000
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

    init_price = price = initial_debt_price / initial_collateral_price
    min_price = init_price * (1 - max_drawdown - drawdown_buffer)
    collateral_tokens = initial_collateral_usd / init_price
    collateral_usd = collateral_tokens * initial_collateral_price
    debt_usd = initial_collateral_usd * ltv # use it all
    debt_tokens = debt_usd / initial_collateral_price

    insolvency = 0
    max_iters = 100000

    for i in range(max_iters):
        price = max(price * decr_scale, min_price)
        # dtc = n_borrow/n_collat * price
        # value of collateral has decreased

        # debt to collateral
        if collateral_usd == 0:
            return insolvency

        dtc = debt_usd / collateral_usd
        if dtc >= ltv:
            # collateral repaid is the smaller of
            # how much we can repay * (1 + liq bonus)
            #   - repay amount is lower bounded by the actual debt
            # the repay amount x (1 + liq bonus) may be larger than the actual collateral to claim, hence the other min
            collateral_repaid_usd = min(min(debt_usd, repay_amount_usd) * (1 + liq_bonus), collateral_usd)
            # now that we know the collateral claimed, we can figure out the repay amount by div by 1+liq bonus
            actual_repay_amount_usd = collateral_repaid_usd / (1 + liq_bonus)
            collateral_usd -= collateral_repaid_usd
            debt_usd -= actual_repay_amount_usd

        if collateral_usd == 0:
            insolvency = debt_usd
            print(collateral_usd)
        if debt_usd == 0:
            insolvency = 0
            break

    return insolvency


def main():
    decr_scalar = 0.995
    threshold = 0
    drawdown_scalar = 1
    lltvs = [0.01 * x for x in range(50, 100)]
    sym_ltvs = {}
    opt_vals = {}

    excluded = ["usdc", "usdt", "rpl"]
    stables = ["usdc"]
    symbols = [
        # 'wsteth'
        'weth', 'wbtc', 'link', 'crv', 'aave', 'usdc'
    ]
    decr_scalars = {90: 1-0.005, 95: 1-0.007, 99: 1-0.01}
    pair_drawdowns = pickle.load(open("../data/pairwise_drawdowns.pkl", "rb"))

    for idx, sym in enumerate(symbols):
        for j, sym2 in enumerate(symbols):
            print("repay for {} | {}: {}".format(sym, sym2, min(repay_amounts_50bps[sym] * init_prices_sym[sym], repay_amounts_50bps[sym2] * init_prices_sym[sym2])))
            if sym == sym2:
                continue
            sym_ltvs[(sym, sym2)] = {}
            # for p in [90, 95, 99.9]:
            for p in [95]:
                print('-' * 90)

                sym_ltvs[(sym, sym2)][p] = {}
                ltvs = sym_ltvs[(sym, sym2)][p]

                for l in lltvs:
                    initial_collateral_usd = get_init_collateral_usd(sym, sym2)
                    ins = simulate_insolvency(
                        initial_collateral_usd=initial_collateral_usd,
                        initial_collateral_price=init_prices_sym[sym],
                        initial_debt_price=init_prices_sym[sym2],
                        ltv=l,
                        repay_amount_usd=min(repay_amounts_50bps[sym] * init_prices_sym[sym], repay_amounts_50bps[sym2] * init_prices_sym[sym2]),
                        liq_bonus=1 - p/100,
                        max_drawdown=pair_drawdowns[(sym, sym2)][30][p] * 1.25,# drawdowns[sym][p] * drawdown_scalar,
                        decr_scale=0.01,
                        symbol1=sym,
                        symbol2=sym2,
                    )

                    ltvs[l] = ins / initial_collateral_usd
                    if ltvs[l] > 0:
                        print(f"First nonzero ltv for {sym}, {sym2}: {l -0.01} | Repay: {repay_amounts_50bps[sym] * init_prices_sym[sym]} | {ltvs[l]}")
                        break

                    # first ltv that is larger than the threshold
                    if (sym, sym2) not in opt_vals and ltvs[l] > 0:
                        opt_vals[(sym, sym2)] = l

                ls = list(ltvs.keys())
                ds = [ltvs[l] for l in ls]
    # pprint.pp(sym_ltvs)
    breakpoint()
if __name__ == "__main__":
    main()  
