from pathlib import Path

from .tokens import Tokens

TOL = 1e-4
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

LARGE_CAPS = {Tokens.WETH, Tokens.WSTETH, Tokens.RETH, Tokens.WBTC}
BLUE_CHIPS = LARGE_CAPS.union(set(STABLECOINS))
SMALL_CAPS = {t for t in Tokens if t not in STABLECOINS and t not in LARGE_CAPS}
PRICE_IMPACT_JSON_PATH = Path(__file__).parent.parent / "data/swap_sizes.json"
DRAWDOWN_PKL_PATH = Path(__file__).parent.parent / "data/pairwise_drawdowns.pkl"


# Default guardrail parameters for the initial position size and drawdown
# These values can be increased to yield a more conservative LLTV recommendation
LARGE_CAP_MIN_WHALE_POS = 200_000_000
SMALL_CAP_MIN_WHALE_POS = 50_000_000
LARGE_CAP_DRAWDOWN = 0.4
DEFAULT_DRAWDOWN = 0.6

M = 0.15
BETA = 0.3