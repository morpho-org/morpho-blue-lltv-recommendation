import datetime
import os
import time
from abc import ABC
from abc import abstractproperty
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import pandas as pd
import requests

from .constants import ADDRESS_MAP
from .constants import SYMBOL_MAP
from .logger import get_logger
from .tokens import Token

log = get_logger(__name__)


def ms_to_dt(ms: float) -> datetime.datetime:
    timestamp_seconds = ms / 1000
    dt_object = datetime.datetime.fromtimestamp(timestamp_seconds)
    return dt_object.strftime("%Y-%m-%d")


@dataclass
class API(ABC):
    def __init__(self):
        self._last_call_time = 0  # time of last request
        self._calls_in_period = (
            0  # number of api requests in the current period
        )

    @abstractproperty
    def requests_per_minute(self) -> float:
        raise NotImplementedError

    def calculate_wait_time(self) -> float:
        dt = time.time() - self._last_call_time
        period_length = 60

        if self._calls_in_period >= self.requests_per_minute:
            return period_length
        elif (
            dt > period_length
            or self._calls_in_period < self.requests_per_minute
        ):
            # no need to wait since the elapsed time is long enough
            return 0

    def make_request(self, **request_kwargs) -> requests.request:
        """
        This function handles making the api request while potentially
        sleeping to avoid hitting the API request limit.
        """
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
        log.debug(f"Sent get request to url: {request_kwargs['url']}")
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
            CoinGecko.PRO_URL
            if self.get_coingecko_api_key()
            else CoinGecko.PUBLIC_URL
        )

    @property
    def requests_per_minute(self):
        """
        Coingecko's advertised public api rate limit is 10-30 calls per minute.
        Source: https://www.coingecko.com/en/api/pricing#:~:text=Our%20Public%20API%20has%20a,the%20next%201%20minute%20window.
        """
        return 500 if self.get_coingecko_api_key() else 10

    def token_info(self, address: str, chain: str = "ethereum"):
        chain_id = 1 if chain == "ethereum" else None
        url = f"{self.api_url}/coins/{chain_id}/contract/{address}"
        response = self.make_request(url=url)
        return response.json()

    def current_price(
        self, address: str, chain: str = "ethereum", currency="usd"
    ):
        address = address.lower()
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
        # results in the response json come in lists of timestamp, field value
        res_js["date"] = [ms_to_dt(t) for t, _ in res_js["prices"]]
        res_js["prices"] = [x for _, x in res_js["prices"]]
        res_js["market_caps"] = [x for _, x in res_js["market_caps"]]
        res_js["total_volumes"] = [x for _, x in res_js["total_volumes"]]

        df = pd.DataFrame(res_js).set_index("date")
        return df

    def ohlc(self, cg_token_id: str, currency: str = "usd"):
        url = (
            f"{self.api_url}/coins/{cg_token_id}/ohlc?vs_currency=usd&days=max"
        )
        response = self.make_request(url=url)

        if not response.ok:
            response.raise_for_status()

        res = response.json()
        data = [[ms_to_dt(t), *x] for t, *x in res]
        df = pd.DataFrame(
            data, columns=["date", "Open", "High", "Low", "Close"]
        ).set_index("date")
        return df

    def get_coingecko_api_key(self) -> Optional[str]:
        """
        If users have a pro CoinGecko api key, they can use it by setting
        setting the `COINGECKO_API_KEY` env var to their key.
        """
        return os.environ.get("COINGECKO_API_KEY")


def token_from_symbol_or_address(input_str: str) -> Token:
    """
    Creates a Token object from an input symbol or address.
    This assumes that the token is an erc20 on ethereum.

    input_str: str representing a token symbol or token address
    """
    if "0x" in input_str and len(input_str) == 42:
        if input_str in ADDRESS_MAP:
            return ADDRESS_MAP[input_str]
        try:
            token_info = CoinGecko().token_info(input_str)
            symbol = token_info["symbol"]
            decimals = token_info["detail_platforms"]["ethereum"][
                "decimal_place"
            ]
            name = token_info["name"]
            return Token(
                symbol=symbol,
                decimals=decimals,
                address=input_str,
                coingecko_id=name,
            )
        except Exception as e:
            raise ValueError(
                f"Could not find token for {input_str}. Exception: {e}"
            )
    else:
        if input_str not in SYMBOL_MAP:
            raise ValueError(
                "Unsupported token symbol. "
                + "Please manually add the token to `tokens.py` before rerunning the script"
            )
        return SYMBOL_MAP[input_str]


# We cache these values so that subsequent calls do not send CoinGecko API requests
@lru_cache
def current_price(addr: str) -> float:
    return CoinGecko().current_price(addr)
