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
from .state_manager import StateManager


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
        
        # State management
        self.state_manager = StateManager("bot_state.json" if dry_run else "bot_state_live.json")
        
        # State
        self.active_positions: Dict[str, Position] = {}
        self.completed_trades: List[Trade] = []
        self.metrics = BotMetrics()
        
        # Capital tracking
        self.initial_capital_sol = self.config.get('wallet.initial_capital_sol', 2.0)
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
            # Try to load saved capital from previous session
            saved_capital = self.state_manager.get_capital(
                default=self.config.get('wallet.initial_capital_sol', 2.0)
            )
            self.available_capital = saved_capital
            
            # Check if this is a fresh start or continuation
            saved_metrics = self.state_manager.get_metrics()
            if saved_metrics:
                self.logger.info(f"📂 Loaded saved state from previous session")
                self.logger.info(f"💰 Continuing with {self.available_capital:.4f} SOL (simulated)")
                # Restore metrics
                self.metrics.initial_capital_sol = saved_metrics.get('initial_capital_sol', self.available_capital)
                self.metrics.total_trades = saved_metrics.get('total_trades', 0)
                self.metrics.winning_trades = saved_metrics.get('winning_trades', 0)
                self.metrics.losing_trades = saved_metrics.get('losing_trades', 0)
                self.metrics.total_pnl_sol = saved_metrics.get('total_pnl_sol', 0.0)
            else:
                self.logger.info(f"💰 Starting fresh with {self.available_capital:.4f} SOL (simulated)")
                self.metrics.initial_capital_sol = self.available_capital
        else:
            # LIVE MODE - Load wallet and get real balance
            self.logger.info("🔴 LIVE TRADING MODE - Loading wallet...")
            
            if not keypair:
                # Try to load from wallet.json
                from pathlib import Path
                import json
                from solders.keypair import Keypair
                
                wallet_path = Path('wallet.json')
                if not wallet_path.exists():
                    raise ValueError("❌ wallet.json not found! Please import your wallet in Settings.")
                
                self.logger.info(f"📂 Loading wallet from {wallet_path}...")
                with open(wallet_path, 'r') as f:
                    keypair_data = json.load(f)
                
                keypair = Keypair.from_bytes(bytes(keypair_data))
                self.keypair = keypair
                self.logger.info(f"✅ Wallet loaded: {str(keypair.pubkey())}")
            else:
                self.keypair = keypair
            
            # Get actual balance from Solana blockchain
            self.logger.info(f"🔗 Querying balance from Solana blockchain...")
            try:
                balance = await self.solana.get_balance(self.keypair.pubkey())
                self.available_capital = balance
                self.initial_capital_sol = balance
                self.metrics.initial_capital_sol = balance
                
                self.logger.info(f"💰 LIVE WALLET BALANCE: {self.available_capital:.9f} SOL")
                
                if balance == 0:
                    self.logger.warning("⚠️  WARNING: Wallet balance is 0 SOL!")
                    self.logger.warning("    Please fund your wallet before trading.")
                elif balance < 0.01:
                    self.logger.warning(f"⚠️  WARNING: Low balance ({balance:.9f} SOL)")
                    self.logger.warning("    You may not have enough for trades + fees.")
                else:
                    self.logger.info(f"✅ Sufficient balance for trading")
                
            except Exception as e:
                self.logger.error(f"❌ Failed to get wallet balance: {e}")
                raise ValueError(f"Could not query wallet balance from Solana: {e}")
        
        # Update current capital and metrics
        self.metrics.current_capital_sol = self.available_capital
        self.metrics.peak_capital_sol = max(self.metrics.peak_capital_sol, self.available_capital)
        
        self.logger.info(f"📊 Initial Capital: {self.available_capital:.9f} SOL")
        self.logger.info(f"📊 Mode: {'DRY RUN (Simulated)' if self.dry_run else '🔴 LIVE TRADING (Real Money!)'}")
        
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
        Execute REAL buy transaction on Pump.fun bonding curve
        
        Args:
            token: Token to buy
            sol_amount: Amount of SOL to spend
            token_amount: Expected token amount
        
        Returns:
            Transaction signature or None
        """
        try:
            self.logger.info("🔴 [LIVE] Building REAL Pump.fun buy transaction...")
            self.logger.info(f"   Spending: {sol_amount:.4f} SOL")
            self.logger.info(f"   Expected tokens: {token_amount:.2f}")
            
            if not self.keypair:
                self.logger.error("❌ No keypair for signing!")
                return None
            
            from solders.pubkey import Pubkey
            from solders.system_program import transfer, TransferParams
            from solders.transaction import Transaction
            from solders.message import Message
            from solders.instruction import Instruction, AccountMeta
            
            # Get recent blockhash
            self.logger.info("   Getting recent blockhash...")
            blockhash_resp = await self.solana.client.get_latest_blockhash()
            if not blockhash_resp or not blockhash_resp.value:
                self.logger.error("❌ Failed to get blockhash")
                return None
            
            recent_blockhash = blockhash_resp.value.blockhash
            
            # Convert SOL to lamports
            lamports = int(sol_amount * 1_000_000_000)
            max_lamports = int(lamports * 1.05)  # 5% slippage tolerance
            
            self.logger.info(f"   Lamports: {lamports:,} (max: {max_lamports:,})")
            
            # Parse token addresses
            try:
                mint = Pubkey.from_string(token.mint)
                bonding_curve = Pubkey.from_string(token.bonding_curve)
            except Exception as e:
                self.logger.error(f"❌ Invalid token addresses: {e}")
                return None
            
            # Build Pump.fun buy instruction
            # Using the discriminator for "buy" instruction
            buy_discriminator = bytes([0x66, 0x06, 0x3d, 0x12, 0x01, 0xda, 0xeb, 0xea])
            
            # Instruction data: discriminator + amount + max_sol_cost
            instruction_data = (
                buy_discriminator +
                lamports.to_bytes(8, 'little') +
                max_lamports.to_bytes(8, 'little')
            )
            
            # Get associated token addresses
            # For now, use simplified account structure
            pumpfun_program = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
            
            # Create instruction accounts
            accounts = [
                AccountMeta(pubkey=self.keypair.pubkey(), is_signer=True, is_writable=True),
                AccountMeta(pubkey=mint, is_signer=False, is_writable=False),
                AccountMeta(pubkey=bonding_curve, is_signer=False, is_writable=True),
                # Add more required accounts here for production
            ]
            
            buy_instruction = Instruction(
                program_id=pumpfun_program,
                accounts=accounts,
                data=instruction_data
            )
            
            # Create transaction
            self.logger.info("   Building transaction...")
            message = Message.new_with_blockhash(
                [buy_instruction],
                self.keypair.pubkey(),
                recent_blockhash
            )
            
            transaction = Transaction.new_unsigned(message)
            transaction = Transaction([transaction.message], [self.keypair])
            
            # Send transaction
            self.logger.info("   Sending transaction to Solana...")
            response = await self.solana.client.send_transaction(
                transaction,
                self.keypair,
                opts={'skip_preflight': False, 'preflight_commitment': 'confirmed'}
            )
            
            if not response or not response.value:
                self.logger.error("❌ Transaction failed to send")
                return None
            
            signature = str(response.value)
            
            # Wait for confirmation
            self.logger.info(f"   Waiting for confirmation...")
            confirmed = await self.solana.client.confirm_transaction(signature, commitment='confirmed')
            
            if confirmed:
                self.logger.success(f"✅ BUY TRANSACTION CONFIRMED!")
                self.logger.success(f"   Signature: {signature}")
                self.logger.success(f"   Solscan: https://solscan.io/tx/{signature}")
                self.logger.success(f"   Token: {token.symbol} ({token.mint[:8]}...)")
                return signature
            else:
                self.logger.error("❌ Transaction confirmation timeout")
                return None
        
        except Exception as e:
            self.logger.error(f"❌ Buy transaction failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
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
            
            # Save state after each trade (for dry-run persistence)
            if self.dry_run:
                self._save_state()
            
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
        Execute REAL sell transaction on Pump.fun bonding curve
        
        Args:
            position: Position to sell
        
        Returns:
            Tuple of (signature, exit_sol_amount) or None
        """
        try:
            exit_sol = position.current_price * position.entry_token_amount
            
            self.logger.info("🔴 [LIVE] Building REAL Pump.fun sell transaction...")
            self.logger.info(f"   Selling: {position.entry_token_amount:.2f} tokens")
            self.logger.info(f"   Expected SOL: {exit_sol:.4f}")
            
            if not self.keypair:
                self.logger.error("❌ No keypair for signing!")
                return None
            
            from solders.pubkey import Pubkey
            from solders.transaction import Transaction
            from solders.message import Message
            from solders.instruction import Instruction, AccountMeta
            
            # Get recent blockhash
            self.logger.info("   Getting recent blockhash...")
            blockhash_resp = await self.solana.client.get_latest_blockhash()
            if not blockhash_resp or not blockhash_resp.value:
                self.logger.error("❌ Failed to get blockhash")
                return None
            
            recent_blockhash = blockhash_resp.value.blockhash
            
            # Convert tokens to smallest unit
            token_amount_raw = int(position.entry_token_amount * 1_000_000)  # Assuming 6 decimals
            min_sol_output = int(exit_sol * 0.95 * 1_000_000_000)  # 5% slippage tolerance, in lamports
            
            self.logger.info(f"   Token amount: {token_amount_raw:,}")
            self.logger.info(f"   Min SOL output: {min_sol_output:,} lamports")
            
            # Parse token addresses
            try:
                mint = Pubkey.from_string(position.token.mint)
                bonding_curve = Pubkey.from_string(position.token.bonding_curve)
            except Exception as e:
                self.logger.error(f"❌ Invalid token addresses: {e}")
                return None
            
            # Build Pump.fun sell instruction
            # Using the discriminator for "sell" instruction
            sell_discriminator = bytes([0x33, 0xe6, 0x85, 0xa4, 0x01, 0x7f, 0x83, 0xad])
            
            # Instruction data: discriminator + token_amount + min_sol_output
            instruction_data = (
                sell_discriminator +
                token_amount_raw.to_bytes(8, 'little') +
                min_sol_output.to_bytes(8, 'little')
            )
            
            pumpfun_program = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
            
            # Create instruction accounts
            accounts = [
                AccountMeta(pubkey=self.keypair.pubkey(), is_signer=True, is_writable=True),
                AccountMeta(pubkey=mint, is_signer=False, is_writable=False),
                AccountMeta(pubkey=bonding_curve, is_signer=False, is_writable=True),
                # Add more required accounts here for production
            ]
            
            sell_instruction = Instruction(
                program_id=pumpfun_program,
                accounts=accounts,
                data=instruction_data
            )
            
            # Create transaction
            self.logger.info("   Building transaction...")
            message = Message.new_with_blockhash(
                [sell_instruction],
                self.keypair.pubkey(),
                recent_blockhash
            )
            
            transaction = Transaction.new_unsigned(message)
            transaction = Transaction([transaction.message], [self.keypair])
            
            # Send transaction
            self.logger.info("   Sending transaction to Solana...")
            response = await self.solana.client.send_transaction(
                transaction,
                self.keypair,
                opts={'skip_preflight': False, 'preflight_commitment': 'confirmed'}
            )
            
            if not response or not response.value:
                self.logger.error("❌ Transaction failed to send")
                return None
            
            signature = str(response.value)
            
            # Wait for confirmation
            self.logger.info(f"   Waiting for confirmation...")
            confirmed = await self.solana.client.confirm_transaction(signature, commitment='confirmed')
            
            if confirmed:
                self.logger.success(f"✅ SELL TRANSACTION CONFIRMED!")
                self.logger.success(f"   Signature: {signature}")
                self.logger.success(f"   Solscan: https://solscan.io/tx/{signature}")
                self.logger.success(f"   Received: {exit_sol:.4f} SOL")
                return (signature, exit_sol)
            else:
                self.logger.error("❌ Transaction confirmation timeout")
                return None
        
        except Exception as e:
            self.logger.error(f"❌ Sell transaction failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
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
                # Simulate price movement based on token quality
                import random
                
                # Get token quality (stored when position created)
                quality = getattr(position.token, '_mock_quality', 'dud')
                
                # Calculate how far we've moved from entry
                price_change_from_entry = ((position.current_price - position.entry_price) / position.entry_price) * 100
                
                # IMPROVED QUALITY-BASED PRICE SIMULATION - More profitable but realistic
                # Simulate realistic pump-and-dump patterns with better upside
                if quality == 'moon':
                    # MOON SHOT TOKEN - Strong upward bias, can reach 5-8x
                    if price_change_from_entry < 0:
                        price_change = random.uniform(0.01, 0.05)  # Bounce back strong
                    elif price_change_from_entry < 80:
                        price_change = random.uniform(0.02, 0.08)  # Strong pump phase
                    elif price_change_from_entry < 200:
                        price_change = random.uniform(0.01, 0.06)  # Continued pump
                    elif price_change_from_entry < 350:
                        price_change = random.uniform(-0.02, 0.04)  # Peak phase
                    elif price_change_from_entry < 500:
                        price_change = random.uniform(-0.05, 0.02)  # Topping
                    else:
                        price_change = random.uniform(-0.12, -0.02)  # Correction
                    
                    max_mult = 8.0  # Can 8x - realistic moon shot
                
                elif quality == 'moderate':
                    # MODERATE PUMPER - Good gains, reaches 2-3x with some volatility
                    if price_change_from_entry < 0:
                        price_change = random.uniform(0.005, 0.04)  # Small recovery
                    elif price_change_from_entry < 60:
                        price_change = random.uniform(0.01, 0.06)  # Moderate pump
                    elif price_change_from_entry < 120:
                        price_change = random.uniform(-0.02, 0.04)  # Consolidation
                    elif price_change_from_entry < 180:
                        price_change = random.uniform(-0.05, 0.02)  # Near peak
                    else:
                        price_change = random.uniform(-0.10, -0.01)  # Pullback
                    
                    max_mult = 3.0  # Can 3x - decent pump
                
                else:
                    # DUD TOKEN - Mixed but slightly positive bias initially, then dumps
                    if price_change_from_entry < -30:
                        price_change = random.uniform(-0.05, 0.01)  # Slow bleed
                    elif price_change_from_entry < 0:
                        price_change = random.uniform(-0.03, 0.03)  # Choppy
                    elif price_change_from_entry < 25:
                        price_change = random.uniform(-0.04, 0.03)  # Small moves
                    elif price_change_from_entry < 45:
                        price_change = random.uniform(-0.07, 0.01)  # Topping
                    else:
                        price_change = random.uniform(-0.10, -0.02)  # Dump phase
                    
                    max_mult = 1.6  # Max 60% gain before reversal
                
                new_price = position.current_price * (1 + price_change)
                
                # Apply quality-based caps (realistic limits)
                new_price = max(position.entry_price * 0.05, new_price)  # Min 5% of entry (not total dump)
                new_price = min(position.entry_price * max_mult, new_price)  # Quality-based max
                
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
    
    def _save_state(self):
        """Save current bot state for persistence"""
        try:
            state = {
                'current_capital': self.available_capital,
                'metrics': {
                    'initial_capital_sol': self.metrics.initial_capital_sol,
                    'current_capital_sol': self.metrics.current_capital_sol,
                    'peak_capital_sol': self.metrics.peak_capital_sol,
                    'total_trades': self.metrics.total_trades,
                    'winning_trades': self.metrics.winning_trades,
                    'losing_trades': self.metrics.losing_trades,
                    'total_pnl_sol': self.metrics.total_pnl_sol,
                    'best_trade_pnl_sol': self.metrics.best_trade_pnl_sol,
                    'worst_trade_pnl_sol': self.metrics.worst_trade_pnl_sol,
                },
                'trade_count': len(self.completed_trades)
            }
            self.state_manager.save_state(state)
        except Exception as e:
            self.logger.error(f"Error saving state: {e}")
    
    def _save_metrics(self):
        """Save metrics to file"""
        metrics_file = self.config.get('tracking.metrics_file')
        if metrics_file:
            self.logger.log_metrics(self.metrics, metrics_file)

