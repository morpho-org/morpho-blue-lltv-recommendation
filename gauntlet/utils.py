import datetime
from functools import lru_cache

from .coingecko import CoinGecko
from .cowswap import get_cowswap
from .logger import get_logger


log = get_logger(__name__)
MAX_ITERS = 20
CG = CoinGecko()


def compute_liquidation_incentive(m: float, beta: float, lltv: float) -> float:
    """
    Morpho Blue's proposed liquidation incentive formula
    m: float, a constant that determines the max liq incentive
    beta: float, constant
    lltv: float, liquidation loan to value parameter of the market
    """
    return min(m, (1 / (beta * lltv + (1 - beta))) - 1)


def ms_to_dt(ms) -> datetime.datetime:
    timestamp_seconds = ms / 1000
    dt_object = datetime.datetime.fromtimestamp(timestamp_seconds)
    return dt_object.strftime("%Y-%m-%d")


@lru_cache
def current_price(addr: str) -> float:
    return CG.current_price(addr)


def price_impact_size_cowswap(
    token_in: str,
    token_in_decimals: int,
    token_out: str,
    token_out_decimals: int,
    target_price_impact: float,
    rtol=5e-2,
    max_sz_usd=1_000_000_000,
) -> float:
    def cowswap_oracle(token_in: str, token_out: str, size: float):
        """
        token_in: address of the sell token
        token_out: address of the buy token
        size: amount of token_in to sell
        """
        response = get_cowswap(
            token_in, token_out, token_in_decimals, size, quality="optimal"
        )
        amount_in_usd = (
            float(response["quote"]["sellAmount"])
            / (10**token_in_decimals)
            * current_price(token_in)
        )
        amount_out_usd = (
            float(response["quote"]["buyAmount"])
            / (10**token_out_decimals)
            * current_price(token_out)
        )
        price_impact = 1 - float(amount_out_usd / amount_in_usd)
        return price_impact

    cg = CoinGecko()
    spot_in = cg.current_price(token_in)
    min_sz = 0
    max_sz = max_sz_usd / spot_in
    iters = 0
    price_impact = 1

    while (
        abs(1 - (price_impact / target_price_impact)) > rtol
        and iters < MAX_ITERS
    ):
        mid = (max_sz + min_sz) / 2.0
        price_impact = cowswap_oracle(token_in, token_out, mid)

        if price_impact < target_price_impact:
            min_sz = mid
        else:
            max_sz = mid

        log.debug(
            f"{iters:2d} | x = {mid:.2f} | price impact: {price_impact:.4f} | swap total: ${mid * spot_in/1e6:.2f}mil"
        )
        iters += 1
    return (max_sz + min_sz) / 2.0
