import time
import json
import requests
from coingecko import CoinGecko

def get_cowswap(token_in: str, token_out: str, token_in_decimals: int, amount: float, quality: str = "optimal"):
    url = "https://api.cow.fi/mainnet/api/v1/quote"
    params = {
        "sellToken": token_in,
        "buyToken": token_out,
        "receiver": "0x0000000000000000000000000000000000000000",
        "partiallyFillable": False,
        "sellAmountBeforeFee": str(
            int(amount * 10 ** token_in_decimals)
        ),
        "sellTokenBalance": "erc20",
        "buyTokenBalance": "erc20",
        "kind": "sell",
        "from": "0x0000000000000000000000000000000000000000",
        "priceQuality": quality,
        "onchainOrder": False,
        "validTo": int(time.time() + 60 * 60)
    }
    response = requests.post(url, json=params)
    return response.json()

def get_impact(token_in: str, token_out: str, token_in_decimals: int, token_out_decimals: int, amount: float, quality: str = "optimal"):
    cg = CoinGecko()
    spot_in = cg.current_price(token_in)
    spot_out = cg.current_price(token_out)

    response = get_cowswap(token_in, token_out, token_in_decimals, amount, quality)
    amount_in_usd = float(response['quote']['sellAmount']) / (10 ** token_in_decimals) * spot_in
    amount_out_usd = float(response['quote']['buyAmount']) / (10 ** token_out_decimals) * spot_out
    price_impact = 1 - float(amount_out_usd / amount_in_usd)
    return price_impact

if __name__ == '__main__':
    weth = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
    usdc = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    amount = 100_000

    cg = CoinGecko()
    weth_spot = cg.current_price(weth)
    print("weth spot: {}".format(weth_spot))
    st = time.time()
    res = get_cowswap(weth, usdc, 18, amount, "fast")
    end = time.time()
    amount_in = weth_spot * float(res['quote']['sellAmount']) / 1e18
    amount_out = float(res['quote']['buyAmount']) / 1e6
    price_impact = 1 - (amount_out / amount_in)

    print("Swap size of {} | Sell price: {:.2f} | Amount received: {}".format(
        int(res['quote']['sellAmount']) / 1e18,
        int(res['quote']['sellAmount']) / 1e18 * weth_spot,
        int(res['quote']['buyAmount']) / 1e6,
    ))
    print("Price impact: {:.3f}".format(
        price_impact
    ))
    print("Cow swap time: {:.3f}s".format(end - st))
