## Script containing the functions to calculate an optimal LLTV or supply cap
import numpy as np
import yfinance as yf

from gauntlet.sim import compute_liquidation_incentive
from gauntlet.constants import M, BETA
from gauntlet.sim import simulate_insolvency
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

def get_max_lltv(collateral_token_address, loan_token_address):
    
    # Parameters for the simulation
    collateral_token = token_from_symbol_or_address(collateral_token_address)
    debt_token = token_from_symbol_or_address(loan_token_address)

    tokens = [collateral_token, debt_token]
    prices = {t: current_price(t.address) for t in tokens}
    if collateral_token.symbol[0] == 'b':
        # RWA Backed asset case

        ticker = collateral_token.symbol[1:] + '.L' # Yahoo finance ticker
        
        # Last year historical prices of RWA
        bond_ticker = yf.Ticker(ticker)
        df_prices = bond_ticker.history(period="max")
        df_prices.sort_index(inplace=True)
        df_prices.dropna(inplace=True)

        # Max drawdown computation
        # 99% Worst drawdown for NB_FULL_LIQUIDATION_DAYS (which is equal to the time it takes to fully liquidate a position)
        NB_FULL_LIQUIDATION_DAYS = 30
        df_prices['drawdown'] = (df_prices['Close'].rolling(NB_FULL_LIQUIDATION_DAYS).max() - df_prices['Close']) / df_prices['Close'].rolling(NB_FULL_LIQUIDATION_DAYS).max()
        p = 0.99
        max_drawdown = df_prices['drawdown'].quantile(p)

        # Pct_decrease computation
        # Mean drawdown over NB_LIQUIDATION_DAYS (which is equal to the timestep for one liquidation)
        NB_LIQUIDATION_DAYS = 3
        pct_decrease = ((df_prices['Close'].rolling(NB_LIQUIDATION_DAYS).max() - df_prices['Close']) / df_prices['Close'].rolling(NB_LIQUIDATION_DAYS).max()).mean()

        # Repay amount, assumed repayment amount is 100k USD (no flashloans available)
        repay_amount_usd = 100_000 # no flashloan for RWA

        init_collateral_usd = 40_000_000 # 40M USD the current supply of IB01 


    else:
        # Crypto backed asset case

        update_cache = False
        use_cache = True

        price_impacts = get_price_impacts(
            tokens,
            impacts=[0.005, 0.25],
            update_cache=update_cache,
            use_cache=use_cache,
        )
        collat_price = prices[collateral_token]
        debt_price = prices[debt_token]

        drawdowns = get_drawdowns(
            tokens, update_cache=update_cache, use_cache=use_cache
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
        pct_decrease = 0.005
    
    lltvs = np.arange(0.01, 1.0, 0.001)
    opt_lltv = None
    opt_li = None

    # Iterate through all LLTVs and find the optimal one
    for ltv in lltvs:
        liq_bonus = compute_liquidation_incentive(M, BETA, ltv)
        insolvency = simulate_insolvency(
            initial_collateral_usd=init_collateral_usd
            or init_collateral_usd,
            collateral_price=prices.get(collateral_token),
            debt_price=prices.get(debt_token),
            lltv=ltv,
            repay_amount_usd=repay_amount_usd or repay_amount_usd,
            liq_bonus=liq_bonus,
            max_drawdown=max_drawdown or max_drawdown,
            pct_decrease=pct_decrease,
        )

        # If the simulation is insolvent, then we have found the optimal LLTV
        if insolvency > 0:
            break

        opt_lltv = ltv
        opt_li = liq_bonus


    return opt_lltv

def get_max_supply_cap(collateral_token, loan_token, lltv):
    1


if __name__ == '__main__':
    collateral_token = "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84" # stETH
    loan_token = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2" # WETH

    collateral_token = "0xCA30c93B02514f86d5C86a6e375E3A330B435Fb5" # IB01
    loan_token = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48" # WETH

    max_lltv = get_max_lltv(collateral_token, loan_token)
    print(max_lltv)