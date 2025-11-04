#!/usr/bin/env python3
"""
Flask Web Dashboard for Pump.fun Trading Bot
Beautiful real-time monitoring interface
"""

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
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

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
        await self.trading_engine.start(keypair=None)
        
        # Emit updates periodically
        while self.running:
            await asyncio.sleep(2)  # Update every 2 seconds
            if self.running:
                self.emit_update()
    
    def emit_update(self):
        """Emit bot status update via WebSocket"""
        try:
            if not self.trading_engine:
                return
                
            metrics = self.trading_engine.metrics
            
            # Calculate true current capital (available + positions value)
            current_capital = self.trading_engine.available_capital
            
            # Add value of open positions
            for position in self.trading_engine.active_positions.values():
                position_value = position.current_price * position.entry_token_amount
                current_capital += position_value
            
            # Update metrics with current capital
            metrics.update_capital(current_capital)
            
            # Force recalculate ROI
            if metrics.initial_capital_sol > 0:
                metrics.current_capital_sol = current_capital
                roi = ((current_capital - metrics.initial_capital_sol) / metrics.initial_capital_sol) * 100
            else:
                roi = 0.0
            
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
            
            socketio.emit('bot_update', update_data)
        except Exception as e:
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


@app.route('/api/status')
def get_status():
    """Get current bot status"""
    if not bot_state['engine']:
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
        
        # Update specific fields
        if 'mode' in data:
            config['mode'] = data['mode']
        
        if 'strategy' in data:
            for key, value in data['strategy'].items():
                if key in config['strategy']:
                    config['strategy'][key] = value
        
        if 'risk' in data:
            for key, value in data['risk'].items():
                if key in config['risk']:
                    config['risk'][key] = value
        
        if 'wallet' in data:
            for key, value in data['wallet'].items():
                if key in config['wallet']:
                    config['wallet'][key] = value
        
        # Save config
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return jsonify({'success': True, 'message': 'Configuration updated'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/wallet/check', methods=['POST'])
def check_wallet():
    """Check wallet balance"""
    try:
        data = request.json
        keypair_path = data.get('keypair_path')
        
        if not keypair_path:
            return jsonify({'error': 'Wallet path required'}), 400
        
        # Check if file exists
        wallet_file = Path(keypair_path)
        if not wallet_file.exists():
            return jsonify({'error': f'Wallet file not found: {keypair_path}'}), 404
        
        # Try to load the actual wallet and check balance
        try:
            import json as json_lib
            with open(wallet_file, 'r') as f:
                secret_key = json_lib.load(f)
            
            # For now, return mock data (in production this would check actual balance)
            return jsonify({
                'success': True,
                'balance': 2.5,
                'address': f'{keypair_path[:20]}...',
                'exists': True
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
    if bot_state['running']:
        emit('error', {'message': 'Bot is already running'})
        return
    
    def run_bot():
        bot = WebTradingBot()
        bot_state['bot'] = bot
        bot_state['config'] = bot.config
        
        try:
            bot.run_async(bot.initialize())
            bot_state['engine'] = bot.trading_engine
            bot_state['running'] = True
            
            socketio.emit('bot_started', {'message': 'Bot started successfully'})
            
            # Run bot
            bot.run_async(bot.start())
        
        except Exception as e:
            print(f"Error starting bot: {e}")
            bot_state['running'] = False
            socketio.emit('error', {'message': f'Failed to start bot: {str(e)}'})
    
    # Start bot in background thread
    thread = threading.Thread(target=run_bot)
    thread.daemon = True
    thread.start()


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

