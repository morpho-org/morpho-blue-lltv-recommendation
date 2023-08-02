class Token:
    def __init__(self, address: str, decimals: int, coingecko_id: str, symbol: str = ""):
        self.address = address
        self.decimals = decimals
        self.coingecko_id = coingecko_id
        self.symbol = symbol

    def __repr__(self):
        return f"Token(address='{self.address}', decimals={self.decimals}, coingecko_id='{self.coingecko_id}', symbol='{self.symbol}')"

# TODO: expand token set
TOKENS = [
    Token(address='0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9', decimals=18, coingecko_id='aave', symbol='aave'),
    Token(address='0x111111111117dc0aa78b770fa6a738034120c302', decimals=18, coingecko_id='1inch', symbol='1inch'),
    Token(address='0xd33526068d116ce69f19a9ee46f0bd304f21a51f', decimals=18, coingecko_id='rocket-pool', symbol='rpl'),
    Token(address='0x514910771af9ca656af840dff83e8264ecf986ca', decimals=18, coingecko_id='chainlink', symbol='link'),
    Token(address='0x2260fac5e5542a773aa44fbcfedf7c193bc2c599', decimals=8, coingecko_id='wrapped-bitcoin', symbol='wbtc'),
    Token(address='0xae78736cd615f374d3085123a210448e74fc6393', decimals=18, coingecko_id='rocket-pool-eth', symbol='reth'),
    Token(address='0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2', decimals=18, coingecko_id='weth', symbol='weth'),
    Token(address='0xbe9895146f7af43049ca1c1ae358b0541ea49704', decimals=18, coingecko_id='coinbase-wrapped-staked-eth', symbol='cbeth'),
    Token(address='0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0', decimals=18, coingecko_id='wrapped-steth', symbol='wsteth'),
    Token(address='0xc011a73ee8576fb46f5e1c5751ca3b9fe0af2a6f', decimals=18, coingecko_id='havven', symbol='snx'),
    Token(address='0xba100000625a3754423978a60c9317c58a424e3d', decimals=18, coingecko_id='balancer', symbol='bal'),
    Token(address='0xc18360217d8f7ab5e7c516566761ea12ce7f9d72', decimals=18, coingecko_id='ethereum-name-service', symbol='ens'),
    Token(address='0x1f9840a85d5af5bf1d1762f925bdaddc4201f984', decimals=18, coingecko_id='uniswap', symbol='uni'),
    Token(address='0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2', decimals=18, coingecko_id='maker', symbol='mkr'),
    Token(address='0x5a98fcbea516cf06857215779fd812ca3bef1b32', decimals=18, coingecko_id='lido-dao', symbol='ldo'),
    Token(address='0xd533a949740bb3306d119cc777fa900ba034cd52', decimals=18, coingecko_id='curve-dao-token', symbol='crv'),
    Token(address='0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48', decimals=6, coingecko_id='usd-coin', symbol='usdc'),
    Token(address='0xdac17f958d2ee523a2206206994597c13d831ec7', decimals=6, coingecko_id='tether', symbol='usdt')
]

ADDRESS_MAP = {
    t.address: t for t in TOKENS
}

SYMBOL_MAP = {
    t.symbol: t for t in TOKENS
}

ID_MAP = {
    t.coingecko_id: t for t in TOKENS
}

STABLES = {
    SYMBOL_MAP['usdc'], SYMBOL_MAP['usdt']
}
