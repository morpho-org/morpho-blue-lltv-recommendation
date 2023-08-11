import json
import time

import requests
from coingecko import CoinGecko
from tokens import Tokens


def get_cowswap(
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


def get_impact(
    token_in: str,
    token_out: str,
    token_in_decimals: int,
    token_out_decimals: int,
    amount: float,
    quality: str = "optimal",
) -> float:
    """
    Returns the price impact of a token swap of size {amount} from {token_in} to
    {token_out}.
    The price impact of a swap is computed as follows:
    price impact = 1 - (amount received in USD / amount paid in USD)

    token_in: str, token address of the sell token
    token_out: str, token address of the buy token
    token_in_decimals: int, number of decimals of token_in
    token_out_decimals: int, number of decimals of token_out
    amount: float, number of tokens of token_in to be sold
    quality: str (optimal or fast)
    """
    cg = CoinGecko()
    spot_in = cg.current_price(token_in)
    spot_out = cg.current_price(token_out)

    response = get_cowswap(token_in, token_out, token_in_decimals, amount, quality)
    amount_in_usd = (
        float(response["quote"]["sellAmount"]) / (10**token_in_decimals) * spot_in
    )
    amount_out_usd = (
        float(response["quote"]["buyAmount"]) / (10**token_out_decimals) * spot_out
    )
    price_impact = 1 - float(amount_out_usd / amount_in_usd)
    return price_impact


if __name__ == "__main__":
    weth = Tokens.WETH
    usdc = Tokens.USDC
    amount = 5000

    cg = CoinGecko()
    weth_spot = cg.current_price(weth.address)
    res = get_cowswap(weth.address, usdc.address, weth.decimals, amount, "fast")
    amount_in = weth_spot * float(res["quote"]["sellAmount"]) / 1e18
    amount_out = float(res["quote"]["buyAmount"]) / 1e6
    price_impact = 1 - (amount_out / amount_in)

    print(
        "Swap size of {:.2f} | Sell price: {:.2f} | Amount received: {:.2f}".format(
            int(res["quote"]["sellAmount"]) / 10**weth.decimals,
            int(res["quote"]["sellAmount"]) / 10**weth.decimals * weth_spot,
            int(res["quote"]["buyAmount"]) / 10**usdc.decimals,
        )
    )
    print("Price impact: {:.3f}".format(price_impact))
