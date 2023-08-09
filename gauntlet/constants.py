from tokens import Tokens

ADDRESS_MAP = {t.address: t for t in Tokens}

SYMBOL_MAP = {t.symbol: t for t in Tokens}

ID_MAP = {t.coingecko_id: t for t in Tokens}

STABLECOINS = [
    Tokens.USDC,
    Tokens.USDT,
    Tokens.DAI,
    Tokens.FRAX,
    Tokens.LUSD,
]
