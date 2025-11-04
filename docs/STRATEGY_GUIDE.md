# Trading Strategy Guide

Detailed explanation of the bot's trading strategy and how to optimize it.

## Strategy Overview

The bot implements a **momentum-based scalping strategy** designed for Pump.fun meme tokens:

1. **Detect** new token launches in real-time
2. **Observe** early trading activity (3-5 seconds)
3. **Evaluate** momentum signals
4. **Enter** if criteria met with calculated position size
5. **Monitor** price action continuously
6. **Exit** on profit target, stop-loss, or time limit

This strategy aims to capture early pumps while avoiding late entries and managing downside risk.

## Entry Strategy

### 1. Detection Phase

**How it works:**
- WebSocket subscription to Solana blockchain
- Monitors Pump.fun program ID for "create" instructions
- Parses transaction data to extract token details
- Triggers within 1-2 seconds of launch

**Configuration:** N/A (automatic)

### 2. Filtering Phase

**Checks performed:**
- Creator address not blacklisted
- Token name/symbol doesn't contain banned keywords
- Token hasn't already graduated to PumpSwap
- Not flagged as suspicious

**Configuration:**
```yaml
risk:
  blacklist_creators:
    - "ScammerAddress123..."
  blacklist_keywords:
    - "scam"
    - "rug"
    - "test"
```

**Why this matters:** Filters out obvious scams and low-quality tokens before wasting fees.

### 3. Observation Phase

**What's measured:**
- Early buy count (number of purchase transactions)
- Total volume (SOL spent by early buyers)
- Unique buyer addresses
- Price change in observation window
- Bonding curve fill percentage

**Duration:** 3-5 seconds (configurable)

**Configuration:**
```yaml
strategy:
  evaluation_window_seconds: 3
```

**Trade-off:** 
- Shorter window = Earlier entry, but less data
- Longer window = More data, but may miss optimal entry

### 4. Evaluation Phase

**Entry criteria (ALL must be met):**

**a) Minimum Volume**
```yaml
min_early_volume_sol: 0.5
```
Early volume must exceed this threshold. Low volume = low interest = likely to fail.

**b) Bonding Curve Progress**
```yaml
min_bonding_curve_progress: 2   # At least 2% filled
max_bonding_curve_progress: 60  # No more than 60% filled
```
- Too early (<2%): High risk of dead launch
- Too late (>60%): Most gains already captured, higher risk of buying the top

**c) Positive Momentum**
Price change during observation window must be positive or neutral. If price is already dropping in first few seconds, avoid.

**d) Sufficient Buyer Interest**
Multiple unique buyers indicate genuine interest vs. single-wallet manipulation.

**Configuration examples:**

**Aggressive (more trades, higher risk):**
```yaml
min_early_volume_sol: 0.3
min_bonding_curve_progress: 1
max_bonding_curve_progress: 70
```

**Conservative (fewer trades, lower risk):**
```yaml
min_early_volume_sol: 1.0
min_bonding_curve_progress: 5
max_bonding_curve_progress: 40
```

### 5. Position Sizing

**Formula:**
```
Available Capital = Wallet Balance - Min Reserve
Position Size = Available Capital × (max_position_size_percent / 100)
```

**Configuration:**
```yaml
strategy:
  max_position_size_percent: 25  # 25% of available capital

risk:
  min_sol_balance: 0.05  # Keep for fees
```

**Example:**
- Wallet: 2.0 SOL
- Reserve: 0.05 SOL
- Available: 1.95 SOL
- Position: 1.95 × 0.25 = 0.4875 SOL

**Risk Management:**
Never risk entire capital on one trade. If first trade loses, you still have capital for the next opportunity.

## Exit Strategy

The bot uses **multiple exit conditions** evaluated continuously. First condition to trigger causes immediate exit.

### Exit Condition 1: Profit Target

**Trigger:** Price increases by target percentage

**Configuration:**
```yaml
strategy:
  profit_target_percent: 50  # Exit at +50%
```

**Example:**
- Entry: 0.0001 SOL
- Target: 0.00015 SOL (+50%)
- Exit immediately when target hit

**Optimization:**
- Higher target (75-100%): Fewer wins, but larger profits when hit
- Lower target (20-30%): More frequent wins, smaller per-trade profit

**Recommendation:** Start with 30-50%, adjust based on success rate.

### Exit Condition 2: Trailing Stop

**Trigger:** Price falls X% from its peak since entry

**Configuration:**
```yaml
strategy:
  trailing_stop_percent: 10
```

**How it works:**
```
Entry: 0.0001
Peak: 0.0003 (+200%)
Trailing Stop: 0.0003 × 0.9 = 0.00027
Current: 0.00025
→ SELL (below trailing stop)
```

**Purpose:** Lock in profits when price reverses after a pump.

**The bot updates the trailing stop as price rises:**
- Price at 0.0002 → Stop at 0.00018
- Price at 0.0003 → Stop at 0.00027
- Price never moves stop down, only up

**Optimization:**
- Tighter stop (5-8%): Protect profits more, but may exit on minor dips
- Looser stop (15-20%): Hold through volatility, risk giving back more profit

### Exit Condition 3: Stop-Loss

**Trigger:** Price falls below entry by stop-loss percentage

**Configuration:**
```yaml
strategy:
  stop_loss_percent: 10
```

**Example:**
- Entry: 0.0001
- Stop: 0.00009 (-10%)
- Exit if price drops to stop level

**Purpose:** Limit losses on failed pumps.

**Critical:** Stop-loss is non-negotiable. Meme tokens can go to near-zero. Always have a maximum loss defined.

**Optimization:**
- Tighter stop (5-7%): Less loss per trade, but more stopped out
- Looser stop (15-20%): Fewer stop-outs, but larger losses when wrong

### Exit Condition 4: Time Limit

**Trigger:** Position held for maximum duration

**Configuration:**
```yaml
strategy:
  max_hold_time_seconds: 90
```

**Purpose:** 
- Force exit if token goes sideways (not pumping or dumping)
- Free capital for next opportunity
- Pump.fun pumps typically happen in first 30-120 seconds

**Optimization:**
- Shorter (30-60s): High turnover, may miss slower pumps
- Longer (120-180s): Capture slower pumps, but capital tied up longer

### Exit Condition 5: Emergency Limits

**Absolute loss limit:**
```yaml
risk:
  max_loss_per_trade_sol: 0.1
```

If loss exceeds this SOL amount, exit immediately regardless of percentages.

**Minimum hold time:**
```yaml
strategy:
  min_hold_time_seconds: 5
```

Prevents overtrading and thrashing. Must hold at least 5s before any exit is allowed.

## Fee Accounting

Every trade includes fees that reduce profit:

### Pump.fun Fees
- **Buy fee:** 1.25% of purchase amount
- **Sell fee:** 1.25% of sale amount
- **Total:** ~2.5% round-trip

### Solana Network Fees
- **Transaction fee:** ~0.000005 SOL per transaction
- **Priority fee:** Configurable (recommended 5000-10000 lamports)

### Slippage
- Price movement during transaction execution
- Usually minimal with small position sizes
- Max slippage configurable (default 5%)

### Net Profit Formula
```
Gross Profit = Exit Value - Entry Value
Total Fees = (Entry × 0.0125) + (Exit × 0.0125) + Network Fees
Net Profit = Gross Profit - Total Fees
```

**Implication:** You need >2.5% price increase just to break even.

**Configuration:**
```yaml
strategy:
  min_profit_after_fees: 3  # Require >3% gain to be worthwhile
```

## Risk Management Rules

### 1. Position Size Limits

Never risk too much on one trade:
```yaml
strategy:
  max_position_size_percent: 25
```

With this setting, even if you lose 4 trades in a row at -10% each, you still have capital.

### 2. Concurrent Trade Limits

```yaml
strategy:
  max_concurrent_trades: 1
```

**Single trade:** Full focus, easier to manage, no capital fragmentation.

**Multiple trades:** Higher total exposure, harder to monitor, potential correlated losses.

**Recommendation:** Start with 1, increase only after proven success.

### 3. Daily Loss Limits

```yaml
risk:
  max_daily_loss_percent: 20
```

If down 20% in a single day, bot stops trading until next day. Prevents revenge trading and capital destruction.

### 4. Balance Reserve

```yaml
risk:
  min_sol_balance: 0.05
```

Always keep SOL for transaction fees. Running out of fee money prevents closing positions!

## Strategy Optimization

### Backtesting Approach

1. **Run in dry-run mode** with mock data
2. **Record metrics** for 24-48 hours
3. **Analyze results:**
   - Win rate
   - Average profit per trade
   - Max drawdown
   - Total trades executed

4. **Adjust one parameter at a time**
5. **Test again**
6. **Compare results**

### Key Metrics to Track

**Win Rate:**
- Target: >50%
- If <40%, entry criteria too loose or exits too aggressive

**Average Profit per Trade:**
- Should be positive after fees
- If negative, strategy is not profitable

**Profit Factor:**
```
Profit Factor = Total Winning Trades $ / Total Losing Trades $
```
- Target: >1.5
- If <1.0, strategy loses money

**Max Drawdown:**
- Maximum peak-to-trough loss
- Target: <30%
- If >50%, risk management is insufficient

### Common Issues & Solutions

**Issue:** Very few trades executed
**Solutions:**
- Lower `min_early_volume_sol`
- Widen bonding curve range
- Shorten evaluation window

**Issue:** Losing money despite wins
**Solutions:**
- Increase profit target
- Tighten stop-loss
- Ensure `min_profit_after_fees` is set

**Issue:** Frequent stop-outs
**Solutions:**
- Widen stop-loss
- Better entry timing (longer evaluation)
- Stricter entry criteria

**Issue:** Missing profitable pumps
**Solutions:**
- Faster entry (shorter evaluation window)
- Higher bonding curve max
- Consider multiple concurrent trades

## Example Configurations

### Ultra-Conservative
```yaml
strategy:
  max_position_size_percent: 15
  max_concurrent_trades: 1
  profit_target_percent: 30
  stop_loss_percent: 8
  min_early_volume_sol: 1.0
  max_bonding_curve_progress: 40
```

### Balanced (Default)
```yaml
strategy:
  max_position_size_percent: 25
  max_concurrent_trades: 1
  profit_target_percent: 50
  stop_loss_percent: 10
  min_early_volume_sol: 0.5
  max_bonding_curve_progress: 60
```

### Aggressive
```yaml
strategy:
  max_position_size_percent: 40
  max_concurrent_trades: 2
  profit_target_percent: 75
  stop_loss_percent: 12
  min_early_volume_sol: 0.3
  max_bonding_curve_progress: 70
```

## Advanced Strategies

### 1. Scaling Out
Take partial profits at multiple levels:
- Sell 50% at +30%
- Sell 25% at +50%
- Sell remaining at trailing stop

*(Requires code modification)*

### 2. Martingale (Not Recommended)
Double position size after loss.

**Risk:** Can wipe out account quickly.

### 3. Follow Successful Wallets
Track wallets with high win rates and follow their trades.

*(Requires additional data collection)*

### 4. Social Sentiment
Integrate Twitter/Telegram mentions to gauge hype.

*(Requires API integration)*

## Conclusion

The default strategy is designed to be **conservative and sustainable**. Meme token trading is inherently high-risk, so the bot prioritizes:

1. **Capital preservation** (stop-losses, position sizing)
2. **Consistent small wins** over lottery tickets
3. **Quick exits** to avoid holding pumps too long

**Test thoroughly in dry-run mode** before risking real capital. Adjust parameters based on your risk tolerance and results.

Remember: **Most traders lose money on meme tokens.** This bot gives you an edge through speed and discipline, but cannot guarantee profits.

Trade responsibly! 🚀

