import json
from decimal import Decimal

import requests

from coingecko import get_current_price


def to_decimals(decimals: int, amount: float) -> float:
    return int(Decimal(amount) * Decimal(10) ** Decimal(decimals))


def get_swap_route(
    chain: str,
    token_in: str,
    token_out: str,
    token_in_decimals: int,
    amount_in_base_unit: float,
    save_gas: int = 0,
):
    amount_decimals = to_decimals(token_in_decimals, amount_in_base_unit)
    url = f"https://aggregator-api.kyberswap.com/{chain}/api/v1/routes"
    params = {
        "tokenIn": token_in,
        "tokenOut": token_out,
        "amountIn": amount_decimals,
        "saveGas": save_gas,
    }
    response = requests.get(url, params=params)

    if not response.ok:
        response.raise_for_status()

    return response.json()


def get_swap_route_usd(
    chain: str,
    token_in: str,
    token_out: str,
    token_in_decimals: int,
    amount_in_usd: float,
    save_gas: int = 0,
):
    in_price = get_current_price(token_in, chain)
    amount_in_base = amount_in_usd / in_price

    return get_swap_route(
        chain, token_in, token_out, token_in_decimals, amount_in_base, save_gas
    )


if __name__ == "__main__":
    chain = "ethereum"
    weth = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
    usdc = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    amount = 10_000_000
    route = get_swap_route_usd(chain, weth, usdc, 18, amount)
    print(route["data"]["routeSummary"])
