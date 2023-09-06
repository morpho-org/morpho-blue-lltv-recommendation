# Morpho Blue <> Gauntlet Risk Tool 
Gauntlet has developed a risk tool to allow potential lenders to Morpho Blue decide on a LLTV that suits their risk appetite. This tool comes in the form of a Python script that anyone can run on their own local machine. Simply run the following command:
```bash
python main.py --collateral weth --borrow usdc
```
See the Usage section below for further details on customizing the the risk tool parameters.

*If any questions, please reach out to @gauntlet_xyz on Twitter.*

## Contents
1. Background
1. Problem Statement
1. Market Risk Factors
1. Risk Tool Methodology
1. Dependencies
1. Installation
1. Usage
1. Disclaimer

## Background

Morpho Blue is lending protocol that consists of independent lending "markets". Each market is defined by:
- a borrowable asset
- a collateral asset
- price feeds for the borrowable and collateral assets
- a set of allowable liquidation loan-to-value parameters for lenders and borrowers to choose from

Borrowers and lenders decide which LLTV tranche to borrow or supply into when they participate in a market.
    
### Liquidation Example
Suppose we have a WETH collateral / USDC borrow market with a 0.75 LLTV tranches. Larry (a lender) supplies $100 USDC into this 0.75 LLTV bucket. Bob (a borrower) also wants to borrow from the $0.75$ LLTV tranche and supplies $100 WETH collateral to borrow $60 USDC. At this point, his LTV is $0.6$.

If/when the price of WETH drops by 20%, Bob's collateral will be worth $80. Bob can now be liquidated as his loan to value ratio has hit his LLTV: $\frac{\text{Bob's debt}}{\text{Bob's collateral}} = \frac{60}{80} = 0.75$.



## Problem Statement
For lenders entering a specific lending pair market on Morpho Blue, determining a suitable liquidation loan-to-value for their supply position can be a complex decision process. Different LLTV settings across different lending pair markets can lead to very different risk profiles. Our public tool aims to assist in this decision-making process by running simulations under various LLTV settings and price drawdown scenarios. Ultimately, **our tool will provide a recommended LLTV** according to a lender's assumptions about the sort of market downturns they want their position to remain solvent throughout.


## Market Risk Factors
What risk do users take on by borrowing or lending in Morpho Blue?

### Borrower's Perspective
As with all lending protocols, borrowers face **liquidation risk**: if the ratio of their debt to collateral increases, such that it exceeds their chosen liquidation loan-to-value (LLTV), their entire borrow position may be liquidated. This can happen due to the value of their collateral declining and/or the value of their debt increasing. Careful management of a user's LTV is essential to keep their position safe from liquidations. Borrowers can actively manage their borrow position's health by depositing additional collateral or repaying a portion of their debt. These proactive measures build a buffer between their LTV and LLTV to avoid liquidation under adverse market conditions.

### Lender's Perspective
Lenders in Morpho Blue face the risk of **bad debt**. Unlike borrowers who can mitigate their liquidation risk with careful account management, lenders are at the mercy of the market and may realize losses if borrowers in their tranche end up with undercollateralized borrow positions. Such a situation arises when a liquidation leaves a borrower with remaining debt but no collateral to back it. This is often referred to as bad debt or undercollateralized debt.

When bad debt is generated in the aftermath of a liquidation, it is immediately accounted for as a loss by being proportionally distributed among all lenders in the affected tranche. By resolving the bad debt as it is accrued, the negative impact is confined to the present lenders.

### Bad Debt Example
Suppose we have a WETH collateral, USDC borrow lending market with the following:
- Lenders Alice and Bob, and a borrower Eve are all in the 80\% LLTV tranche.
- The liquidation incentive is 10%
- Lenders Alice and Bob have both supplied $100 USDC each in this market and are the only suppliers in this tranche.
- Borrower Eve provides $200 WETH in collateral to borrow $160 USDC. 

If the value of WETH drops such that the value of Eve's collateral is worth $165. At this point, Eve's LTV is $\frac{160}{165} = 0.969$, which is larger than her LLTV. This means she is eligible to be liquidated. A liquidator can repay $150 USDC of her debt to claim $150 \times (1 + 10\%) = 165$. At the end of this liquidation, Eve will have $0 in collateral and $10 in debt. Since this debt is undercollateralized, the debt is realized instantaneously and split between Alice and Bob equally since they both supplied the same amount to begin with. Their supply positions are now worth $95 USDC.

### How Does Bad Debt Arise?
Bad debt accrues when a borrower has some amount of debt that is backed by 0 collateral.  An undercollateralized borrow position primarily stems from liquidations not occuring in a timely manner. Ideally, if the price of the collateral asset ever suffers a large price drop, liquidators would act swiftly to repay the borrower's debt and claim collateral once a borrower is eligible for liquidation, before the loan to value of the position reaches insolvency territory. Delays in liquidation can occur due to:

**High Slippage on Borrow Asset or Collateral Asset Buy/Sells**
- Liquidators may incur excessive slippage costs when
    - buying the borrow asset (to repay the debt)
    - or selling the collateral asset.
 If the slippage amount plus any transaction/gas fees is larger than the liquidation bonus, they likely will not liquidate a borrow position as it is no longer profitable to do so. If the collateral asset continues to decline in value (or conversely, the borrow asset increases in value), the borrow position will get closer to becoming undercollateralized and ultimately accrue bad debt.

**Narrow Healthy Liquidation Window**
In a lending market, having a high LLTV (ex: 95% or higher) can create scenarios where the opportunity window for safe or "healthy" liquidations is extremely limited. If liquidators miss this brief opportunity, subsequent price changes can guarantee that liquidations result in bad debt.

Consider an example involving a WETH/USDC lending market with a 97% LTV tranche and a 2% liquidation incentive. Here's what might happen:
- A borrower supplies $100 WETH as collateral and borrows $97 USDC.
- If the value of WETH drops, and the collateral is suddenly worth \$98.5, an optimal liquidator could repay $\frac{98.5}{1.02} = 96.57$ to claim the entire $98.5$ of WETH collateral.
- This leaves $0.43 USDC debt unbacked, leading to bad debt accrual.

The above scenario illustrates how a high LTV ratio can create a very narrow window for healthy liquidations. In this example, a mere $1.06\% = (1 - \frac{LLTV}{1 + LI}) \times 100\%$ price buffer exists before bad debt is guaranteed, which is an incredibly tight margin. Given that the daily price of WETH/USDC often changes by more than 1.06%, lenders in such a market should probably opt for a more conservative LTV tranche.




## Risk Tool Methodology
This risk tool performs a simulation to assess the potential for bad debt within specific each potential LLTV tranche in a given collateral/borrow market. This simulation method models the behavior of a concentrated borrow position, examining how changes in the ratio of collateral asset to debt asset price might lead to insolvency or liquidation.

In essence, the risk tool recreates a dynamic market environment where it:
- Initiates a concentrated borrow position: Reflecting certain market behaviors and conditions.
- Manipulates the collateral-to-debt ratio, gradually decreasing this ratio at each time step, driving the account closer to insolvency.
- Implements liquidation when applicable: When the account reaches a state where liquidation is justified, the tool liquidates part of the debt progressively.



1. **Concentrated Borrow Position**

The simulation begins with the assumption of one concentrated borrower. This initial collateral position size is determined based on various factors about the collateral asset. In the current state of the tool, we set this position size slightly differently based on the specific lending market under consideration:
- for larger market cap token markets: the larger of $200 million, the size of a 25% slippage sell order
- for smaller market cap token markets: the larger of $50 million, the size of a 25% slippage sell order

We assume that the borrower takes out as much loan as the input LLTV allows (ex: if the LLTV under consideration is 0.80, then the simulation sets the borrow amount to be 80% of the initial collateral).

2. **Simulation Time Step**

After we have initialized the concentrated borrow position, we proceed with simulation. At each timestep of the simulation, we apply:
- **a constant percentage price decrease**: At each time step, a constant percentage decrease (0.5%) is applied to the ratio of the collateral asset to debt asset to bring the borrow position closer towards liquidations and insolvency. We set the max drawdown to be equal to the 99th percentile of monthly price drawdowns.
Ex: If the ratio of the collateral asset to debt asset prices starts the month at $1 and reaches a minimum ratio of 0.5 at some point within a 30 day period, its maximum monthly percent drawdown is 50%. Other time periods other than 1 month may be used, but typically, the distribution remains relatively unchanged beyond a 2-week horizon.

- **liquidate a portion of the borrow position:** At the given timestep, if the borrower's debt to collateral ratio (LTV) is above their LLTV, we liquidate a portion of their position.
We repay an amount equal to the 0.5% price impact swap size of the collateral asset or borrow asset (whichever is smaller). For example, if a $100k swap incurs a $0.50\%$ price impact, then the liquidation amount is $100k. 

Each of the parameters specified thus far is a parameter that the user can also input into the risk tool so as to conform to the assumptions they want to bake into the simulation. User can specify their chosen parameters through CLI arguments as we will demonstrate in the subsequent section.

3. **Simulation Termination**

The simulation stops when the borrower has no more collateral, no more debt, or we have reached the maximum iteration count. Any undercollateralized debt that remains at the end of the simulation is insolvent debt.

We run this simulation LLTV values in the set: $\{0.01, 0.02, \ldots, 0.98, 0.99\}$. The tool/script will recommend the largest LLTV value that incurs zero bad debt in these simulations.


### Parameters 
A key feature of this risk tool is that users can customize all input parameters to tailor the simulation to their unique needs and adapt to current market conditions. The settings for the initial collateral position, repay amount, percent decrease, and max drawdown have been chosen based on extensive experimentation but might not be optimal under different market conditions.


- `initial_collateral_usd`: The initial value of the whale collateral position, determined heuristically based on market cap size.
- `repay_amount_usd`: The amount of USD being repaid at each time step if the account is liquidatable.
- `max_drawdown`: The largest allowed decrease in collateral value during the simulation.
- `pct_decrease`: Proportion to decrease the collateral price by at each time step. The default value is $0.005$.
- `min_liq_bonus`: The minimum liquidation bonus. Currently the liquidation incentive(bonus) is determined by the formula:
    $$LI  = \min\big(M, \frac{1}{\beta \times LLTV + (1-\beta)} - 1\big)
$$ 
    In some cases, the resulting liquidation incentive may be too small (ex: less than $1\%$), so we ensure that the liquidation bonus is no smaller than this value:
    $$LI  = \max(\min\big(M, \frac{1}{\beta \times LLTV + (1-\beta)} - 1\big), \text{min liq bonus}).$$
    
## Dependencies
### Data Dependencies
The risk tool uses data from the following APIs:
- [**CoinGecko**](https://www.coingecko.com/en/api): for historical price data of the collateral and borrow assets of a lending market
- [**GeckoTerminal**](https://apiguide.geckoterminal.com/): for obtaining a rough estimate of the size of DEX liquidity pools containing a given asset
- [**CowSwap**](https://docs.cow.fi/off-chain-services/api): for price impact swap sizes (I.E.: what is the size of swap from token `X` to `Y` that incurs roughly 0.5% price impact?)

### Library Dependencies
The risk tool is intended to have minimal dependencies. The main software dependencies are standard libraries from the scientific computing/data science ecosystem such as
- Pandas
- NumPy
- matplotlib.

See the `requirements.txt` file in the repo for more details.

## Installation
Clone the respository and run the setup script like so:
```
git clone https://github.com/GauntletNetworks/morpho
sh setup.sh
```
The setup script will create a python virtual environment and install the requirements.

## Usage
The risk tool is provided as a python script in this repository. To see all the parameters, run the following:
```bash
~/morpho:~$ python main.py --help
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
- liquidators repay in chunk sizes of $10 million
- price decrease of 1% at each timestep
- price ratio of WSTETH/WETH does not decrease by more than 5%
- an initial concentrated borrow position of $400 million

Then we would run the following command for such a simulation:

```bash
~/morpho:~$ python main.py \
 --collateral wsteth                    \
 --borrow weth                          \
 --max_drawdown 0.05                    \
 --pct_decrease 0.01                    \
 --initial_collateral_usd 400000000     \
 --repay_amount_usd 10000000
```

By default, we use cached drawdown and cached price impact numbers that have been pre-computed. We do this because querying CoinGecko and CowSwap for some of this data can take more time than a user may be willing to wait (on the order of 10-20 seconds). The downside of this is that if certain market conditions change, or if a market event occurs that has a large impact on price or liquidity of an asset, then the cached price impact and drawdown numbers may no longer be relevant and the resulting simulation results may give a misleading recommendation for LLTV. The user can instead run the risk tool script with the `--update_cache` flag to ensure that fresh drawdown and price impact numbers are fetched:
```bash
~/morpho:~$ python main.py \
 --collateral wsteth                 \
 --borrow weth                       \
 --max_drawdown 0.05                 \
 --pct_decrease 0.01                 \
 --initial_collateral_usd 400000000  \
 --repay_amount_usd 10000000         \
 --update_cache
```

While creating this tool, we aimed to provide a reasonable set of default methods for setting parameters such as max drawdown, per iteration percent decrease, repay amount, and initial borrow position. However, specific assets may exhibit unique properties that render these default settings less suitable. In these markets, users have the flexibility to override these settings and manually specify the parameters to better align with the assets' characteristics. We encourage users to explore and experiment with these adjustable parameters to tailor the tool to their particular needs and risk tolerance.

## Disclaimer
This risk tool is designed with a specific focus of simulating bad debt within different LLTV buckets under very specific assumptions about the collateral and borrow assets. While it offers flexibility and adaptability within its scope, it is essential to recognize its limitations and the scenarios it does not cover:
- **Oracle Mispricing Risk**: The tool does not capture risks associated with incorrect or manipulated price feeds from oracles, which could impact the actual market price.
- **Smart Contract Risk**: Risks stemming from vulnerabilities or errors within the underlying smart contracts, such as coding errors or potential exploits, are outside the scope of this model.

Users should recognize the tool's specific focus and limitations, employing it for its intended purpose while seeking supplementary risk assessment methods for scenarios not covered.

## Contact

*If any questions, please reach out to @gauntlet_xyz on Twitter. For more information,  visit our website at www.gauntlet.xyz.*
