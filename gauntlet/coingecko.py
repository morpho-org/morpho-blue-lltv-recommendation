import time
import datetime
import json

import pandas as pd
import requests

CHAIN_IDS = {"ethereum": 1}


def ms_to_dt(ms):
    timestamp_seconds = ms / 1000
    dt_object = datetime.datetime.fromtimestamp(timestamp_seconds)
    return dt_object.strftime("%Y-%m-%d")


def coin_info(token_addr: str, chain_id: int = 1):
    url = f"https://api.coingecko.com/api/v3/coins/{chain_id}/contract/{token_addr}"
    response = requests.get(url)

    if not response.ok:
        response.raise_for_status()
    return response.json()


# TODO: fixed to ethereum for now
def get_current_price(addr: str, chain: str = "ethereum") -> float:
    url = f"https://api.coingecko.com/api/v3/simple/token_price/{chain}?contract_addresses={addr}&vs_currencies=usd"
    response = requests.get(url)
    resp_js = response.json()
    return resp_js[addr]["usd"]


def get_market_chart(chain: str, contract_address: str, interval: str):
    chain_id = CHAIN_IDS[chain]
    url = f"https://api.coingecko.com/api/v3/coins/{chain_id}/contract/{contract_address}/market_chart"
    params = {
        "vs_currency": "usd",
        "days": "max",
        "interval": interval,
    }
    response = requests.get(url, params=params)

    # Raise an exception if the request was unsuccessful
    if not response.ok:
        response.raise_for_status()

    # Otherwise, return the JSON data
    res_js = response.json()
    res_js["date"] = [ms_to_dt(x[0]) for x in res_js["prices"]]
    res_js["prices"] = [x[1] for x in res_js["prices"]]
    res_js["market_caps"] = [x[1] for x in res_js["market_caps"]]
    res_js["total_volumes"] = [x[1] for x in res_js["total_volumes"]]

    df = pd.DataFrame(res_js)
    df.set_index("date", inplace=True)
    return df


def get_ohlc(cg_token_id: str):
    """
    cg_token_id prob needs to be fetched from
    """
    url = f"https://api.coingecko.com/api/v3/coins/{cg_token_id}/ohlc?vs_currency=usd&days=max"
    response = requests.get(url)

    if not response.ok:
        response.raise_for_status()

    res = response.json()
    data = [[ms_to_dt(t), *x] for t, *x in res]
    df = pd.DataFrame(data, columns=["date", "open", "high", "low", "close"])
    df.set_index("date", inplace=True)
    return df


if __name__ == "__main__":
    rpl = "0xd33526068d116ce69f19a9ee46f0bd304f21a51f"
    rpl_info = coin_info(rpl, "ethereum")
    breakpoint()
    weth = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
    steth = "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84"
    wsteth = "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0"
    price = get_current_price(weth)
    steth_data = get_market_chart("ethereum", steth, "daily")
    time.sleep(2)
    weth_data = get_market_chart("ethereum", weth, "daily")
    time.sleep(2)
    wsteth_data = get_market_chart("ethereum", wsteth, "daily")
    weth_info = coin_info(weth, "ethereum")
    breakpoint()
