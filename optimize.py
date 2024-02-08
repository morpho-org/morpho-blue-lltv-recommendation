## Script containing the functions to calculate an optimal LLTV or supply cap
import numpy as np
import yfinance as yf
import requests
import os
import time

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

N_SLEEP_SEC = 15
def get_max_lltv(collateral_token_address, loan_token_address):
    
    # Parameters for the simulation
    time.sleep(N_SLEEP_SEC)
    collateral_token = token_from_symbol_or_address(collateral_token_address)
    time.sleep(N_SLEEP_SEC)
    debt_token = token_from_symbol_or_address(loan_token_address)

    tokens = [collateral_token, debt_token]
    prices = {}

    time.sleep(N_SLEEP_SEC)
    prices[collateral_token] = current_price(collateral_token.address)
    time.sleep(N_SLEEP_SEC)
    prices[debt_token] = current_price(debt_token.address)

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

        init_collateral_usd = debt_token.total_supply # supply of token


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

def get_amount_out(amount, loan_token, collateral_token):
  method = "get"
  apiUrl = "https://api.1inch.dev/swap/v5.2/1/quote"
  requestOptions = {
            "headers": 
                {"Authorization": os.environ['ONEINCH_API_KEY']},
            "body": {},
            "params": {
                "src": loan_token,
                "dst": collateral_token,
                "amount": f"{amount}",
            }
        }
  # Prepare request components
  headers = requestOptions.get("headers", {})
  body = requestOptions.get("body", {})
  params = requestOptions.get("params", {})

  response = requests.get(apiUrl, headers=headers, params=params)
  amountOut = int(response.json()['toAmount'])
  return amountOut

def get_max_supply_cap(collateral_token_address, loan_token_address, lltv):
    # TODO : Add the case for RWA backed assets 

    # Parameters for the simulation
    time.sleep(N_SLEEP_SEC)
    collateral_token = token_from_symbol_or_address(collateral_token_address)
    time.sleep(N_SLEEP_SEC)
    debt_token = token_from_symbol_or_address(loan_token_address)

    tokens = [collateral_token, debt_token]
    prices = {}

    time.sleep(N_SLEEP_SEC)
    prices[collateral_token] = current_price(collateral_token.address)
    time.sleep(N_SLEEP_SEC)
    prices[debt_token] = current_price(debt_token.address)


    if collateral_token.symbol[0] == 'b':
        # RWA Backed asset case

        ticker = collateral_token.symbol[1:] + '.L' # Yahoo finance ticker

        # Last year historical prices of RWA
        bond_ticker = yf.Ticker(ticker)
        df_prices = bond_ticker.history(period="max")
        df_prices.sort_index(inplace=True)
        df_prices.dropna(inplace=True)

        # Current collateral price = last close price
        collat_price = df_prices.iloc[-1]['Close']
        debt_price = 1.

        # Max drawdown computation
        # 99% Worst drawdown for NB_FULL_LIQUIDATION_DAYS (which is equal to the time it takes to fully liquidate a position)
        NB_FULL_LIQUIDATION_DAYS = 30
        df_prices['drawdown'] = (df_prices['Close'].rolling(NB_FULL_LIQUIDATION_DAYS).max() - df_prices['Close']) / df_prices['Close'].rolling(NB_FULL_LIQUIDATION_DAYS).max()
        p = 0.99
        max_drawdown = df_prices['drawdown'].quantile(p)

        # Pct_decrease computation
        # average drawdown over NB_LIQUIDATION_DAYS (which is equal to the timestep for one liquidation)
        NB_LIQUIDATION_DAYS = 3
        pct_decrease = ((df_prices['Close'].rolling(NB_LIQUIDATION_DAYS).max() - df_prices['Close']) / df_prices['Close'].rolling(NB_LIQUIDATION_DAYS).max()).mean()

        # Repay amount, assumed repayment amount is 100k USD (no flashloans available)
        # this is just a guess for what should be the average repayment amount by a liquidator
        repay_amount_usd = 100_000 # no flashloan for RWA

        max_collateral_usd = debt_token.total_supply # supply of token
        N_POINTS = 10000

        for collateral_amount_usd in np.linspace(0, max_collateral_usd, N_POINTS):
            liq_bonus = compute_liquidation_incentive(M, BETA, lltv)
            insolvency = simulate_insolvency(
                initial_collateral_usd=collateral_amount_usd,
                collateral_price=collat_price,
                debt_price=debt_price,
                lltv=lltv,
                repay_amount_usd=repay_amount_usd,
                liq_bonus=liq_bonus,
                max_drawdown=max_drawdown,
                pct_decrease=pct_decrease,
            )

            # Note: for the purpose of this tool, we are just interested in the largest
            # LLTV that results in 0 insolvent debt.
            if insolvency > 0:
                break        
        return collateral_amount_usd * lltv / collat_price
    
    else:
        # Calculate critical LTV for the loan token
        liquidation_incentive = min(M, 1 / (BETA * lltv + (1 - BETA)) - 1)
        critical_ltv = 1 / (1 + liquidation_incentive)
        price_jump = lltv / critical_ltv * 0.95 # 5% discount

        # Calculate corresponding volume for price impact
        amount = 1 * 10**debt_token.decimals
        amountOut = get_amount_out(amount, loan_token_address, collateral_token_address) / 10**collateral_token.decimals
        initial_price = amountOut / amount
        time.sleep(1.5)

        # Binary search for the supply cap
        left = 0
        right = debt_token.total_supply # total supply

        N_iter = 15
        for i in range(N_iter):
            mid = (left + right) / 2
            amount = int(mid * 10**debt_token.decimals)
            amountOut = get_amount_out(amount, loan_token_address, collateral_token_address) / 10**collateral_token.decimals
            price_ratio = amountOut / amount / initial_price
            if price_ratio > price_jump:
                left = mid
            else:
                right = mid
            
            # Sleep to prevent API spamming
            time.sleep(1.5)
            
        cap_amount = (left + right) / 2
        return cap_amount

            


if __name__ == '__main__':
    collateral_token = "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0" # wstETH
    loan_token = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2" # WETH
    lltv = 0.94


    max_lltv = get_max_lltv(collateral_token, loan_token)
    max_cap = get_max_supply_cap(collateral_token, loan_token, lltv)
    print(max_lltv, max_cap)


    collateral_token = "0xCA30c93B02514f86d5C86a6e375E3A330B435Fb5" # IB01
    loan_token = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48" # WETH
    lltv = 0.94

    max_lltv = get_max_lltv(collateral_token, loan_token)
    max_cap = get_max_supply_cap(collateral_token, loan_token, lltv)
    print(max_lltv, max_cap)