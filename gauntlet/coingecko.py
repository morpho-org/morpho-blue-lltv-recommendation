import datetime
import os
import time
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import requests
from tokens import Tokens
import logger

log = logger.get_logger(__name__)

def ms_to_dt(ms):
    timestamp_seconds = ms / 1000
    dt_object = datetime.datetime.fromtimestamp(timestamp_seconds)
    return dt_object.strftime("%Y-%m-%d")


@dataclass
class API(ABC):
    def __init__(self):
        self._last_call_time = 0  # time of last request
        self._calls_in_period = 0 # number of api requests in the current period

    @property
    @abstractmethod
    def requests_per_minute(self, request) -> float:
        raise NotImplementedError

    def calculate_wait_time(self) -> float:
        dt = time.time() - self._last_call_time
        period_length = 60

        if self._calls_in_period >= self.requests_per_minute:
            return period_length
        elif dt > period_length or self._calls_in_period < self.requests_per_minute:
            # no need to wait since the elapsed time is long enough
            return 0

    def make_request(self, **request_kwargs) -> requests.request:
        '''
        This function handles making the api request while potentially
        sleeping to avoid hitting the API request limit.
        '''
        wt = self.calculate_wait_time()

        if wt > 0:
            # Obey the rate limit
            log.debug(f"Rate limit hit. Sleeping for {wt:.3f}s ...")
            time.sleep(wt)
            self._last_call_time = time.time()
            # reset the counter
            self._calls_in_period = 0

        self._calls_in_period += 1
        header = self.get_header()
        if header:
            request_kwargs["headers"] = header

        response = requests.get(**request_kwargs)
        if not response.ok:
            response.raise_for_status()

        return response

    def get_header(self) -> dict[str, str]:
        return {}


class CoinGecko(API):
    CHAIN_IDS = {"ethereum": 1}
    PUBLIC_URL = "https://api.coingecko.com/api/v3"
    PRO_URL = "https://pro-api.coingecko.com/api/v3"

    def get_header(self):
        return {"x-cg-pro-api-key": self.get_coingecko_api_key()}

    @property
    def api_url(self):
        return (
            CoinGecko.PRO_URL if self.get_coingecko_api_key() else CoinGecko.PUBLIC_URL
        )

    @property
    def requests_per_minute(self):
        """
        Coingecko's advertised public api rate limit is 10-30 calls per minute.
        Source: https://www.coingecko.com/en/api/pricing#:~:text=Our%20Public%20API%20has%20a,the%20next%201%20minute%20window.
        """
        if self.get_coingecko_api_key():
            return 500
        else:
            return 10

    def token_info(self, address: str, chain: str = "ethereum"):
        chain_id = 1 if chain == "ethereum" else None
        url = f"{self.api_url}/coins/{chain_id}/contract/{address}"
        response = self.make_request(url=url)
        return response.json()

    def current_price(self, address: str, chain: str = "ethereum", currency="usd"):
        url = f"{self.api_url}/simple/token_price/{chain}?contract_addresses={address}&vs_currencies={currency}"
        response = self.make_request(url=url)
        resp_js = response.json()
        return resp_js[address][currency]

    def market_chart(
        self,
        address: str,
        chain: str = "ethereum",
        interval: str = "daily",
        currency: str = "usd",
    ):
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

    def get_coingecko_api_key(self) -> Optional[str]:
        '''
        If users have a pro CoinGecko api key, they can use it by setting
        setting the `COINGECKO_API_KEY` env var to their key.
        '''
        return os.environ.get("COINGECKO_API_KEY")


if __name__ == "__main__":
    usdc = Tokens.USDC
    api = CoinGecko()
    results = []

    for tok in Tokens:
        price = api.current_price(tok.address)
        results.append(price)
        print(f"{len(results):2d} | Token: {tok.symbol:6s} | Spot price: {price:.2f}")

    info = api.token_info(usdc.address)
    market_chart = api.market_chart(usdc.address)
    ohlc = api.ohlc(usdc.coingecko_id)
