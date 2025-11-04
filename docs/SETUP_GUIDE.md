# Setup Guide

Complete step-by-step guide to setting up the Pump.fun Trading Bot.

## Prerequisites

### System Requirements
- **Operating System**: macOS, Linux, or Windows 10+
- **Python**: Version 3.9 or higher
- **RAM**: Minimum 2GB available
- **Storage**: 500MB for code and logs
- **Network**: Stable internet connection (low latency preferred)

### Financial Requirements
- Minimum 0.5 SOL for testing (recommended: 2-5 SOL)
- SOL for transaction fees (~0.001 SOL per trade)
- Access to a Solana wallet

## Step-by-Step Installation

### 1. Install Python

**macOS:**
```bash
# Check if Python 3.9+ is installed
python3 --version

# If not, install via Homebrew
brew install python@3.11
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip
```

**Windows:**
- Download Python from [python.org](https://python.org)
- Ensure "Add Python to PATH" is checked during installation

### 2. Clone or Download the Project

```bash
cd pumpfun1
```

### 3. Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
# macOS/Linux:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

You should see `(venv)` in your terminal prompt.

### 4. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This will install all required packages including:
- solana (Solana Python SDK)
- websockets (For real-time data)
- pyyaml (Configuration)
- rich (Beautiful console output)
- And more...

### 5. Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your preferred editor
nano .env  # or vim, code, etc.
```

At minimum, set:
```
TRADING_MODE=dry_run
SOLANA_RPC_ENDPOINT=https://api.mainnet-beta.solana.com
SOLANA_WS_ENDPOINT=wss://api.mainnet-beta.solana.com
```

### 6. Configure Trading Parameters

Edit `config.yaml`:

```bash
nano config.yaml
```

**For testing**, use conservative settings:
```yaml
mode: dry_run

strategy:
  max_position_size_percent: 20  # Only 20% per trade
  max_concurrent_trades: 1       # One at a time
  profit_target_percent: 30      # Exit at +30%
  stop_loss_percent: 10          # Stop at -10%
```

### 7. Create Directories

```bash
mkdir -p logs data
```

## Wallet Setup (For Live Trading)

### Create a New Wallet

```bash
python bot.py --create-keypair wallet.json
```

This will generate a new Solana keypair and display the public address.

**⚠️ IMPORTANT:**
- Save the public address (you'll need it to fund the wallet)
- **NEVER share `wallet.json`** - it contains your private key
- Back up `wallet.json` securely
- Add `wallet.json` to `.gitignore` (already done)

### Fund the Wallet

1. Copy the public address from the output
2. Send SOL to this address from an exchange (Coinbase, Binance, etc.) or another wallet
3. Wait for confirmation (usually 1-2 minutes)

### Verify Balance

```bash
python bot.py --check-balance wallet.json
```

You should see your SOL balance.

## RPC Provider Setup (Optional but Recommended)

Free RPC endpoints work but may be slow or rate-limited. For best performance:

### Option 1: Helius (Recommended)

1. Sign up at [helius.dev](https://helius.dev)
2. Create a free API key
3. Update your `.env`:
```
SOLANA_RPC_ENDPOINT=https://mainnet.helius-rpc.com/?api-key=YOUR_KEY
SOLANA_WS_ENDPOINT=wss://mainnet.helius-rpc.com/?api-key=YOUR_KEY
```

### Option 2: QuickNode

1. Sign up at [quicknode.com](https://quicknode.com)
2. Create a Solana Mainnet endpoint
3. Copy your HTTP and WSS URLs
4. Update `.env` with your endpoints

### Option 3: Alchemy

1. Sign up at [alchemy.com](https://alchemy.com)
2. Create a Solana app
3. Use the provided endpoints

## First Run - Dry-Run Mode

Test the bot without risking real money:

```bash
# Make sure config.yaml has: mode: dry_run
python bot.py
```

You should see:
1. Startup banner
2. Configuration summary
3. Mock token detections
4. Simulated trades

Let it run for 5-10 minutes to see how it behaves.

**What to observe:**
- Does it detect tokens?
- Does it enter positions?
- Does it exit at profit/loss targets?
- Check `logs/trades.csv` for trade history

Press `Ctrl+C` to stop gracefully.

## Fine-Tuning

Based on dry-run results, adjust `config.yaml`:

### If too many trades:
- Increase `min_early_volume_sol`
- Increase `min_bonding_curve_progress`
- Decrease `max_bonding_curve_progress`

### If no trades:
- Decrease `min_early_volume_sol`
- Lower entry criteria thresholds

### If losing money:
- Increase `profit_target_percent` (take profit earlier)
- Decrease `stop_loss_percent` (cut losses sooner)
- Enable trailing stops

## Going Live

**⚠️ Only after extensive dry-run testing!**

1. Ensure wallet is funded with SOL
2. Start with small capital (0.5-1 SOL)
3. Update config:
```yaml
mode: live

wallet:
  initial_capital_sol: 1.0  # Your actual capital
```

4. Run:
```bash
python bot.py --mode live
```

5. **Monitor closely** for the first hour
6. Watch `logs/bot.log` for any errors
7. Check trades in `logs/trades.csv`

## Monitoring

### Real-time Monitoring

The console shows:
- New token detections
- Trade entries and exits
- P&L for each trade
- Running metrics

### Log Files

```bash
# Watch main log
tail -f logs/bot.log

# Watch trades
tail -f logs/trades.csv
```

### Metrics

Check `data/metrics.json` for detailed statistics:
```bash
cat data/metrics.json | python -m json.tool
```

## Troubleshooting Setup

### "Python not found"
- Ensure Python 3.9+ is installed
- Try `python3` instead of `python`

### "No module named 'solana'"
- Activate virtual environment: `source venv/bin/activate`
- Reinstall: `pip install -r requirements.txt`

### "Failed to connect to Solana RPC"
- Check internet connection
- Try a different RPC endpoint
- Verify endpoint URL has no typos

### "Keypair file not found"
- Create keypair: `python bot.py --create-keypair wallet.json`
- Check file path in config.yaml

### "Insufficient balance"
- Fund wallet with SOL
- Lower position size in config
- Ensure `min_sol_balance` is not too high

## Running as a Service (Advanced)

To run the bot 24/7, use a process manager:

### Using systemd (Linux)

Create `/etc/systemd/system/pumpfun-bot.service`:
```ini
[Unit]
Description=Pump.fun Trading Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/pumpfun1
Environment="PATH=/path/to/pumpfun1/venv/bin"
ExecStart=/path/to/pumpfun1/venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable pumpfun-bot
sudo systemctl start pumpfun-bot
sudo systemctl status pumpfun-bot
```

### Using screen (Simple)

```bash
screen -S pumpfun
source venv/bin/activate
python bot.py

# Detach: Ctrl+A, then D
# Reattach: screen -r pumpfun
```

## Next Steps

1. Read [STRATEGY_GUIDE.md](./STRATEGY_GUIDE.md) to understand the trading logic
2. Review [CONFIGURATION.md](./CONFIGURATION.md) for all config options
3. Start with dry-run mode
4. Test thoroughly before going live
5. Start with small capital
6. Monitor regularly

## Getting Help

- Check `logs/bot.log` for errors
- Review this guide and README.md
- Test in dry-run mode to isolate issues
- Verify all prerequisites are met

Good luck and trade responsibly! 🚀

