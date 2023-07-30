import time
import json
import requests

def get_impact(token_in: str, token_out: str, token_in_decimals: int, amount: float, quality: str = "optimal"):
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

if __name__ == '__main__':
    weth = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
    usdc = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    amount = 10_000

    st = time.time()
    impact = get_impact(weth, usdc, 18, amount, "optimal")
    end = time.time()
    print(impact['quote']['buyAmount'])
    print("Cow swap time: {:.3f}".format(end - st))


    st = time.time()
    impact = get_impact(weth, usdc, 18, amount, "fast")
    end = time.time()
    print(impact['quote']['buyAmount'])
    print("Cow swap time: {:.3f}".format(end - st))
