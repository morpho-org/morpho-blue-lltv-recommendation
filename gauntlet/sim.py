import matplotlib.pyplot as plt
import pprint
import random
import time
from utils import price_impact_size

import pandas as pd
from coingecko import get_current_price
from constants import ADDRESS_MAP
from constants import SYMBOL_MAP
from constants import Token
from constants import TOKENS

from drawdowns import load_prices, load_ohlcs, compute_drawdowns, get_price_ratios

def get_init_prices():
    init_prices = {}

    for s, tok in SYMBOL_MAP.items():
        init_prices[tok] = get_current_price(tok.address)
        time.sleep(2)

    pprint.pp(init_prices)
    return init_prices


# get_init_prices()
# hard code for now to avoid api dependence for end-to-end walkthrough
init_prices = {
    Token(
        address="0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9",
        decimals=18,
        coingecko_id="aave",
        symbol="aave",
    ): 70.12,
    Token(
        address="0x111111111117dc0aa78b770fa6a738034120c302",
        decimals=18,
        coingecko_id="1inch",
        symbol="1inch",
    ): 0.299573,
    Token(
        address="0xd33526068d116ce69f19a9ee46f0bd304f21a51f",
        decimals=18,
        coingecko_id="rocket-pool",
        symbol="rpl",
    ): 29.47,
    Token(
        address="0x514910771af9ca656af840dff83e8264ecf986ca",
        decimals=18,
        coingecko_id="chainlink",
        symbol="link",
    ): 7.5,
    Token(
        address="0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",
        decimals=8,
        coingecko_id="wrapped-bitcoin",
        symbol="wbtc",
    ): 29266,
    Token(
        address="0xae78736cd615f374d3085123a210448e74fc6393",
        decimals=18,
        coingecko_id="rocket-pool-eth",
        symbol="reth",
    ): 1997.6,
    Token(
        address="0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
        decimals=18,
        coingecko_id="weth",
        symbol="weth",
    ): 1854.7,
    Token(
        address="0xbe9895146f7af43049ca1c1ae358b0541ea49704",
        decimals=18,
        coingecko_id="coinbase-wrapped-staked-eth",
        symbol="cbeth",
    ): 1934.15,
    Token(
        address="0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0",
        decimals=18,
        coingecko_id="wrapped-steth",
        symbol="wsteth",
    ): 2101.14,
    Token(
        address="0xc011a73ee8576fb46f5e1c5751ca3b9fe0af2a6f",
        decimals=18,
        coingecko_id="havven",
        symbol="snx",
    ): 2.57,
    Token(
        address="0xba100000625a3754423978a60c9317c58a424e3d",
        decimals=18,
        coingecko_id="balancer",
        symbol="bal",
    ): 4.49,
    Token(
        address="0xc18360217d8f7ab5e7c516566761ea12ce7f9d72",
        decimals=18,
        coingecko_id="ethereum-name-service",
        symbol="ens",
    ): 9.15,
    Token(
        address="0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",
        decimals=18,
        coingecko_id="uniswap",
        symbol="uni",
    ): 5.82,
    Token(
        address="0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2",
        decimals=18,
        coingecko_id="maker",
        symbol="mkr",
    ): 1148.0,
    Token(
        address="0x5a98fcbea516cf06857215779fd812ca3bef1b32",
        decimals=18,
        coingecko_id="lido-dao",
        symbol="ldo",
    ): 1.91,
    Token(
        address="0xd533a949740bb3306d119cc777fa900ba034cd52",
        decimals=18,
        coingecko_id="curve-dao-token",
        symbol="crv",
    ): 0.722208,
}
init_prices_sym = {token.symbol: value for token, value in init_prices.items()}
init_prices_sym["wsteth"] = 2104 # init_prices[SYMBOL_MAP["wsteth"]]
# Using pre-computed values during testing
# repay_amounts_25bps = {
#     tok.symbol: price_impact_size(tok.address, tok.decimals, SYMBOL_MAP['usdc'].address, SYMBOL_MAP['usdc'].decimals, 0.0025) for tok in TOKENS if tok.symbol not in {'usdc', 'usdt'}
# }
# repay_amounts_25bps = {}
# for sym, tok in SYMBOL_MAP.items():
#    print(sym)
#    repay_amounts_25bps[sym] = price_impact_size(tok.address, tok.decimals, SYMBOL_MAP['usdc'].address, SYMBOL_MAP['usdc'].decimals, 0.0025)
#
# pprint.pp(repay_amounts_25bps)
# TODO: These figures look really off. Probably need at least 50bps price impact.
repay_amounts_25_bps = {
    "aave": 192.1541839582141,
    "1inch": 780490.2683210145,
    "rpl": 145.22300943235894,
    "link": 81.27184587217045,
    "wbtc": 21.395316993016568,
    "reth": 939.9862636674002,
    "weth": 2703.0095308116056,
    "cbeth": 972.0112597784333,
    "wsteth": 894.5226588552972,
    "snx": 520.1859907670454,
    "bal": 17438.61607142857,
    "ens": 770.476725439078,
    "uni": 6746.545768566494,
    "mkr": 50.851153385520625,
    "ldo": 10225.785340314136,
    "crv": 407219.46466473094,
}

# repay_amounts_50bps = {
#     repay_amounts_50bps[tok.symbol] = price_impact_size(tok.address, tok.decimals, SYMBOL_MAP['usdc'].address, SYMBOL_MAP['usdc'].decimals, 0.005) for tok in TOKENS if tok.symbol not in {'usdc', 'usdt'}
# }
# pprint.pp(repay_amounts_50bps)
repay_amounts_50bps = {
    "aave": 244.48989628040053,
    "1inch": 784106.7623039943,
    "rpl": 1657.4380515953835,
    "link": 31778.074866310155,
    "wbtc": 300.2972390434158,
    "reth": 6000,
    "weth": 9268,
    "cbeth": 4100,
    "wsteth": 6500.283573406092,
    "snx": 7454.675572519083,
    "bal": 83018.73601789711,
    "ens": 1475.5752060439563,
    "uni": 5059.90932642487,
    "mkr": 100,
    "ldo": 30677.35602094241,
    "crv": 382861.5919551731,
}

# Use aave supply caps and take some constant fraction of it
init_collaterals = {
    "weth": 500_000_000 / init_prices_sym["weth"],
    "reth": 500_000_000 / init_prices_sym["weth"],
    "cbeth": 500_000_000 / init_prices_sym["reth"],
    "wsteth": 500_000_000 / init_prices_sym["wsteth"],
    "wbtc": 500_000_000 / init_prices_sym["wbtc"],
    "link": 10_000_000 / init_prices_sym["link"],
    "crv": 10_000_000 / init_prices_sym["crv"],
}


AAVE_LIQ_BONUS = {
    "aave": 0.075,
    "1inch": 0.075,
    # "rpl": -1.000,
    "link": 0.070,
    "wbtc": 0.050,
    "reth": 0.075,
    "weth": 0.050,
    "cbeth": 0.075,
    "wsteth": 0.070,
    "frax": 0.060,
    # "lusd": -1.000,
    "usdt": 0.045,
    "usdc": 0.045,
    "dai": 0.040,
    "snx": 0.085,
    "bal": 0.083,
    "ens": 0.080,
    "uni": 0.100,
    "mkr": 0.085,
    "ldo": 0.090,
    "crv": 0.083,
}

drawdowns = compute_drawdowns() # symbol -> np array

# symbol -> pctile -> float
# drawdowns = {"weth": 0.18, "wbtc": 0.17, "link": 0.18, "crv": 0.31, "bal": 0.3}

'''
- initial collateral price
- initial supply price
- price inc rate, supply inc rate
'''
def simulate_insolvency(
    *,
    initial_collateral_price,
    initial_debt_price,
    initial_collateral,
    ltv,
    repay_amount_usd,
    liq_bonus,
    max_drawdown=0.3,
    decr_scale=0.995,
    symbol="",
):
    drawdown_buffer = 0.02
    if 1 - ltv > max_drawdown:
        return 0

    min_price = initial_collateral_price * (1 - max_drawdown - drawdown_buffer)
    collateral = initial_collateral  # in tokens
    collateral_usd = initial_collateral_price * collateral
    price = initial_collateral_price
    debt_usd = initial_debt_price * ltv * collateral_usd
    insolvency = 0
    max_iters = 100000

    price *= (1 - 0.1) # initial drop
    for i in range(max_iters):
        # Decrease the price of the collateral
        #nprice = max(min_price, price * decr_scale)
        price = price * decr_scale
        collateral_usd = price * collateral

        # If the debt to collateral ratio is lower than the LTV, we can start liquidating
        dtc = debt_usd / collateral_usd
        if dtc >= ltv:
            if debt_usd < repay_amount_usd:
                debt_usd = 0  # repay larger than debt so done
                claimed_collateral_usd = min(
                    repay_amount_usd * (1 + liq_bonus), collateral_usd
                )  # claim the rest or the standard bonus
                collateral_usd -= claimed_collateral_usd
                collateral -= claimed_collateral_usd / price  # tokens
                insolvency = 0
                break
            else:
                # repay is less than the debt. but potentially more than the collateral remaining
                claimed_collateral_usd = min(
                    repay_amount_usd * (1 + liq_bonus), collateral_usd
                )
                repay_amount_usd = claimed_collateral_usd / (1 + liq_bonus)
                collateral_usd -= claimed_collateral_usd
                collateral -= claimed_collateral_usd / price
                debt_usd -= repay_amount_usd

        if collateral_usd == 0:
            insolvency = debt_usd
            break

    # print("Iters:", i, "price:", price, "debt_usd", debt_usd, "collateral_usd", collateral_usd)
    return insolvency


def main():
    decr_scalar = 0.995
    threshold = 0
    drawdown_scalar = 1
    lltvs = [0.01 * x for x in range(50, 100)]
    sym_ltvs = {}
    opt_vals = {}

    excluded = ["usdc", "usdt", "rpl"]
    symbols = list(x for x in SYMBOL_MAP.keys() if not x in excluded)
    symbols = [
        # 'wsteth'
        'weth', 'wbtc', 'link', 'crv'
    ]
    decr_scalars = {90: 1-0.005, 95: 1-0.007, 99: 1-0.01}

    for p in [90, 95, 99]:
        print('-' * 90)
        for idx, sym in enumerate(symbols):
            sym_ltvs[sym] = {}
            ltvs = sym_ltvs[sym]

            for l in lltvs:
                ins = simulate_insolvency(
                    initial_collateral_price=init_prices_sym[sym],
                    initial_debt_price=1,
                    initial_collateral=init_collaterals.get(sym, 20_000_000 / init_prices_sym[sym]),
                    ltv=l,
                    repay_amount_usd=repay_amounts_50bps[sym] * init_prices_sym[sym],
                    liq_bonus=AAVE_LIQ_BONUS[sym],
                    max_drawdown=0.3,# drawdowns[sym][p] * drawdown_scalar,
                    decr_scale=decr_scalars[p],
                    symbol=sym,
                )

                ltvs[l] = ins / (init_collaterals.get(sym, 20_000_000 / init_prices_sym[sym])* init_prices_sym[sym])
                if ltvs[l] > 0:
                    print(f"First nonzero ltv for {sym}: {l -0.01} | Repay: {repay_amounts_50bps[sym] * init_prices_sym[sym]} | {ltvs[l]}")
                    break

                # first ltv that is larger than the threshold
                if sym not in opt_vals and ltvs[l] > threshold:
                    opt_vals[sym] = l

            ls = list(ltvs.keys())
            ds = [ltvs[l] for l in ls]


if __name__ == "__main__":
    main()
