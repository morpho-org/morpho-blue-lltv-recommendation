import time

import requests

from .coingecko import CoinGecko
from .coingecko import current_price


MAX_ITERS = 20


def cowswap_query(
    token_in: str,
    token_out: str,
    token_in_decimals: int,
    amount: float,
    quality: str = "optimal",
) -> requests.Request:
    """
    Returns the raw cowswap API response for a token swap from {token_in} to {token_out}
    of size {amount}.

    token_in: str, token address of the sell token
    token_out: str, token address of the buy token
    token_in_decimals: int, number of decimals of token_in
    amount: float, number of tokens of token_in to be sold
    quality: str (optimal or fast)

    """
    url = "https://api.cow.fi/mainnet/api/v1/quote"
    params = {
        "sellToken": token_in,
        "buyToken": token_out,
        "receiver": "0x0000000000000000000000000000000000000000",
        "partiallyFillable": False,
        "sellAmountBeforeFee": str(int(amount * 10**token_in_decimals)),
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


def price_impact_size(
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
        response = cowswap_query(
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
