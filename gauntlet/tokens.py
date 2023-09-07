from enum import Enum
from typing import NamedTuple

class Token(NamedTuple):
    symbol: str
    address: str
    decimals: int
    coingecko_id: str


class Tokens(Token, Enum):
    AAVE = Token("aave", '0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9', 18, 'aave')
    ONEINCH = Token(symbol="1inch", address='0x111111111117dc0aa78b770fa6a738034120c302', decimals=18, coingecko_id='1inch')
    RPL = Token(symbol="rpl", address='0xd33526068d116ce69f19a9ee46f0bd304f21a51f', decimals=18, coingecko_id='rocket-pool')
    LINK = Token(symbol="link", address='0x514910771af9ca656af840dff83e8264ecf986ca', decimals=18, coingecko_id='chainlink')
    WBTC = Token(symbol="wbtc", address='0x2260fac5e5542a773aa44fbcfedf7c193bc2c599', decimals=8, coingecko_id='wrapped-bitcoin')
    RETH = Token(symbol="reth", address='0xae78736cd615f374d3085123a210448e74fc6393', decimals=18, coingecko_id='rocket-pool-eth')
    WETH = Token(symbol="weth", address='0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2', decimals=18, coingecko_id='weth')
    CBETH = Token(symbol="cbeth", address='0xbe9895146f7af43049ca1c1ae358b0541ea49704', decimals=18, coingecko_id='coinbase-wrapped-staked-eth')
    WSTETH = Token(symbol="wsteth", address='0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0', decimals=18, coingecko_id='wrapped-steth')
    SNX = Token(symbol="snx", address='0xc011a73ee8576fb46f5e1c5751ca3b9fe0af2a6f', decimals=18, coingecko_id='havven')
    BAL = Token(symbol="bal", address='0xba100000625a3754423978a60c9317c58a424e3d', decimals=18, coingecko_id='balancer')
    ENS = Token(symbol="ens", address='0xc18360217d8f7ab5e7c516566761ea12ce7f9d72', decimals=18, coingecko_id='ethereum-name-service')
    UNI = Token(symbol="uni", address='0x1f9840a85d5af5bf1d1762f925bdaddc4201f984', decimals=18, coingecko_id='uniswap')
    MKR = Token(symbol="mkr", address='0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2', decimals=18, coingecko_id='maker')
    LDO = Token(symbol="ldo", address='0x5a98fcbea516cf06857215779fd812ca3bef1b32', decimals=18, coingecko_id='lido-dao')
    CRV = Token(symbol="crv", address='0xd533a949740bb3306d119cc777fa900ba034cd52', decimals=18, coingecko_id='curve-dao-token')
    USDC = Token(symbol="usdc", address='0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48', decimals=6, coingecko_id='usd-coin')
    USDT = Token(symbol="usdt", address='0xdac17f958d2ee523a2206206994597c13d831ec7', decimals=6, coingecko_id='tether')
    DAI = Token(symbol="dai", address="0x6b175474e89094c44da98b954eedeac495271d0f", decimals=18, coingecko_id="dai")
    LUSD = Token(symbol="lusd", address="0x5f98805a4e8be255a32880fdec7f6728c6568ba0", decimals=18, coingecko_id="liquity-usd")
    FRAX = Token(symbol="frax", address="0x853d955acef822db058eb8505911ed77f175b99e", decimals=18, coingecko_id="frax")
