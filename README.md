# 🚀 Pump.fun Trading Bot

An intelligent, automated trading bot for Pump.fun meme tokens on the Solana blockchain. This bot is designed to capitalize on short-term price movements of newly launched tokens while managing risk through sophisticated entry/exit strategies.

## ⚠️ Disclaimer

**This bot is for educational purposes only.** Trading meme tokens is extremely high-risk and volatile. Most traders lose money. Never invest more than you can afford to lose. This software comes with no warranties or guarantees of profitability.

## ✨ Features

### 🌐 **NEW: Web Dashboard**
- **Beautiful Real-Time UI**: Modern dark theme with live metrics
- **Settings Page**: Easy configuration without editing files
- **Mode Switcher**: Toggle between dry-run and live trading with safety checks
- **Live Updates**: WebSocket-powered real-time data (auto-refresh every 2 seconds)
- **Interactive Charts**: Performance tracking and P&L distribution
- **Bot Controls**: Start/Stop from the browser
- **Trade History**: Complete log with filtering options

### 🎯 Core Trading Capabilities
- **Real-time Launch Detection**: Monitors Solana blockchain for new Pump.fun token launches via WebSocket
- **Intelligent Entry Strategy**: Evaluates early momentum, volume, and bonding curve progress before entering
- **Dynamic Exit Logic**: Multi-condition exits including profit targets, trailing stops, and stop-loss
- **Risk Management**: Position sizing, concurrent trade limits, and daily loss limits
- **Dual-Mode Operation**: Dry-run (paper trading) and live trading modes

### 🛡️ Risk Management
- Configurable position sizing (% of capital per trade)
- Stop-loss protection (default 10%)
- Take-profit targets (default 50%)
- Trailing stops to lock in gains
- Maximum hold time limits
- Daily loss limits
- Creator and keyword blacklists

### 📊 Monitoring & Analytics
- Real-time performance metrics
- Trade history logging (CSV)
- Profit/loss tracking
- Win rate and ROI calculations
- Detailed console logging with color-coded output
- Metrics persistence (JSON)

### 🔧 Technical Features
- Async/await architecture for high performance
- WebSocket subscriptions for low-latency detection
- Modular, extensible codebase
- Comprehensive error handling
- Graceful shutdown with position closing
- Configuration via YAML and environment variables

## 📋 Requirements

- **Python**: 3.9 or higher
- **Operating System**: macOS, Linux, or Windows
- **Capital**: Minimum 0.5 SOL recommended (adjust in config)
- **RPC Endpoint**: Solana RPC access (free tier works, premium recommended)

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
cd pumpfun1

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `config.yaml` to set your parameters:
- Trading mode (dry_run or live)
- Position size limits
- Profit targets and stop-loss levels
- RPC endpoints

### 3. Create a Trading Wallet (Live Mode Only)

```bash
# Generate a new keypair
python bot.py --create-keypair wallet.json

# Fund the wallet with SOL
# Send SOL to the displayed public key address
```

### 4. Launch the Web Dashboard

Start the beautiful web interface:

```bash
python web_app.py
```

Then open your browser to **http://localhost:5001**

### 5. Test in Dry-Run Mode

The dashboard starts in dry-run mode by default (safe testing with simulated data).

1. Click **"▶ Start Bot"** in the dashboard
2. Watch metrics update in real-time
3. View trades in the history table
4. Monitor performance charts

### 6. Go Live (When Ready)

**⚠️ Only after thorough testing!**

1. Click **"⚙️ Settings"** in the dashboard
2. Select **"Live Trading Mode"**
3. Configure your wallet path
4. Click **"Check Balance"** to verify funds
5. **Save Settings** (you'll get a safety warning)
6. Return to dashboard and start the bot

Or use command line:
```bash
python bot.py --mode live
```

## 📖 Usage

### Web Dashboard (Recommended)

```bash
# Start the web interface
python web_app.py

# Access at http://localhost:5001
```

**Dashboard Features:**
- 📊 Real-time metrics and charts
- 🎮 Start/Stop bot controls
- ⚙️ Settings page for configuration
- 💰 Mode switcher (dry-run ↔ live trading)
- 📜 Trade history with filtering
- 🎯 Active positions monitor

### Command Line

```bash
# Run bot with default config
python bot.py

# Use custom config file
python bot.py --config my_config.yaml

# Force dry-run mode
python bot.py --mode dry_run

# Force live mode
python bot.py --mode live

# Create new keypair
python bot.py --create-keypair path/to/wallet.json

# Check wallet balance
python bot.py --check-balance path/to/wallet.json
```

### Stopping the Bot

Press `Ctrl+C` to gracefully stop the bot. It will:
1. Close all open positions
2. Save final metrics
3. Display performance summary

## 🎛️ Configuration

Key configuration parameters in `config.yaml`:

### Trading Strategy
```yaml
strategy:
  max_position_size_percent: 25      # Max % of capital per trade
  max_concurrent_trades: 1           # Number of simultaneous positions
  profit_target_percent: 50          # Take profit at +50%
  stop_loss_percent: 10              # Stop loss at -10%
  trailing_stop_percent: 10          # Trailing stop from peak
  max_hold_time_seconds: 90          # Max hold time before forced exit
```

### Risk Management
```yaml
risk:
  max_daily_loss_percent: 20         # Stop trading if down 20% in a day
  max_loss_per_trade_sol: 0.1        # Absolute max loss per trade
  min_sol_balance: 0.05              # Keep for transaction fees
  blacklist_creators: []             # Creator addresses to avoid
  blacklist_keywords:                # Token name filters
    - "scam"
    - "rug"
```

### Entry Criteria
```yaml
strategy:
  min_early_volume_sol: 0.5          # Min volume to consider entry
  evaluation_window_seconds: 3       # Observation period
  min_bonding_curve_progress: 2      # Min % filled
  max_bonding_curve_progress: 60     # Max % (avoid late entries)
```

## 📊 Performance Tracking

### Logs

The bot creates several log files:

- `logs/bot.log` - Detailed execution log
- `logs/trades.csv` - Trade history (entry, exit, P&L)
- `data/metrics.json` - Real-time performance metrics

### Metrics

Track your bot's performance:
- Total P&L (SOL and %)
- Win rate
- Average profit per trade
- Maximum drawdown
- ROI since start

View metrics in real-time on the console or check `data/metrics.json`.

## 🏗️ Architecture

```
pumpfun1/
├── bot.py                    # Main entry point
├── config.yaml               # Configuration
├── requirements.txt          # Python dependencies
├── src/
│   ├── __init__.py
│   ├── config.py            # Configuration management
│   ├── models.py            # Data models (Token, Position, Trade)
│   ├── logger.py            # Logging system
│   ├── solana_client.py     # Solana RPC/WebSocket client
│   ├── detector.py          # Launch detection
│   ├── risk_manager.py      # Risk management
│   └── trading_engine.py    # Core trading logic
├── logs/                     # Log files
└── data/                     # Metrics and history
```

### Component Overview

1. **Config**: YAML + environment variable management
2. **Solana Client**: Async RPC calls and WebSocket subscriptions
3. **Pump.fun Client**: Specialized methods for Pump.fun smart contracts
4. **Launch Detector**: Monitors blockchain for new token events
5. **Risk Manager**: Position sizing, filters, and exit conditions
6. **Trading Engine**: Orchestrates all components, manages positions

## 🔬 Development

### Dry-Run Mode

Dry-run mode is essential for testing:
- Uses mock tokens with simulated price movements
- No real transactions sent
- Safe to test strategy parameters
- Logs all "would-be" trades

### Extending the Bot

The modular architecture makes it easy to extend:

**Add custom entry signals:**
```python
# In risk_manager.py
def check_entry_criteria(self, token, activity):
    # Add your custom logic
    if token.holder_count > 100:
        return True, "High holder count"
    # ...
```

**Add notification integrations:**
```python
# In logger.py
def send_telegram_alert(self, message):
    # Implement Telegram notifications
    pass
```

## ⚙️ Advanced Configuration

### Using Premium RPC Providers

For best performance, use a premium RPC provider:

**Helius:**
```yaml
solana:
  rpc_endpoint: "https://mainnet.helius-rpc.com/?api-key=YOUR_KEY"
  ws_endpoint: "wss://mainnet.helius-rpc.com/?api-key=YOUR_KEY"
```

**QuickNode:**
```yaml
solana:
  rpc_endpoint: "https://your-endpoint.solana-mainnet.quiknode.pro/YOUR_TOKEN/"
  ws_endpoint: "wss://your-endpoint.solana-mainnet.quiknode.pro/YOUR_TOKEN/"
```

### Priority Fees

Increase priority fee for faster transaction confirmation:
```yaml
solana:
  priority_fee: 10000  # Higher = faster (in lamports)
```

## 🐛 Troubleshooting

### Common Issues

**"Failed to connect to Solana RPC"**
- Check your internet connection
- Verify RPC endpoint URL
- Try a different RPC provider
- Check for rate limiting

**"Keypair file not found"**
- Create a keypair: `python bot.py --create-keypair wallet.json`
- Verify the path in config.yaml

**"Insufficient balance"**
- Check balance: `python bot.py --check-balance wallet.json`
- Fund your wallet with SOL
- Adjust `min_sol_balance` in config

**No trades executing in live mode**
- Verify Pump.fun program ID is correct
- Check RPC endpoint supports WebSocket subscriptions
- Ensure sufficient SOL balance
- Review entry criteria (may be too strict)

### Debug Mode

Enable detailed logging:
```yaml
logging:
  level: "DEBUG"
```

## 📈 Trading Strategy Explained

### Entry Strategy

1. **Detection**: Monitor blockchain for new Pump.fun token launches
2. **Filtering**: Skip blacklisted creators and keywords
3. **Observation**: Wait 3-5 seconds to observe early trading activity
4. **Evaluation**: Check momentum, volume, bonding curve progress
5. **Entry**: Buy if criteria met, using calculated position size

### Exit Strategy

The bot exits when **any** of these conditions are met:

- **Profit Target**: Price increases by target % (default 50%)
- **Trailing Stop**: Price falls X% from peak (default 10%)
- **Stop Loss**: Price falls below entry by X% (default 10%)
- **Time Limit**: Maximum hold time reached (default 90s)
- **Manual**: Bot shutdown triggers position close

### Fee Accounting

All profit calculations include:
- Pump.fun trading fee (1.25%)
- Solana network fees (~0.000005 SOL)
- Slippage estimates

Net profit = Gross profit - Fees

## 🤝 Contributing

This is a personal project, but suggestions and improvements are welcome!

## 📄 License

This project is for educational purposes. Use at your own risk.

## 🙏 Acknowledgments

- Solana blockchain and ecosystem
- Pump.fun platform
- Python Solana libraries (solana-py, anchorpy)

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Review logs in `logs/bot.log`
3. Test in dry-run mode first
4. Verify configuration settings

---

**Remember**: Trading meme tokens is extremely risky. This bot is a tool to help automate a strategy, but it cannot guarantee profits. Always start with small amounts you can afford to lose, test thoroughly in dry-run mode, and monitor the bot's performance closely.

Happy (safe) trading! 🚀

