import streamlit as st

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
from gauntlet.tokens import Tokens

st.title("Gauntlet LLTV recommandation algorithm")
st.text("Enter collateral and debt token symbols to get LLTV recommendation")

def print_optimal_lltv(collateral_symbol, debt_symbol):

    ## Simulation parameters
    update_cache = False
    use_cache = False
    m = 0.15
    beta = 0.3
    min_liq_bonus = 0.005 
    pct_decrease = 0.005

    collateral_token = token_from_symbol_or_address(collateral_symbol)
    debt_token = token_from_symbol_or_address(debt_symbol)

    tokens = [collateral_token, debt_token]
    prices = {t: current_price(t.address) for t in tokens}
    price_impacts = get_price_impacts(
        tokens,
        impacts=[0.005, 0.25],
        update_cache=update_cache,
        use_cache=use_cache,
    )
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

    lltvs = np.arange(0.01, 1.0, 0.01)
    opt_lltv = None
    opt_li = None
    for ltv in lltvs:
        liq_bonus = max(
            compute_liquidation_incentive(m, beta, ltv),
            min_liq_bonus,
        )
        insolvency = simulate_insolvency(
            initial_collateral_usd=init_collateral_usd,
            collateral_price=prices.get(collateral_token),
            debt_price=prices.get(debt_token),
            lltv=ltv,
            repay_amount_usd=repay_amount_usd,
            liq_bonus=liq_bonus,
            max_drawdown=max_drawdown,
            pct_decrease=pct_decrease,
        )

        # Note: for the purpose of this tool, we are just interested in the largest
        # LLTV that results in 0 insolvent debt.
        if insolvency > 0:
            break

    opt_lltv = ltv
    opt_li = liq_bonus

    st.text(f"Optimal LLTV: {opt_lltv*100:.2f}%")
    st.text(f"Liquidation Incentive: {opt_li*100:.2f}%")


tokens = [token.symbol for token in Tokens]
print(tokens)
# radio button
collateral_symbol = st.selectbox("Collateral token symbol", tokens)
debt_symbol = st.selectbox("Debt token symbol", tokens)
submit_button = st.button("Submit (will take 1 minute)", on_click=print_optimal_lltv, args=(collateral_symbol.lower(), debt_symbol.lower()))

