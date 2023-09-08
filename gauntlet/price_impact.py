import time

import requests

from .coingecko import CoinGecko
from .coingecko import current_price
from .logger import get_logger
from .tokens import Token

log = get_logger(__name__)
MAX_ITERS = 20


def cowswap_query(
    token_in: Token,
    token_out: Token,
    amount: float,
    quality: str = "optimal",
) -> requests.Request:
    """
    Returns the raw cowswap API response for a token swap from {token_in} to {token_out}
    of size {amount}.

    token_in: Token, token object representing the sell token
    token_out: Token, token object representing the buy token
    amount: float, number of tokens of token_in to be sold
    quality: str (optimal or fast)

    """
    url = "https://api.cow.fi/mainnet/api/v1/quote"
    params = {
        "sellToken": token_in.address,
        "buyToken": token_out.address,
        "receiver": "0x0000000000000000000000000000000000000000",
        "partiallyFillable": False,
        "sellAmountBeforeFee": str(int(amount * 10**token_in.decimals)),
        "sellTokenBalance": "erc20",
        "buyTokenBalance": "erc20",
        "kind": "sell",
        "from": "0x0000000000000000000000000000000000000000",
        "priceQuality": quality,
        "onchainOrder": False,
        "validTo": int(time.time() + 60 * 60),
    }
    response = requests.post(url, json=params)
    return response.json()


def cowswap_price_impact(
    token_in: Token, token_out: Token, size: float
) -> float:
    """
    token_in: address of the sell token
    token_out: address of the buy token
    size: amount of token_in to sell

    Returns: price impact of a swap of {size} from token_in to token_out

    Sometimes cowswap returns incorrect results. It is worth double checking
    the price impact numbers against other DEX aggregators like 1inch.
    """
    response = cowswap_query(token_in, token_out, size, quality="fast")
    amount_in_usd = (
        float(response["quote"]["sellAmount"])
        / (10**token_in.decimals)
        * current_price(token_in.address)
    )
    amount_out_usd = (
        float(response["quote"]["buyAmount"])
        / (10**token_out.decimals)
        * current_price(token_out.address)
    )
    price_impact = 1 - float(amount_out_usd / amount_in_usd)
    return price_impact


def price_impact_size(
    token_in: Token,
    token_out: Token,
    target_price_impact: float,
    rtol=5e-2,
    max_sz_usd=1_000_000_000,
) -> float:
    """
    Computes the number of token_in necessary to get the target_price_impact
    when swapping token_in for token_out.

    token_in: Token object to swap out of
    token_out: Token object to swap into of
    target_price_impact: float
    rtol: float, relative tolerance
    max_sz_usd: float, upper bound for the amount of token_in necessary
        to generate the given target_price_impact

    Returns: float, number of tokens necessary to get the desired
        target_price_impact.
    """
    cg = CoinGecko()
    spot_in = cg.current_price(token_in.address)
    min_sz = 0
    max_sz = max_sz_usd / spot_in
    iters = 0
    price_impact = 1

    log.info(
        f"Computing size of swap price impact of {target_price_impact:.3f} for {token_in.symbol} -> {token_out.symbol}"
    )
    while (
        abs(1 - (price_impact / target_price_impact)) > rtol
        and iters < MAX_ITERS
    ):
        mid = (max_sz + min_sz) / 2.0
        price_impact = cowswap_price_impact(token_in, token_out, mid)

        if price_impact < target_price_impact:
            min_sz = mid
        else:
            max_sz = mid

        log.info(
            f"{iters:2d} | {token_in.symbol:6s} | swap size = {mid:.2f} | price impact: {price_impact:.4f} | swap total: ${mid * spot_in/1e6:.2f}mil"
        )
        iters += 1

    return (max_sz + min_sz) / 2.0


def price_impact_size_approximate(
    token_in: str,
    token_in_decimals: int,
    token_out: str,
    token_out_decimals: int,
    target_price_impact: float,
    rtol=5e-2,
    max_sz_usd=1_000_000_000,
):
    """
    Compute approximate price impact sizes for a token_in to token_out swap.
    We approximate the price impact size by querying the price impacts for
    a few swap sizes and fitting a polynomial curve to the resulting
    (swap size, price impact) pairs.
    """
    return 0
