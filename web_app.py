#!/usr/bin/env python3
"""
Flask Web Dashboard for Pump.fun Trading Bot
Beautiful real-time monitoring interface
"""

# Eventlet monkey patching must be first!
import eventlet
eventlet.monkey_patch()

import sys
import json
import asyncio
import threading
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import get_config
from src.logger import get_logger
from src.solana_client import SolanaClient, PumpFunClient
from src.detector import LaunchDetector, MockLaunchDetector
from src.risk_manager import RiskManager
from src.trading_engine import TradingEngine
from src.models import BotMetrics

# Initialize Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'pumpfun-trading-bot-secret'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', logger=True, engineio_logger=True)

# Global state
bot_state = {
    'running': False,
    'bot': None,
    'engine': None,
    'config': None,
    'metrics': None,
    'last_update': None
}


class WebTradingBot:
    """Trading bot wrapper for web interface"""
    
    def __init__(self, config_path="config.yaml"):
        self.config = get_config(config_path)
        self.logger = get_logger(
            log_file=self.config.get('logging.log_file'),
            trade_log_file=self.config.get('logging.trade_log_file'),
            level='INFO'
        )
        
        self.solana_client = None
        self.pumpfun_client = None
        self.detector = None
        self.risk_manager = None
        self.trading_engine = None
        self.loop = None
        self.running = False
    
    async def initialize(self):
        """Initialize all components"""
        self.logger.info("Initializing bot components...")
        
        # Initialize Solana client
        self.solana_client = SolanaClient(
            rpc_endpoint=self.config.get('solana.rpc_endpoint'),
            ws_endpoint=self.config.get('solana.ws_endpoint'),
            commitment=self.config.get('solana.commitment', 'confirmed')
        )
        
        connected = await self.solana_client.connect()
        if not connected:
            raise Exception("Failed to connect to Solana RPC")
        
        # Initialize Pump.fun client
        self.pumpfun_client = PumpFunClient(self.solana_client)
        
        # Initialize detector (mock for now)
        self.detector = MockLaunchDetector(
            self.solana_client,
            self.pumpfun_client
        )
        
        # Initialize risk manager
        self.risk_manager = RiskManager(self.config.config)
        
        # Initialize trading engine
        self.trading_engine = TradingEngine(
            config=self.config,
            solana_client=self.solana_client,
            pumpfun_client=self.pumpfun_client,
            detector=self.detector,
            risk_manager=self.risk_manager,
            dry_run=True  # Always dry-run for web demo
        )
        
        self.logger.info("✅ All components initialized")
    
    async def start(self):
        """Start the trading bot"""
        self.running = True
        
        # Start trading engine in background task
        engine_task = asyncio.create_task(self.trading_engine.start(keypair=None))
        
        # Emit updates periodically
        while self.running:
            await asyncio.sleep(2)  # Update every 2 seconds
            if self.running:
                self.emit_update()
        
        # Wait for engine to stop
        await engine_task
    
    def emit_update(self):
        """Emit bot status update via WebSocket"""
        try:
            if not self.trading_engine:
                print("⚠️  No trading engine, skipping update")
                return
                
            metrics = self.trading_engine.metrics
            
            # Calculate true current capital (available + positions value)
            current_capital = self.trading_engine.available_capital
            
            print(f"📊 Available Capital: {current_capital:.4f} SOL")
            print(f"📊 Active Positions: {len(self.trading_engine.active_positions)}")
            
            # Add value of open positions
            for position in self.trading_engine.active_positions.values():
                position_value = position.current_price * position.entry_token_amount
                current_capital += position_value
                print(f"   + Position {position.token.symbol}: {position_value:.4f} SOL")
            
            # Update metrics with current capital
            metrics.update_capital(current_capital)
            
            # Force recalculate ROI
            if metrics.initial_capital_sol > 0:
                metrics.current_capital_sol = current_capital
                roi = ((current_capital - metrics.initial_capital_sol) / metrics.initial_capital_sol) * 100
            else:
                roi = 0.0
            
            print(f"📊 Total Capital: {current_capital:.4f} SOL")
            print(f"📊 ROI: {roi:.2f}%")
            print(f"📊 Trades: {metrics.total_trades} (W:{metrics.winning_trades} L:{metrics.losing_trades})")
            
            update_data = {
                'running': self.running,
                'timestamp': datetime.now().isoformat(),
                'capital': {
                    'current': round(current_capital, 4),
                    'initial': round(metrics.initial_capital_sol, 4),
                    'peak': round(metrics.peak_capital_sol, 4),
                    'roi': round(roi, 2)
                },
                'trades': {
                    'total': metrics.total_trades,
                    'winning': metrics.winning_trades,
                    'losing': metrics.losing_trades,
                    'win_rate': round(metrics.win_rate, 2)
                },
                'pnl': {
                    'total': round(metrics.total_pnl_sol, 4),
                    'net': round(metrics.net_pnl, 4),
                    'fees': round(metrics.total_fees_paid_sol, 4),
                    'best': round(metrics.best_trade_pnl_sol, 4),
                    'worst': round(metrics.worst_trade_pnl_sol, 4)
                },
                'activity': {
                    'evaluated': metrics.tokens_evaluated,
                    'skipped': metrics.tokens_skipped,
                    'active_positions': len(self.trading_engine.active_positions)
                },
                'positions': [
                    {
                        'symbol': pos.token.symbol,
                        'entry_price': pos.entry_price,
                        'current_price': pos.current_price,
                        'pnl_percent': round(pos.unrealized_pnl_percent, 2),
                        'pnl_sol': round(pos.unrealized_pnl_sol, 4),
                        'hold_time': round(pos.hold_time_seconds, 0)
                    }
                    for pos in self.trading_engine.active_positions.values()
                ]
            }
            
            print(f"🔔 Emitting update via WebSocket...")
            socketio.emit('bot_update', update_data)
            print(f"✅ Update emitted successfully!")
            
        except Exception as e:
            print(f"❌ Error emitting update: {e}")
            self.logger.error(f"Error emitting update: {e}")
    
    async def stop(self):
        """Stop the trading bot"""
        self.running = False
        if self.trading_engine:
            await self.trading_engine.stop()
        if self.solana_client:
            await self.solana_client.disconnect()
    
    def run_async(self, coro):
        """Run async coroutine in bot's event loop"""
        if self.loop is None:
            self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        return self.loop.run_until_complete(coro)


# Routes
@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')


@app.route('/settings')
def settings():
    """Settings page"""
    return render_template('settings.html')


@app.route('/api/reset_state', methods=['POST'])
def reset_state():
    """Reset bot state (start fresh with initial capital)"""
    try:
        from src.state_manager import StateManager
        
        state_manager = StateManager("bot_state.json")
        state_manager.clear_state()
        
        return jsonify({
            'success': True,
            'message': 'Bot state reset successfully. Restart the bot to start fresh.'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/status')
def get_status():
    """Get current bot status"""
    if not bot_state['engine']:
        # Bot not running, but try to load saved state to show
        from src.state_manager import StateManager
        state_manager = StateManager("bot_state.json")
        saved_state = state_manager.load_state()
        
        if saved_state:
            # Show saved state
            saved_metrics = saved_state.get('metrics', {})
            return jsonify({
                'running': False,
                'message': 'Bot not initialized (showing saved state)',
                'timestamp': datetime.now().isoformat(),
                'capital': {
                    'current': round(saved_state.get('current_capital', 2.0), 4),
                    'initial': round(saved_metrics.get('initial_capital_sol', 2.0), 4),
                    'peak': round(saved_metrics.get('peak_capital_sol', 2.0), 4),
                    'roi': round(((saved_state.get('current_capital', 2.0) - saved_metrics.get('initial_capital_sol', 2.0)) / saved_metrics.get('initial_capital_sol', 2.0) * 100) if saved_metrics.get('initial_capital_sol', 2.0) > 0 else 0.0, 2)
                },
                'trades': {
                    'total': saved_metrics.get('total_trades', 0),
                    'winning': saved_metrics.get('winning_trades', 0),
                    'losing': saved_metrics.get('losing_trades', 0),
                    'win_rate': round((saved_metrics.get('winning_trades', 0) / max(saved_metrics.get('total_trades', 1), 1) * 100), 2)
                },
                'pnl': {
                    'total': round(saved_metrics.get('total_pnl_sol', 0.0), 4),
                    'net': round(saved_metrics.get('total_pnl_sol', 0.0), 4),
                    'fees': round(saved_metrics.get('total_fees_paid_sol', 0.0), 4)
                }
            })
        else:
            # No saved state, show defaults
            return jsonify({
                'running': False,
                'message': 'Bot not initialized'
            })
    
    engine = bot_state['engine']
    metrics = engine.metrics
    
    return jsonify({
        'running': bot_state['running'],
        'timestamp': datetime.now().isoformat(),
        'capital': {
            'current': round(engine.available_capital, 4),
            'initial': round(metrics.initial_capital_sol, 4),
            'peak': round(metrics.peak_capital_sol, 4),
            'roi': round(metrics.roi_percent, 2)
        },
        'trades': {
            'total': metrics.total_trades,
            'winning': metrics.winning_trades,
            'losing': metrics.losing_trades,
            'win_rate': round(metrics.win_rate, 2)
        },
        'pnl': {
            'total': round(metrics.total_pnl_sol, 4),
            'net': round(metrics.net_pnl, 4),
            'fees': round(metrics.total_fees_paid_sol, 4)
        }
    })


@app.route('/api/trades')
def get_trades():
    """Get trade history"""
    try:
        trade_log = Path('logs/trades.csv')
        if not trade_log.exists():
            return jsonify([])
        
        import csv
        trades = []
        with open(trade_log, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                trades.append({
                    'timestamp': row['timestamp'],
                    'symbol': row['token_symbol'],
                    'entry_price': float(row['entry_price']),
                    'exit_price': float(row['exit_price']) if row['exit_price'] else 0,
                    'pnl_sol': float(row['pnl_sol']),
                    'pnl_percent': float(row['pnl_percent']),
                    'outcome': row['outcome'],
                    'hold_time': float(row['hold_time_seconds']),
                    'exit_reason': row['exit_reason']
                })
        
        # Return latest 50 trades
        return jsonify(trades[-50:])
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/metrics')
def get_metrics():
    """Get detailed metrics"""
    try:
        metrics_file = Path('data/metrics.json')
        if metrics_file.exists():
            with open(metrics_file, 'r') as f:
                return jsonify(json.load(f))
        return jsonify({})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config')
def get_config_api():
    """Get current configuration"""
    if bot_state['config']:
        return jsonify(bot_state['config'].config)
    
    # Return default config if bot not initialized
    try:
        config = get_config()
        return jsonify(config.config)
    except:
        return jsonify({})


@app.route('/api/config/update', methods=['POST'])
def update_config():
    """Update configuration"""
    try:
        data = request.json
        
        if bot_state['running']:
            return jsonify({'error': 'Cannot update config while bot is running'}), 400
        
        # Update config file
        import yaml
        config_path = Path('config.yaml')
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Update mode
        if 'mode' in data:
            config['mode'] = data['mode']
            print(f"✅ Mode updated to: {data['mode']}")
        
        # Map frontend keys to config structure
        # Frontend sends: risk, entry, exit
        # Config has: strategy (with nested fields), risk
        
        if 'risk' in data:
            # Risk settings map to both strategy and risk sections
            for key, value in data['risk'].items():
                # These go to strategy section
                if key in ['max_position_size_percent', 'max_concurrent_trades']:
                    if 'strategy' not in config:
                        config['strategy'] = {}
                    config['strategy'][key] = value
                # These go to risk section
                elif key in config.get('risk', {}):
                    config['risk'][key] = value
        
        if 'entry' in data:
            # Entry settings go to strategy section
            if 'strategy' not in config:
                config['strategy'] = {}
            for key, value in data['entry'].items():
                # Map frontend keys to config keys
                if key == 'min_bonding_curve_percent':
                    config['strategy']['min_bonding_curve_progress'] = value
                elif key == 'max_bonding_curve_percent':
                    config['strategy']['max_bonding_curve_progress'] = value
                elif key in ['min_early_volume_sol', 'evaluation_window_seconds']:
                    config['strategy'][key] = value
        
        if 'exit' in data:
            # Exit settings go to strategy section
            if 'strategy' not in config:
                config['strategy'] = {}
            for key, value in data['exit'].items():
                config['strategy'][key] = value
        
        if 'wallet' in data:
            for key, value in data['wallet'].items():
                if key in config['wallet']:
                    config['wallet'][key] = value
        
        # Save config
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        print(f"✅ Config saved successfully. Mode: {config.get('mode', 'unknown')}")
        
        return jsonify({
            'success': True, 
            'message': 'Configuration updated',
            'mode': config.get('mode')
        })
    
    except Exception as e:
        print(f"❌ Error updating config: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/wallet/check', methods=['POST'])
def check_wallet():
    """Check wallet balance"""
    try:
        data = request.json
        # Accept both 'wallet_path' and 'keypair_path' for flexibility
        wallet_path = data.get('wallet_path') or data.get('keypair_path')
        
        if not wallet_path:
            return jsonify({'error': 'Wallet path required'}), 400
        
        # Check if file exists
        wallet_file = Path(wallet_path)
        if not wallet_file.exists():
            return jsonify({'error': f'Wallet file not found: {wallet_path}'}), 404
        
        # Try to load the actual wallet and check balance
        try:
            import json as json_lib
            from solders.keypair import Keypair as SoldersKeypair
            from solana.rpc.api import Client
            from solders.pubkey import Pubkey
            
            with open(wallet_file, 'r') as f:
                secret_key = json_lib.load(f)
            
            # Load keypair to get address
            keypair = SoldersKeypair.from_bytes(bytes(secret_key))
            address = str(keypair.pubkey())
            pubkey = Pubkey.from_string(address)
            
            # Query ACTUAL balance from Solana blockchain
            try:
                # Load RPC endpoint from config
                import yaml
                with open('config.yaml', 'r') as f:
                    config = yaml.safe_load(f)
                
                rpc_url = config['solana']['rpc_endpoint']
                client = Client(rpc_url)
                
                # Get balance (in lamports)
                response = client.get_balance(pubkey)
                lamports = response.value if hasattr(response, 'value') else 0
                
                # Convert lamports to SOL (1 SOL = 1_000_000_000 lamports)
                balance_sol = lamports / 1_000_000_000
                
                return jsonify({
                    'success': True,
                    'balance': balance_sol,
                    'address': address,
                    'exists': True,
                    'source': 'blockchain'  # Indicate this is real data
                })
            except Exception as rpc_error:
                # If RPC fails, still return the address but with 0 balance
                print(f"RPC Error: {rpc_error}")
                return jsonify({
                    'success': True,
                    'balance': 0.0,
                    'address': address,
                    'exists': True,
                    'error': f'Could not fetch balance from blockchain: {str(rpc_error)}'
                })
        except Exception as e:
            return jsonify({'error': f'Invalid wallet file: {str(e)}'}), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/wallet/create', methods=['POST'])
def create_wallet():
    """Create a new wallet"""
    try:
        data = request.json
        wallet_path = data.get('wallet_path', 'wallet.json')
        
        # Generate new keypair
        from solders.keypair import Keypair as SoldersKeypair
        import json as json_lib
        
        keypair = SoldersKeypair()
        
        # Save to file
        wallet_file = Path(wallet_path)
        wallet_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(wallet_file, 'w') as f:
            json_lib.dump(list(bytes(keypair)), f)
        
        return jsonify({
            'success': True,
            'path': wallet_path,
            'address': str(keypair.pubkey()),
            'message': 'Wallet created successfully'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/wallet/import', methods=['POST'])
def import_wallet():
    """Import wallet from private key (Phantom, Solflare, etc.)"""
    try:
        data = request.json
        private_key = data.get('private_key', '').strip()
        wallet_path = data.get('wallet_path', 'wallet.json')
        
        if not private_key:
            return jsonify({'error': 'Private key is required'}), 400
        
        from solders.keypair import Keypair as SoldersKeypair
        import json as json_lib
        import base58
        
        # Try to parse the private key (can be base58 string or array)
        try:
            # Try base58 decode first (most common format from Phantom)
            private_key_bytes = base58.b58decode(private_key)
            keypair = SoldersKeypair.from_bytes(private_key_bytes)
        except:
            try:
                # Try as JSON array [1,2,3,...]
                private_key_array = json_lib.loads(private_key)
                keypair = SoldersKeypair.from_bytes(bytes(private_key_array))
            except:
                return jsonify({'error': 'Invalid private key format. Please copy it exactly from Phantom.'}), 400
        
        # Save to file
        wallet_file = Path(wallet_path)
        wallet_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(wallet_file, 'w') as f:
            json_lib.dump(list(bytes(keypair)), f)
        
        return jsonify({
            'success': True,
            'path': wallet_path,
            'address': str(keypair.pubkey()),
            'message': 'Phantom wallet imported successfully'
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to import wallet: {str(e)}'}), 500


# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    emit('connected', {'message': 'Connected to Pump.fun Trading Bot'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')


@socketio.on('start_bot')
def handle_start_bot():
    """Start the trading bot"""
    print("🚀 Received start_bot request")
    
    if bot_state['running']:
        print("⚠️  Bot already running")
        emit('error', {'message': 'Bot is already running'})
        return
    
    def run_bot():
        print("🔧 Initializing bot...")
        bot = WebTradingBot()
        bot_state['bot'] = bot
        bot_state['config'] = bot.config
        
        try:
            print("🔧 Running bot.initialize()...")
            bot.run_async(bot.initialize())
            bot_state['engine'] = bot.trading_engine
            bot_state['running'] = True
            
            print("✅ Bot initialized successfully!")
            socketio.emit('bot_started', {'message': 'Bot started successfully'})
            
            # Run bot
            print("🚀 Starting bot main loop...")
            bot.run_async(bot.start())
        
        except Exception as e:
            import traceback
            print(f"❌ Error starting bot: {e}")
            print(f"❌ Traceback: {traceback.format_exc()}")
            bot_state['running'] = False
            socketio.emit('error', {'message': f'Failed to start bot: {str(e)}'})
    
    # Start bot in background thread
    print("🧵 Starting bot thread...")
    thread = threading.Thread(target=run_bot)
    thread.daemon = True
    thread.start()
    print("✅ Bot thread started!")


@socketio.on('stop_bot')
def handle_stop_bot():
    """Stop the trading bot"""
    if not bot_state['running']:
        emit('error', {'message': 'Bot is not running'})
        return
    
    def stop_bot():
        try:
            if bot_state['bot']:
                bot_state['bot'].run_async(bot_state['bot'].stop())
            bot_state['running'] = False
            bot_state['bot'] = None
            socketio.emit('bot_stopped', {'message': 'Bot stopped successfully'})
        except Exception as e:
            print(f"Error stopping bot: {e}")
            socketio.emit('error', {'message': f'Failed to stop bot: {str(e)}'})
    
    thread = threading.Thread(target=stop_bot)
    thread.daemon = True
    thread.start()


def main():
    """Run the web application"""
    print("\n" + "="*60)
    print("🚀 Pump.fun Trading Bot - Web Dashboard")
    print("="*60)
    print("\n📊 Starting web server...")
    print("\n🌐 Access the dashboard at:")
    print("   http://localhost:5001")
    print("\n💡 Press Ctrl+C to stop")
    print("="*60 + "\n")
    
    socketio.run(app, host='0.0.0.0', port=5001, debug=False, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    main()

