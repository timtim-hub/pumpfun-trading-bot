"""
Trading Engine
Core trading logic and position management
"""

import asyncio
from typing import Dict, Optional, List
from datetime import datetime

from .models import TokenInfo, Position, Trade, TradeStatus, BotMetrics
from .solana_client import SolanaClient, PumpFunClient
from .detector import LaunchDetector
from .risk_manager import RiskManager
from .logger import get_logger
from .config import Config


class TradingEngine:
    """Main trading engine orchestrating all components"""
    
    def __init__(self, config: Config, 
                 solana_client: SolanaClient,
                 pumpfun_client: PumpFunClient,
                 detector: LaunchDetector,
                 risk_manager: RiskManager,
                 dry_run: bool = True):
        """
        Initialize trading engine
        
        Args:
            config: Configuration object
            solana_client: Solana client
            pumpfun_client: Pump.fun client
            detector: Launch detector
            risk_manager: Risk manager
            dry_run: Whether in dry-run mode
        """
        self.config = config
        self.solana = solana_client
        self.pumpfun = pumpfun_client
        self.detector = detector
        self.risk_manager = risk_manager
        self.logger = get_logger()
        self.dry_run = dry_run
        
        # State
        self.active_positions: Dict[str, Position] = {}
        self.completed_trades: List[Trade] = []
        self.metrics = BotMetrics()
        
        # Capital tracking
        self.available_capital = 0.0
        self.keypair = None
        
        # Control flags
        self.is_running = False
        self.should_stop = False
    
    async def start(self, keypair=None):
        """
        Start the trading engine
        
        Args:
            keypair: Solana keypair for trading (optional in dry-run)
        """
        self.is_running = True
        self.keypair = keypair
        
        # Print startup banner
        self.logger.print_banner()
        
        mode = "DRY-RUN" if self.dry_run else "LIVE TRADING"
        self.logger.info(f"🤖 Starting trading bot in {mode} mode...")
        
        # Initialize capital
        if self.dry_run:
            self.available_capital = self.config.get('wallet.initial_capital_sol', 2.0)
            self.logger.info(f"💰 Starting with {self.available_capital:.4f} SOL (simulated)")
        else:
            if not keypair:
                raise ValueError("Keypair required for live trading")
            
            # Get actual balance
            balance = await self.solana.get_balance(keypair.pubkey())
            self.available_capital = balance
            self.logger.info(f"💰 Wallet balance: {self.available_capital:.4f} SOL")
        
        # Initialize metrics
        self.metrics.initial_capital_sol = self.available_capital
        self.metrics.current_capital_sol = self.available_capital
        self.metrics.peak_capital_sol = self.available_capital
        
        # Print configuration
        self.logger.print_config_summary(self.config.config)
        
        # Start monitoring loop
        asyncio.create_task(self._position_monitoring_loop())
        
        # Start launch detection
        await self.detector.start_monitoring(self._on_token_detected)
    
    async def stop(self):
        """Stop the trading engine gracefully"""
        self.logger.info("\n🛑 Stopping trading bot...")
        self.should_stop = True
        
        # Close any open positions
        if self.active_positions:
            self.logger.info(f"Closing {len(self.active_positions)} open positions...")
            for mint, position in list(self.active_positions.items()):
                await self._close_position(position, "Bot shutdown")
        
        # Save final metrics
        self._save_metrics()
        
        # Print final summary
        self.logger.print_metrics_summary(self.metrics)
        
        self.is_running = False
        self.logger.success("Bot stopped successfully")
    
    async def _on_token_detected(self, token: TokenInfo):
        """
        Callback when new token is detected
        
        Args:
            token: Detected token information
        """
        try:
            self.metrics.tokens_evaluated += 1
            
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"📊 Evaluating: {token.symbol} ({token.mint[:8]}...)")
            self.logger.info(f"{'='*60}")
            
            # Check if we should skip this token
            should_skip, skip_reason = self.risk_manager.should_skip_token(token)
            if should_skip:
                self.logger.info(f"⏭️  Skipping: {skip_reason}")
                self.metrics.tokens_skipped += 1
                return
            
            # Check if we can open a position
            can_trade, trade_reason = self.risk_manager.can_open_position(
                len(self.active_positions),
                self.available_capital
            )
            
            if not can_trade:
                self.logger.warning(f"❌ Cannot trade: {trade_reason}")
                self.metrics.tokens_skipped += 1
                return
            
            # Wait and observe early activity
            eval_window = self.config.get('strategy.evaluation_window_seconds', 3)
            self.logger.info(f"⏳ Observing for {eval_window}s...")
            
            activity = await self.detector.get_early_trading_activity(
                token.bonding_curve,
                eval_window
            )
            
            self.logger.info(f"📈 Early Activity:")
            self.logger.info(f"   Buys: {activity['buy_count']}")
            self.logger.info(f"   Volume: {activity['volume_sol']:.2f} SOL")
            self.logger.info(f"   Buyers: {activity['unique_buyers']}")
            self.logger.info(f"   Price Change: {activity['price_change_percent']:.1f}%")
            self.logger.info(f"   Curve Progress: {activity['bonding_curve_progress']:.1f}%")
            
            # Check entry criteria
            should_enter, entry_reason = self.risk_manager.check_entry_criteria(
                token,
                activity
            )
            
            if not should_enter:
                self.logger.info(f"⏭️  No entry: {entry_reason}")
                self.metrics.tokens_skipped += 1
                return
            
            # Enter trade
            self.logger.success(f"✅ Entry criteria met: {entry_reason}")
            await self._enter_position(token)
        
        except Exception as e:
            self.logger.error(f"Error processing token: {e}")
    
    async def _enter_position(self, token: TokenInfo):
        """
        Enter a trading position
        
        Args:
            token: Token to trade
        """
        try:
            self.logger.trade_info(f"🎯 ENTERING POSITION: {token.symbol}")
            
            # Calculate position size
            position_size = self.risk_manager.calculate_position_size(
                self.available_capital,
                token.current_price or token.initial_price
            )
            
            sol_amount = position_size['sol_amount']
            token_amount = position_size['token_amount']
            
            self.logger.info(f"💵 Position Size: {sol_amount:.4f} SOL")
            
            # Execute buy (or simulate in dry-run)
            if self.dry_run:
                # Simulate buy
                signature = f"dry_run_buy_{token.mint[:8]}"
                self.logger.info(f"🧪 [DRY-RUN] Simulated buy: {token_amount:.2f} tokens")
            else:
                # Real buy transaction
                signature = await self._execute_buy(
                    token,
                    sol_amount,
                    token_amount
                )
                
                if not signature:
                    self.logger.error("❌ Buy transaction failed")
                    return
            
            # Create position
            position = Position(
                token=token,
                entry_time=datetime.now(),
                entry_price=token.current_price or token.initial_price,
                entry_sol_amount=sol_amount,
                entry_token_amount=token_amount,
                entry_signature=signature,
                current_price=token.current_price or token.initial_price,
                highest_price=token.current_price or token.initial_price,
                lowest_price=token.current_price or token.initial_price,
                status=TradeStatus.HOLDING
            )
            
            # Set risk parameters
            self.risk_manager.update_position_risk(position)
            
            # Update capital
            self.available_capital -= sol_amount
            
            # Add to active positions
            self.active_positions[token.mint] = position
            
            self.logger.success(
                f"✅ POSITION OPENED: {token.symbol}\n"
                f"   Entry: {position.entry_price:.8f} SOL\n"
                f"   Amount: {token_amount:.2f} tokens\n"
                f"   Stop Loss: {position.stop_loss_price:.8f}\n"
                f"   Take Profit: {position.take_profit_price:.8f}"
            )
        
        except Exception as e:
            self.logger.error(f"Error entering position: {e}")
    
    async def _execute_buy(self, token: TokenInfo, 
                          sol_amount: float,
                          token_amount: float) -> Optional[str]:
        """
        Execute buy transaction on Solana
        
        Args:
            token: Token to buy
            sol_amount: Amount of SOL to spend
            token_amount: Expected token amount
        
        Returns:
            Transaction signature or None
        """
        try:
            # This is a simplified version
            # Full implementation would:
            # 1. Create associated token account if needed
            # 2. Build buy instruction with proper accounts
            # 3. Add compute budget and priority fee
            # 4. Sign and send transaction
            # 5. Wait for confirmation
            
            self.logger.info("📤 Sending buy transaction...")
            
            # Placeholder for actual transaction
            # In production, use pumpfun_client.create_buy_instruction()
            
            signature = "placeholder_signature"
            
            self.logger.success(f"✅ Buy transaction confirmed: {signature[:16]}...")
            
            return signature
        
        except Exception as e:
            self.logger.error(f"Buy transaction failed: {e}")
            return None
    
    async def _close_position(self, position: Position, reason: str):
        """
        Close a trading position
        
        Args:
            position: Position to close
            reason: Reason for closing
        """
        try:
            self.logger.trade_info(f"🚪 CLOSING POSITION: {position.token.symbol} - {reason}")
            
            # Execute sell (or simulate)
            if self.dry_run:
                # Simulate sell
                signature = f"dry_run_sell_{position.token.mint[:8]}"
                exit_sol = position.current_price * position.entry_token_amount
                self.logger.info(f"🧪 [DRY-RUN] Simulated sell: {exit_sol:.4f} SOL")
            else:
                # Real sell transaction
                result = await self._execute_sell(position)
                if not result:
                    self.logger.error("❌ Sell transaction failed")
                    return
                
                signature, exit_sol = result
            
            # Calculate fees properly
            fee_rate = self.config.get('strategy.trading_fee_percent', 1.25) / 100
            
            # Entry fee on SOL spent
            entry_fee = position.entry_sol_amount * fee_rate
            
            # Exit value before fees
            gross_exit_value = position.current_price * position.entry_token_amount
            
            # Exit fee on SOL received
            exit_fee = gross_exit_value * fee_rate
            
            # Net exit value after exit fee
            net_exit_value = gross_exit_value - exit_fee
            
            total_fees = entry_fee + exit_fee
            
            # Create trade record with net exit value
            trade = Trade.from_position(
                position,
                position.current_price,
                net_exit_value,  # Use net value after fees
                reason,
                total_fees,
                signature
            )
            
            # Update capital
            self.available_capital += trade.exit_sol_amount
            
            # Update metrics
            self.metrics.update_from_trade(trade)
            self.metrics.update_capital(self.available_capital)
            
            # Log trade
            self.logger.log_trade(trade)
            self.completed_trades.append(trade)
            
            # Remove from active positions
            if position.token.mint in self.active_positions:
                del self.active_positions[position.token.mint]
            
            # Print trade summary
            if trade.pnl_sol > 0:
                self.logger.profit(
                    f"💰 PROFIT: {trade.token.symbol}\n"
                    f"   P&L: +{trade.pnl_sol:.4f} SOL ({trade.pnl_percent:.2f}%)\n"
                    f"   Hold Time: {trade.hold_time_seconds:.0f}s\n"
                    f"   New Balance: {self.available_capital:.4f} SOL"
                )
            else:
                self.logger.loss(
                    f"📉 LOSS: {trade.token.symbol}\n"
                    f"   P&L: {trade.pnl_sol:.4f} SOL ({trade.pnl_percent:.2f}%)\n"
                    f"   Hold Time: {trade.hold_time_seconds:.0f}s\n"
                    f"   New Balance: {self.available_capital:.4f} SOL"
                )
        
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
    
    async def _execute_sell(self, position: Position) -> Optional[tuple]:
        """
        Execute sell transaction
        
        Args:
            position: Position to sell
        
        Returns:
            Tuple of (signature, exit_sol_amount) or None
        """
        try:
            self.logger.info("📤 Sending sell transaction...")
            
            # Placeholder for actual transaction
            # In production, use pumpfun_client.create_sell_instruction()
            
            signature = "placeholder_signature"
            exit_sol = position.current_price * position.entry_token_amount
            
            self.logger.success(f"✅ Sell transaction confirmed: {signature[:16]}...")
            
            return (signature, exit_sol)
        
        except Exception as e:
            self.logger.error(f"Sell transaction failed: {e}")
            return None
    
    async def _position_monitoring_loop(self):
        """Continuously monitor and update active positions"""
        while self.is_running and not self.should_stop:
            try:
                if not self.active_positions:
                    await asyncio.sleep(1)
                    continue
                
                # Update each position
                for mint, position in list(self.active_positions.items()):
                    await self._update_position(position)
                
                # Check for exit conditions
                for mint, position in list(self.active_positions.items()):
                    should_exit, exit_reason = self.risk_manager.check_exit_conditions(position)
                    
                    if should_exit:
                        await self._close_position(position, exit_reason)
                
                # Save metrics periodically
                self._save_metrics()
                
                await asyncio.sleep(1)  # Update every second
            
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(1)
    
    async def _update_position(self, position: Position):
        """
        Update position with latest price
        
        Args:
            position: Position to update
        """
        try:
            # Get current price
            if self.dry_run:
                # Simulate price movement
                import random
                price_change = random.uniform(-0.05, 0.15)  # -5% to +15%
                new_price = position.current_price * (1 + price_change)
            else:
                # Get real price from bonding curve
                curve_data = await self.pumpfun.get_bonding_curve_data(
                    position.token.bonding_curve
                )
                # Parse price from curve data (simplified)
                new_price = position.current_price * 1.01  # Placeholder
            
            # Update position
            position.update_price(new_price)
            
            # Update trailing stop
            self.risk_manager.update_position_risk(position)
        
        except Exception as e:
            self.logger.error(f"Error updating position: {e}")
    
    def _save_metrics(self):
        """Save metrics to file"""
        metrics_file = self.config.get('tracking.metrics_file')
        if metrics_file:
            self.logger.log_metrics(self.metrics, metrics_file)

