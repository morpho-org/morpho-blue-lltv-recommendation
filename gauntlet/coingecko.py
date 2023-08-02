import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
import time
import datetime
import json

import pandas as pd
import requests

def get_coingecko_api_key():
    return os.environ.get("COINGECKO_API_KEY")

@dataclass
class API(ABC):
    def __init__(self):
        self._last_call_time = 0 # time since the Epoch as given by time.time()
        self._last_call_time = 0
        self._calls_in_period = 0

    @property
    @abstractmethod
    def requests_per_minute(self, request) -> float:
        raise NotImplemented

    @property
    def period_duration(self):
        return 60 / self.requests_per_minute

    def calculate_wait_time(self) -> float:
        dt = time.time() - self._last_call_time
        period_length = 60 / self.requests_per_minute

        if self._calls_in_period >= self.requests_per_minute:
            return period_length
        elif dt > period_length or self._calls_in_period < self.requests_per_minute:
            # no need to wait since the elapsed time is long enough
            return 0
        # else:
        # not sure

    def make_request(self, **request_kwargs) -> requests.request:
        wt = self.calculate_wait_time()

        if wt > 0:
            time.sleep(wt) # Obey the rate limit
            self._last_call_time = time.time()
            self._calls_in_period = 0

        self._calls_in_period += 1
        header =  {"x-cg-pro-api-key": get_coingecko_api_key()}
        request_kwargs = {**request_kwargs, "headers": header}
        response = requests.get(**request_kwargs)
        if not response.ok:
            response.raise_for_status()

        return response

    def backoff(self):
        time.sleep(self.period)

class CoinGecko(API):
    CHAIN_IDS = {"ethereum": 1}
    PUBLIC_URL = "https://api.coingecko.com/api/v3"
    PRO_URL = "https://pro-api.coingecko.com/api/v3"

    @property
    def api_url(self):
        return CoinGecko.PRO_URL if get_coingecko_api_key() else CoinGecko.PUBLIC_URL

    @property
    def requests_per_minute(self):
        '''
        Coingecko's advertised public api rate limit is 10-30 calls per minute.
        Source: https://www.coingecko.com/en/api/pricing#:~:text=Our%20Public%20API%20has%20a,the%20next%201%20minute%20window.
        '''
        if get_coingecko_api_key():
            return 500
        else:
            return 10

    def token_info(self, address: str, chain: str = "ethereum"):
        chain_id = 1 if chain == 'ethereum' else None
        url = f"{self.api_url}/coins/{chain_id}/contract/{address}"
        response = self.make_request(url=url)
        return response.json()

    def current_price(self, address: str, chain: str = "ethereum", currency='usd'):
        url = f"{self.api_url}/simple/token_price/{chain}?contract_addresses={address}&vs_currencies={currency}"
        response = self.make_request(url=url)
        resp_js = response.json()
        return resp_js[address][currency]

    def market_chart(self, address: str, chain: str = "ethereum", interval: str = "daily", currency: str = "usd"):
        chain_id = CoinGecko.CHAIN_IDS[chain]
        url = f"{self.api_url}/coins/{chain_id}/contract/{address}/market_chart"
        params = {
            "vs_currency": currency,
            "days": "max",
            "interval": interval,
        }
        response = self.make_request(url=url, params=params)
        if not response.ok:
            response.raise_for_status()

        res_js = response.json()
        res_js["date"] = [ms_to_dt(x[0]) for x in res_js["prices"]]
        res_js["prices"] = [x[1] for x in res_js["prices"]]
        res_js["market_caps"] = [x[1] for x in res_js["market_caps"]]
        res_js["total_volumes"] = [x[1] for x in res_js["total_volumes"]]

        df = pd.DataFrame(res_js)
        df.set_index("date", inplace=True)
        return df


    def ohlc(self, cg_token_id: str, currency: str = "usd"):
        url = f"{self.api_url}/coins/{cg_token_id}/ohlc?vs_currency=usd&days=max"
        response = self.make_request(url=url)

        if not response.ok:
            response.raise_for_status()

        res = response.json()
        data = [[ms_to_dt(t), *x] for t, *x in res]
        df = pd.DataFrame(data, columns=["date", "open", "high", "low", "close"])
        df.set_index("date", inplace=True)
        return df


def ms_to_dt(ms):
    timestamp_seconds = ms / 1000
    dt_object = datetime.datetime.fromtimestamp(timestamp_seconds)
    return dt_object.strftime("%Y-%m-%d")


if __name__ == "__main__":
    usdc = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    usdt = "0xdac17f958d2ee523a2206206994597c13d831ec7"
    weth = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
    steth = "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84"
    wsteth = "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0"

    api = CoinGecko()
    for i in range(10):
        st = time.time()
        info = api.token_info(usdc)
        print("i = {} | Time for token info call: {:.2f}s".format(i, time.time() - st))

    price = api.current_price(usdc)
    market_chart = api.market_chart(usdc)
    ohlc = api.ohlc("usd-coin")
