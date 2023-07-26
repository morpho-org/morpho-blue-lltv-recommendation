import pprint
import time
import random
import pandas as pd
from constants import Token, TOKENS, SYMBOL_MAP, ADDRESS_MAP
from coingecko import get_current_price

from utils import price_impact_size

def get_init_prices():
    init_prices = {}

    for s, tok in SYMBOL_MAP.items():
        init_prices[tok] = get_current_price(tok.address)
        time.sleep(2)

    pprint.pp(init_prices)
    return init_prices


# get_init_prices()
# hard code for now to avoid api dependence for end-to-end walkthrough
init_prices =  {
    Token(address='0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9', decimals=18, coingecko_id='aave', symbol='aave'): 70.12,
    Token(address='0x111111111117dc0aa78b770fa6a738034120c302', decimals=18, coingecko_id='1inch', symbol='1inch'): 0.299573,
    Token(address='0xd33526068d116ce69f19a9ee46f0bd304f21a51f', decimals=18, coingecko_id='rocket-pool', symbol='rpl'): 29.47,
    Token(address='0x514910771af9ca656af840dff83e8264ecf986ca', decimals=18, coingecko_id='chainlink', symbol='link'): 7.5,
    Token(address='0x2260fac5e5542a773aa44fbcfedf7c193bc2c599', decimals=8, coingecko_id='wrapped-bitcoin', symbol='wbtc'): 29266,
    Token(address='0xae78736cd615f374d3085123a210448e74fc6393', decimals=18, coingecko_id='rocket-pool-eth', symbol='reth'): 1997.6,
    Token(address='0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2', decimals=18, coingecko_id='weth', symbol='weth'): 1854.7,
    Token(address='0xbe9895146f7af43049ca1c1ae358b0541ea49704', decimals=18, coingecko_id='coinbase-wrapped-staked-eth', symbol='cbeth'): 1934.15,
    Token(address='0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0', decimals=18, coingecko_id='wrapped-steth', symbol='wsteth'): 2101.14,
    Token(address='0xc011a73ee8576fb46f5e1c5751ca3b9fe0af2a6f', decimals=18, coingecko_id='havven', symbol='snx'): 2.57,
    Token(address='0xba100000625a3754423978a60c9317c58a424e3d', decimals=18, coingecko_id='balancer', symbol='bal'): 4.49,
    Token(address='0xc18360217d8f7ab5e7c516566761ea12ce7f9d72', decimals=18, coingecko_id='ethereum-name-service', symbol='ens'): 9.15,
    Token(address='0x1f9840a85d5af5bf1d1762f925bdaddc4201f984', decimals=18, coingecko_id='uniswap', symbol='uni'): 5.82,
    Token(address='0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2', decimals=18, coingecko_id='maker', symbol='mkr'): 1148.0,
    Token(address='0x5a98fcbea516cf06857215779fd812ca3bef1b32', decimals=18, coingecko_id='lido-dao', symbol='ldo'): 1.91,
    Token(address='0xd533a949740bb3306d119cc777fa900ba034cd52', decimals=18, coingecko_id='curve-dao-token', symbol='crv'): 0.722208
}
init_prices_sym = {token.symbol: value for token, value in init_prices.items()}

# Using pre-computed values during testing
# repay_amounts_25bps = {
#     tok.symbol: price_impact_size(tok.address, tok.decimals, SYMBOL_MAP['usdc'].address, SYMBOL_MAP['usdc'].decimals, 0.0025) for tok in TOKENS if tok.symbol not in {'usdc', 'usdt'}
# }
#repay_amounts_25bps = {}
#for sym, tok in SYMBOL_MAP.items():
#    print(sym)
#    repay_amounts_25bps[sym] = price_impact_size(tok.address, tok.decimals, SYMBOL_MAP['usdc'].address, SYMBOL_MAP['usdc'].decimals, 0.0025)
#
#pprint.pp(repay_amounts_25bps)
# TODO: These figures look really off. Probably need at least 50bps price impact.
repay_amounts_25_bps = {
    'aave': 192.1541839582141,
    '1inch': 780490.2683210145,
    'rpl': 145.22300943235894,
    'link': 81.27184587217045,
    'wbtc': 21.395316993016568,
    'reth': 939.9862636674002,
    'weth': 2703.0095308116056,
    'cbeth': 972.0112597784333,
    'wsteth': 894.5226588552972,
    'snx': 520.1859907670454,
    'bal': 17438.61607142857,
    'ens': 770.476725439078,
    'uni': 6746.545768566494,
    'mkr': 50.851153385520625,
    'ldo': 10225.785340314136,
    'crv': 407219.46466473094
}

# repay_amounts_50bps = {
#     repay_amounts_50bps[tok.symbol] = price_impact_size(tok.address, tok.decimals, SYMBOL_MAP['usdc'].address, SYMBOL_MAP['usdc'].decimals, 0.005) for tok in TOKENS if tok.symbol not in {'usdc', 'usdt'}
# }
# pprint.pp(repay_amounts_50bps)
repay_amounts_50bps = {
    'aave': 244.48989628040053,
    '1inch': 784106.7623039943,
    'rpl': 1657.4380515953835,
    'link': 41778.074866310155,
    'wbtc': 128.2972390434158,
    'reth': 4853.918960221665,
    'weth': 9268,
    'cbeth': 3100,
    'wsteth': 4765.283573406092,
    'snx': 7454.675572519083,
    'bal': 83018.73601789711,
    'ens': 1475.5752060439563,
    'uni': 5059.90932642487,
    'mkr': 100,
    'ldo': 30677.35602094241,
    'crv': 732861.5919551731
}

# Use aave supply caps and take some constant fraction of it
init_collaterals = {
    'weth': 500_000_000 / init_prices['weth'],
    'wbtc': 350_000_000 / init_prices['wbtc'],
    'link': 10_000_000 / init_prices['link'],
    'crv': 10_000_000 / init_prices['crv'],
    'bal': 5_000_000 / init_prices['crv'],
}


AAVE_LIQ_BONUS = {
    "weth": 0.05,
    "wbtc": 0.05,
    "link": 0.07,
    "crv": 0.083,
    "bal": 0.083,
}

# Loop over the tokens, get the market data, compute
drawdowns = {
    'weth': 0.18,
    'wbtc': 0.17,
    'link': 0.18,
    'crv': 0.31,
    'bal': 0.3
}

def main():
    threshold = 0.05
    drawdown_scalar = 1.5

    sym_ltvs = {}
    lltvs = [0.01 * x for x in range(60, 100)]
    fig, axs = plt.subplots(3, 2, figsize=(10, 10)) # Create a 2x2 grid of subplots
    fig.subplots_adjust(wspace=0.3, hspace=0.3) # Add space between subplots
    opt_vals = {}

    for idx, sym in SYMBOL_MAP.items():
        sym_ltvs[sym] = {}
        ltvs = sym_ltvs[sym]

        for l in lltvs:
            ins = simulate_insolvency(initial_collateral_price=init_prices[sym], initial_debt_price=1, initial_collateral=init_collaterals[sym], LTV=l,
                                          repay_amount_usd=repay_amounts_50bps[sym], liq_bonus=liq_bonus[sym], max_drawdown=drawdowns[sym] * drawdown_scalar, decr_scale=0.99, symbol=sym)

            ltvs[l] = ins / (init_collaterals[sym] * init_prices[sym])
            if sym not in opt_vals and ltvs[l] > threshold:
                opt_vals[sym] = l

        ls = list(ltvs.keys())
        ds = [ltvs[l]for l in ls]

    #     ax = axs[idx//2, idx%2]
    #     ax.plot(ls, ds)
    #     ax.set_ylabel("Bad Debt")
    #     ax.set_xlabel("LLTV")
    #     ax.axhline(threshold, color='r', linestyle='--')
    #     ax.set_title(f"{sym.upper()} Insolvent Debt by LLTV: {opt_vals[sym]:.2f}")
    # plt.show()
