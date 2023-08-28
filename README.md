# Morpho Blue Risk Tool 
Gauntlet has developed a risk tool to allow potential lenders to Morpho Blue decide on a LLTV that suits their risk appetite.

### Methodology
The risk tool conducts a simulation to evaluate the amount of bad debt within a given LLTV bucket for a particular collateral/borrow market. 

1. **Concentrated Borrow Position**

The simulation begins with the assumption of one borrower holding a concentrated position.
This initial collateral position size is determined based on various factors about the asset. In the current state of the tool, we set this position size slightly differently based on the specific lending market under consideration:
- for larger market cap token markets: the larger of $200 million, the size of a 25% price impact sell order
- for smaller market cap token markets: the larger of $50 million, the size of a 25% price impact sell order

We assume that the borrower takes out as much loan as the input LLTV allows (ex: if the LLTV under consideration is 0.80, then the simulation sets the borrow amount to be 80% of the initial collateral).

2. **Simulation Time Step**

After we have initialized the concentrated borrow position, we simulate the following:
- a constant price decrease: At each time step, a constant price decrease (0.5%) is applied to the collateral asset, up to a maximum drawdown.
This maximum drawdown is based on the max observed drawdown of the collateral asset's price ratio to the debt asset over a 1-month period. Other time periods may be used, but typically, the distribution remains relatively unchanged beyond a 2-week horizon.
- (potential) liquidation: if the borrower's debt to collateral ratio (LTV) is above their LLTV, we liquidate a portion of their position.
We repay an amount equal to the 0.5% price impact swap size of the collateral asset or borrow asset (whichever is smaller). For example, if a $100k swap incurs a 50bps price impact, then the liquidation amount is $100k). This amount remains fixed throughout the simulation.

3. **Simulation Termination**

The simulation stops when the borrower has no more collateral, no more debt, or we have reached the maximum iteration count. Any uncollateralized debt that remains at the end of the simulation is insolvent debt.

We run a simulation for potential LLTVs in the range $[0.01, 0.99]$. The tool/script will recommend the largest LLTV value that incurs zero bad debt.


### Parameters 
All the moving parts within this methodology are customizable by users, allowing them to experiment with different assumptions and adapt the simulation to specific scenarios. 

- `initial_collateral_usd`: The initial value of the whale collateral position, determined heuristically based on market cap size.
- `repay_amount_usd`: The amount of USD being repaid at each time step if the account is liquidatable.
- `min_liq_bonus`: The minimum liquidation bonus. Currently the liquidation incentive(bonus) is determined by the formula:
    $$LI  = \min\big(M, \frac{1}{\beta \times LLTV + (1-\beta)} - 1\big)
$$ 
    In some cases, the resulting liquidation incentive may be too small (ex: less than $1\%$), so we clamp to this given `min_liq_bonus`.
- `max_drawdown`: The largest allowed decrease in collateral value during the simulation.
- `pct_decrease`: Proportion to decrease the collateral price by at each time step. The default value is $0.005$.

## Dependencies

### Data Dependencies
The risk tool uses data from the following APIs:
- [**CoinGecko**](https://www.coingecko.com/en/api): for historical price data of the collateral and borrow assets of a lending market
- [**GeckoTerminal**](https://apiguide.geckoterminal.com/): for obtaining a rough estimate of the size of DEX liquidity pools containing a given asset
- [**CowSwap**](https://docs.cow.fi/off-chain-services/api): for price impact swap sizes (I.E.: what is the size of swap from token `X` to `Y` that incurs roughly 0.5% price impact?)

### Library Dependencies
The risk tool is intended to have minimal dependencies. The main software dependencies are standard libraries from the scientific computing/data science ecosystem such as Pandas, NumPy, and matplotlib. See the `requirements.txt` file in the repo for full details.

## Installation
Clone the respository and run the setup script like so:
```
git clone {repository url}
sh setup.sh
```
The setup script will create a python virtual environment and install the requirements.

## Usage

### Inputs
The risk tool is provided as a python script in this repository. To see all the parameters, run the following:
```bash
~$ python main.py --help
usage: main.py [-h] [-b BORROW] [-c COLLATERAL] [--pct_decrease PCT_DECREASE] [--initial_collateral_usd INITIAL_COLLATERAL_USD] [--collateral_price COLLATERAL_PRICE] [--debt_price DEBT_PRICE]
                   [--repay_amount_usd REPAY_AMOUNT_USD] [--max_drawdown MAX_DRAWDOWN] [--m M] [--beta BETA] [--min_liq_bonus MIN_LIQ_BONUS]

optional arguments:
  -h, --help            show this help message and exit
  -b BORROW, --borrow BORROW
                        symbol or address of the borrowable asset
  -c COLLATERAL, --collateral COLLATERAL
                        symbol or address of the collateral asset
  --pct_decrease PCT_DECREASE
                        Per iter percent drop of the collateral price to debt price
  --initial_collateral_usd INITIAL_COLLATERAL_USD
                        Size of collateral position to liquidate in the simulation
  --collateral_price COLLATERAL_PRICE
                        [Optional] Price of collateral asset. If this is not provided, the simulation uses the current price
  --debt_price DEBT_PRICE
                        [Optional] Price of the borrowable asset. If this is not provided, the simulation uses the current price.
  --repay_amount_usd REPAY_AMOUNT_USD
                        [Optional] Amount of debt that is repaid during the simulation
  --max_drawdown MAX_DRAWDOWN
                        [Optional] The maximum proportion the collateral price to debt price can drop during the simulation
  --m M                 Liquidation incentive parameter that determines the largest liquidation incentive allowed
  --beta BETA           Liquidation incentive parameter
  --min_liq_bonus MIN_LIQ_BONUS
                        Minimum liquidation bonus
```

For instance, if we wanted to get a recommended LLTV for the following:
- `WSTETH` collateral
- `WETH` borrow
- assuming that the ratio of WSETH/WETH does not decrease from their current prices by more than 5 percent
- liquidators repay in chunk sizes of $10mill
- price decrease of 1% at each timestep
- price ratio of WSTETH/WETH does not decrease by more than 5%
- an initial concentrated borrow position of $400 million

Then we would run the following command for such a simulation:

```bash
~$ python main.py   \
 --collateral wsteth  \
 --borrow weth        \
 --max_drawdown 0.05  \
 --pct_decrease 0.01  \
 --initial_collateral_usd 400000000
 --repay_amount_usd 10000000
```

While creating this tool, we aimed to provide a reasonable set of default methods for setting parameters such as max drawdown, per iteration percent decrease, repay amount, and initial borrow position. However, specific assets may exhibit unique properties that render these default settings less suitable. In these markets, users have the flexibility to override these settings and manually specify the parameters to better align with the assets' characteristics. We encourage users to explore and experiment with these adjustable parameters to tailor the tool to their particular needs and risk tolerance.

## Disclaimer
This risk tool is designed with a specific focus of simulating bad debt within different LLTV buckets under very specific assumptions about the collateral and borrow assets. While it offers flexibility and adaptability within its scope, it is essential to recognize its limitations and the scenarios it does not cover:
- **Oracle Mispricing Risk**: The tool does not capture risks associated with incorrect or manipulated price feeds from oracles, which could impact the actual market price.
- **Smart Contract Risk**: Risks stemming from vulnerabilities or errors within the underlying smart contracts, such as coding errors or potential exploits, are outside the scope of this model.
- **Geopolitical Risk**: Political events and changes in international relations that may affect market behavior cannot be simulated or predicted by this tool.
- **Market Volatility due to Government Regulation**: Changes in government regulations and their direct impact on market volatility are not within the tool's predictive capacity.

Users should recognize the tool's specific focus and limitations, employing it for its intended purpose while seeking supplementary risk assessment methods for scenarios not covered.


## Risk on Morpho Blue

### Borrower's Perspective
A borrower primarily needs to worry about keeping their account position safe from liquidations. Unlike other protocols, there is no close factor, which means the entirety of a borrower's position may be liquidated once their loan-to-value is below their LLTV.
As in other lending protocols, a borrower can manage the health of their borrow position by depositing additional collateral or by repaying a portion of their debt.


### Lender's Perspective
Unlike in other lending protocols, lenders on Morpho Blue have more control over risk management. Lenders who are supplying the borrowable asset choose:
- what asset to accept as collateral
- the liquidation loan to value (LLTV)

The lender is primarily concerned with situations where borrower(s) get liquidated in a way that leaves their position with **uncollateralized debt**. This arises when a liquidator repays some portion of a borrower's debt while claiming the entirety of their collateral. When a liquidation like this goes through, all lenders in the same LLTV tranche will have their supply amounts reduced pro-rata according to their share of the LLTV bucket. We illustrate such a liquidation below.

### Example
Suppose we have a WETH collateral, USDC borrow lending market with the following:
- lenders Alice and Bob, and a borrower Eve are all in the 80\% LLTV tranche.
- The liquidation incentive is 10%
- lenders Alice and Bob have both supplied $100 USDC each in this market and are the only suppliers in this LLTV bucket.
- borrower Eve provides $200 WETH in collateral to borrow $160 USDC. 

If the value of WETH drops such that the value of Eve's collateral is worth 165, her LTV would be $\frac{160}{165} = 0.969$, which is larger than her LLTV. This means she is eligible to be liquidated. A liquidator can repay $150 USDC of her debt to claim $150 \times (1 + 10\%) = 165$. At the end of this liquidation, Eve will have $0 in collateral and $10 in debt. Since this debt is uncollateralized, the debt is realized instantaneously and split between Alice and Bob equally since they both supplied the same amount to begin with. Their supply positions are now worth $95 USDC.

