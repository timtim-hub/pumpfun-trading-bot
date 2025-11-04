#!/usr/bin/env python3
"""
Pump.fun Trading Bot
Main entry point for the automated trading bot
"""

import asyncio
import argparse
import signal
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import get_config
from src.logger import get_logger
from src.solana_client import SolanaClient, PumpFunClient
from src.real_detector import RealLaunchDetector
from src.risk_manager import RiskManager
from src.trading_engine import TradingEngine


class TradingBot:
    """Main trading bot coordinator"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize trading bot
        
        Args:
            config_path: Path to configuration file
        """
        self.config = get_config(config_path)
        self.logger = get_logger(
            log_file=self.config.get('logging.log_file'),
            trade_log_file=self.config.get('logging.trade_log_file'),
            level=self.config.get('logging.level', 'INFO')
        )
        
        self.solana_client = None
        self.pumpfun_client = None
        self.detector = None
        self.risk_manager = None
        self.trading_engine = None
        
        # Flag for graceful shutdown
        self.shutdown_requested = False
    
    async def initialize(self):
        """Initialize all components"""
        self.logger.info("🔧 Initializing components...")
        
        # Initialize Solana client
        self.solana_client = SolanaClient(
            rpc_endpoint=self.config.get('solana.rpc_endpoint'),
            ws_endpoint=self.config.get('solana.ws_endpoint'),
            commitment=self.config.get('solana.commitment', 'confirmed')
        )
        
        # Connect to Solana
        connected = await self.solana_client.connect()
        if not connected:
            raise Exception("Failed to connect to Solana RPC")
        
        # Initialize Pump.fun client
        self.pumpfun_client = PumpFunClient(self.solana_client)
        
        # Initialize detector (REAL in both modes)
        self.detector = RealLaunchDetector(
            self.solana_client,
            self.pumpfun_client
        )
        self.logger.info("✓ Using REAL detector for both dry-run and live modes")
        
        # Initialize risk manager
        self.risk_manager = RiskManager(self.config.config)
        
        # Load keypair if in live mode
        keypair = None
        if self.config.is_live():
            keypair_path = self.config.get('wallet.keypair_path')
            if not keypair_path:
                raise ValueError("Keypair path required for live trading")
            
            keypair = self.solana_client.load_keypair(keypair_path)
            if not keypair:
                raise Exception("Failed to load keypair")
        
        # Initialize trading engine
        self.trading_engine = TradingEngine(
            config=self.config,
            solana_client=self.solana_client,
            pumpfun_client=self.pumpfun_client,
            detector=self.detector,
            risk_manager=self.risk_manager,
            dry_run=self.config.is_dry_run()
        )
        
        self.logger.success("✅ All components initialized")
        
        return keypair
    
    async def run(self):
        """Run the trading bot"""
        try:
            # Initialize components
            keypair = await self.initialize()
            
            # Start trading engine
            await self.trading_engine.start(keypair)
            
            # Keep running until shutdown
            while not self.shutdown_requested:
                await asyncio.sleep(1)
        
        except KeyboardInterrupt:
            self.logger.info("\n⚠️  Keyboard interrupt received")
        except Exception as e:
            self.logger.error(f"Fatal error: {e}")
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Gracefully shutdown the bot"""
        if self.shutdown_requested:
            return
        
        self.shutdown_requested = True
        
        # Stop trading engine
        if self.trading_engine:
            await self.trading_engine.stop()
        
        # Disconnect from Solana
        if self.solana_client:
            await self.solana_client.disconnect()
        
        self.logger.info("👋 Goodbye!")
    
    def handle_signal(self, signum, frame):
        """Handle OS signals for graceful shutdown"""
        self.logger.info(f"\n⚠️  Received signal {signum}")
        self.shutdown_requested = True


async def main():
    """Main entry point"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Pump.fun Trading Bot - Automated meme token trading on Solana"
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='Path to configuration file (default: config.yaml)'
    )
    
    parser.add_argument(
        '--mode',
        type=str,
        choices=['dry_run', 'live'],
        help='Trading mode (overrides config file)'
    )
    
    parser.add_argument(
        '--create-keypair',
        type=str,
        metavar='PATH',
        help='Create a new keypair and save to PATH, then exit'
    )
    
    parser.add_argument(
        '--check-balance',
        type=str,
        metavar='KEYPAIR_PATH',
        help='Check balance of keypair and exit'
    )
    
    args = parser.parse_args()
    
    # Handle utility commands
    if args.create_keypair:
        # Create new keypair
        from src.solana_client import SolanaClient
        
        print(f"Creating new keypair...")
        client = SolanaClient("", "")
        keypair = client.create_keypair(args.create_keypair)
        print(f"✅ Keypair created and saved to: {args.create_keypair}")
        print(f"   Public key: {keypair.pubkey()}")
        print(f"\n⚠️  IMPORTANT: Keep this file secure and backed up!")
        print(f"   Fund this wallet with SOL before trading.")
        return
    
    if args.check_balance:
        # Check wallet balance
        from src.solana_client import SolanaClient
        from src.config import get_config
        
        config = get_config(args.config)
        client = SolanaClient(
            config.get('solana.rpc_endpoint'),
            config.get('solana.ws_endpoint')
        )
        
        await client.connect()
        keypair = client.load_keypair(args.check_balance)
        
        if keypair:
            balance = await client.get_balance(keypair.pubkey())
            print(f"\n💰 Wallet Balance")
            print(f"   Address: {keypair.pubkey()}")
            print(f"   Balance: {balance:.6f} SOL")
            print(f"   USD Value: ~${balance * 50:.2f} (assuming $50/SOL)\n")
        
        await client.disconnect()
        return
    
    # Override config mode if specified
    if args.mode:
        import os
        os.environ['TRADING_MODE'] = args.mode
    
    # Create and run bot
    bot = TradingBot(args.config)
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, lambda s, f: bot.handle_signal(s, f))
    signal.signal(signal.SIGTERM, lambda s, f: bot.handle_signal(s, f))
    
    # Run the bot
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Exiting...")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)

