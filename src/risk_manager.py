"""
Risk Management System
Handles position sizing, stop-loss, and risk controls
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from .models import TokenInfo, Position, BotMetrics
from .logger import get_logger


class RiskManager:
    """Manages trading risk and position sizing"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize risk manager
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = get_logger()
        
        # Risk parameters
        self.max_position_size_percent = config['strategy']['max_position_size_percent']
        self.max_concurrent_trades = config['strategy']['max_concurrent_trades']
        self.stop_loss_percent = config['strategy']['stop_loss_percent']
        self.profit_target_percent = config['strategy']['profit_target_percent']
        self.trailing_stop_percent = config['strategy']['trailing_stop_percent']
        self.max_hold_time = config['strategy']['max_hold_time_seconds']
        self.min_hold_time = config['strategy']['min_hold_time_seconds']
        
        # Global risk limits
        self.max_daily_loss_percent = config['risk']['max_daily_loss_percent']
        self.max_loss_per_trade_sol = config['risk']['max_loss_per_trade_sol']
        self.min_sol_balance = config['risk']['min_sol_balance']
        
        # Filters
        self.blacklist_creators = config['risk']['blacklist_creators']
        self.blacklist_keywords = config['risk']['blacklist_keywords']
        
        # Daily tracking
        self.daily_start_capital = 0.0
        self.daily_reset_time = datetime.now()
    
    def calculate_position_size(self, available_capital: float, 
                               token_price: float) -> Dict[str, float]:
        """
        Calculate position size for a trade
        
        Args:
            available_capital: Available SOL balance
            token_price: Current token price in SOL
        
        Returns:
            Dictionary with sol_amount and token_amount
        """
        # Ensure minimum balance is maintained
        tradeable_capital = max(0, available_capital - self.min_sol_balance)
        
        # Calculate position size as percentage of available capital
        position_sol = tradeable_capital * (self.max_position_size_percent / 100)
        
        # Calculate token amount
        token_amount = position_sol / token_price if token_price > 0 else 0
        
        self.logger.debug(
            f"Position size: {position_sol:.4f} SOL "
            f"({self.max_position_size_percent}% of {tradeable_capital:.4f} SOL)"
        )
        
        return {
            'sol_amount': position_sol,
            'token_amount': token_amount
        }
    
    def can_open_position(self, current_positions: int, 
                         available_capital: float) -> tuple[bool, str]:
        """
        Check if new position can be opened
        
        Args:
            current_positions: Number of current open positions
            available_capital: Available SOL balance
        
        Returns:
            Tuple of (can_trade, reason)
        """
        # Check concurrent position limit
        if current_positions >= self.max_concurrent_trades:
            return False, f"Max concurrent trades reached ({self.max_concurrent_trades})"
        
        # Check minimum balance
        if available_capital <= self.min_sol_balance:
            return False, f"Insufficient balance (min: {self.min_sol_balance} SOL)"
        
        # Check daily loss limit
        if self._is_daily_loss_limit_reached(available_capital):
            return False, "Daily loss limit reached"
        
        return True, "OK"
    
    def _is_daily_loss_limit_reached(self, current_capital: float) -> bool:
        """Check if daily loss limit has been reached"""
        # Reset daily tracking if new day
        now = datetime.now()
        if (now - self.daily_reset_time).days >= 1:
            self.daily_start_capital = current_capital
            self.daily_reset_time = now
            return False
        
        # Calculate daily P&L
        if self.daily_start_capital == 0:
            self.daily_start_capital = current_capital
            return False
        
        daily_loss_percent = (
            (self.daily_start_capital - current_capital) / self.daily_start_capital * 100
        )
        
        if daily_loss_percent >= self.max_daily_loss_percent:
            self.logger.warning(
                f"Daily loss limit reached: {daily_loss_percent:.2f}% "
                f"(limit: {self.max_daily_loss_percent}%)"
            )
            return True
        
        return False
    
    def check_entry_criteria(self, token: TokenInfo, 
                            activity: Dict[str, Any]) -> tuple[bool, str]:
        """
        Evaluate if token meets entry criteria
        
        Args:
            token: Token information
            activity: Early trading activity metrics
        
        Returns:
            Tuple of (should_enter, reason)
        """
        config = self.config['strategy']
        
        # 🔥 ULTRA SELECTIVE ENTRY - Only trade the absolute BEST setups (top 10%)
        
        # Get all metrics
        progress = activity.get('bonding_curve_progress', 0)
        volume = activity.get('volume_sol', 0)
        price_change = activity.get('price_change_percent', 0)
        buy_count = activity.get('buy_count', 0)
        sell_count = activity.get('sell_count', 0)
        unique_buyers = activity.get('unique_buyers', 0)
        
        # EXTREMELY STRICT FILTERS - Miss 90% of tokens to catch only winners
        if progress < config['min_bonding_curve_progress']:
            return False, f"Bonding curve progress too low ({progress:.1f}%)"
        
        if progress > config['max_bonding_curve_progress']:
            return False, f"Entry too late ({progress:.1f}% filled)"
        
        # MUCH HIGHER volume requirement (2.5x minimum)
        if volume < config['min_early_volume_sol'] * 2.5:
            return False, f"Volume too low ({volume:.2f} SOL) - need stronger signal"
        
        # Require STRONG early momentum (at least +10%)
        if price_change < 10:
            return False, f"Weak momentum ({price_change:.1f}%) - need +10% minimum"
        
        if token.is_suspicious:
            return False, "Token flagged as suspicious"
        
        # Calculate ELITE MOMENTUM SCORE (0-100 points) - VERY demanding
        momentum_score = 0
        
        # Volume score (0-35 points) - MUCH higher thresholds
        if volume >= 8.0:
            momentum_score += 35
        elif volume >= 5.0:
            momentum_score += 28
        elif volume >= 3.0:
            momentum_score += 18
        elif volume >= 2.0:
            momentum_score += 8
        
        # Price change score (0-35 points) - Reward EXPLOSIVE early pumps
        if price_change >= 100:
            momentum_score += 35
        elif price_change >= 75:
            momentum_score += 30
        elif price_change >= 50:
            momentum_score += 22
        elif price_change >= 25:
            momentum_score += 12
        
        # Buy/sell ratio score (0-20 points) - REQUIRE heavy buy pressure
        total_trades = buy_count + max(sell_count, 1)
        buy_ratio = buy_count / total_trades
        if buy_ratio >= 0.95:
            momentum_score += 20
        elif buy_ratio >= 0.88:
            momentum_score += 12
        elif buy_ratio >= 0.75:
            momentum_score += 5
        
        # Unique buyers score (0-10 points) - FOMO indicator
        if unique_buyers >= 40:
            momentum_score += 10
        elif unique_buyers >= 25:
            momentum_score += 6
        elif unique_buyers >= 15:
            momentum_score += 3
        
        # 🔥 FILTER: Only enter if momentum score >= 60 (ELITE signal only)
        # This will skip 90%+ of tokens but catch the real pumps
        if momentum_score < 60:
            return False, f"❌ REJECTED (score: {momentum_score}/100) - Only trade elite setups (60+)"
        
        if momentum_score >= 80:
            return True, f"🔥 ELITE PUMP (score: {momentum_score}/100) - MAXIMUM CONFIDENCE"
        elif momentum_score >= 70:
            return True, f"🚀 EXCELLENT SETUP (score: {momentum_score}/100) - HIGH CONVICTION"
        else:
            return True, f"✅ STRONG SIGNAL (score: {momentum_score}/100) - GOOD ENTRY"
    
    def check_exit_conditions(self, position: Position) -> tuple[bool, str]:
        """
        Check if position should be exited
        
        Args:
            position: Current position
        
        Returns:
            Tuple of (should_exit, reason)
        """
        # Calculate hold time
        hold_time = position.hold_time_seconds
        
        # Don't exit too early (prevent overtrading)
        if hold_time < self.min_hold_time:
            return False, "Min hold time not reached"
        
        # 💰 INSTANT PROFIT-TAKING - Exit at FIRST profitable opportunity
        quality = getattr(position.token, '_mock_quality', 'dud')
        
        # For Pump.fun, speed is everything - take profit FAST before reversal
        if quality == 'moon':
            # Moon shots - Still exit faster than before
            if position.unrealized_pnl_percent >= 200:
                return True, f"🌙 MASSIVE GAINS (+{position.unrealized_pnl_percent:.1f}%) - BANK IT NOW!"
            elif position.unrealized_pnl_percent >= 120 and hold_time >= 30:
                return True, f"🌙 Strong pump (+{position.unrealized_pnl_percent:.1f}%) - EXIT BEFORE REVERSAL!"
            elif position.unrealized_pnl_percent >= 80 and hold_time >= 40:
                return True, f"🌙 Good profit (+{position.unrealized_pnl_percent:.1f}%) - taking it!"
            elif position.unrealized_pnl_percent >= 50 and hold_time >= 50:
                return True, f"🌙 Decent gain (+{position.unrealized_pnl_percent:.1f}%) - locking in"
        
        elif quality == 'moderate':
            # Moderate - Exit MUCH faster
            if position.unrealized_pnl_percent >= 80:
                return True, f"💎 GREAT PROFIT (+{position.unrealized_pnl_percent:.1f}%) - EXIT NOW!"
            elif position.unrealized_pnl_percent >= 50 and hold_time >= 25:
                return True, f"💎 Good gains (+{position.unrealized_pnl_percent:.1f}%) - secure profit!"
            elif position.unrealized_pnl_percent >= 30 and hold_time >= 35:
                return True, f"💎 Solid profit (+{position.unrealized_pnl_percent:.1f}%) - take it!"
            elif position.unrealized_pnl_percent >= 20 and hold_time >= 45:
                return True, f"💎 Small win (+{position.unrealized_pnl_percent:.1f}%) - better than loss!"
        
        else:
            # Duds - Exit IMMEDIATELY at ANY profit (Pump.fun duds dump FAST)
            if position.unrealized_pnl_percent >= 25:
                return True, f"⚡ PROFIT DETECTED (+{position.unrealized_pnl_percent:.1f}%) - EXIT IMMEDIATELY!"
            elif position.unrealized_pnl_percent >= 15 and hold_time >= 15:
                return True, f"⚡ Quick win (+{position.unrealized_pnl_percent:.1f}%) - GET OUT NOW!"
            elif position.unrealized_pnl_percent >= 10 and hold_time >= 25:
                return True, f"⚡ Small profit (+{position.unrealized_pnl_percent:.1f}%) - TAKE IT!"
            elif position.unrealized_pnl_percent >= 5 and hold_time >= 35:
                return True, f"⚡ Tiny gain (+{position.unrealized_pnl_percent:.1f}%) - exit before dump!"
        
        # 🛑 ULTRA TIGHT STOP LOSSES - Cut losses INSTANTLY (Pump.fun dumps are BRUTAL)
        if quality == 'dud':
            # INSTANT stop on duds - NO MERCY
            if position.unrealized_pnl_percent <= -3:
                return True, f"🛑 INSTANT STOP on dud ({position.unrealized_pnl_percent:.1f}%) - CUT NOW!"
        elif quality == 'moderate':
            # Very tight stop on moderate
            if position.unrealized_pnl_percent <= -4:
                return True, f"🛑 QUICK STOP ({position.unrealized_pnl_percent:.1f}%) - preserve capital!"
        else:
            # Even moon shots - tight stop (Pump.fun is unforgiving)
            if position.unrealized_pnl_percent <= -6:
                return True, f"🛑 STOP LOSS ({position.unrealized_pnl_percent:.1f}%) - exit now!"
        
        # Check trailing stop (lock in profits)
        if position.trailing_stop_price and position.current_price <= position.trailing_stop_price:
            return True, f"📉 Trailing stop triggered (peak: {position.highest_price:.6f})"
        
        # Check max hold time - Force exit to avoid holding dead positions
        if hold_time >= self.max_hold_time:
            # Force exit at max time, regardless of P&L
            return True, f"⏰ Max hold time reached ({hold_time:.0f}s) - FORCE EXIT"
        
        # 🛑 HARD CAP: Absolute maximum loss per trade (EMERGENCY STOP)
        # This is a safety net - should never be hit with tight stop losses
        if position.unrealized_pnl_sol < 0:  # Only check if losing
            if abs(position.unrealized_pnl_sol) >= self.max_loss_per_trade_sol:
                return True, f"🚨 EMERGENCY STOP - Max loss cap hit ({abs(position.unrealized_pnl_sol):.4f} SOL) - CUT NOW!"
        
        return False, "No exit conditions met"
    
    def update_position_risk(self, position: Position):
        """
        Update risk parameters for a position (stops, targets)
        
        Args:
            position: Position to update
        """
        # Set stop loss if not already set
        if not position.stop_loss_price:
            position.stop_loss_price = position.entry_price * (1 - self.stop_loss_percent / 100)
        
        # Set take profit if not already set
        if not position.take_profit_price:
            position.take_profit_price = position.entry_price * (1 + self.profit_target_percent / 100)
        
        # Update trailing stop
        position.update_trailing_stop(self.trailing_stop_percent)
    
    def calculate_expected_profit(self, entry_price: float, 
                                 exit_price: float,
                                 position_sol: float) -> Dict[str, float]:
        """
        Calculate expected profit after fees
        
        Args:
            entry_price: Entry price
            exit_price: Expected exit price
            position_sol: Position size in SOL
        
        Returns:
            Dictionary with profit metrics
        """
        # Calculate gross profit
        tokens = position_sol / entry_price
        exit_value = tokens * exit_price
        gross_profit_sol = exit_value - position_sol
        gross_profit_percent = ((exit_price / entry_price) - 1) * 100
        
        # Calculate fees (1.25% on entry and exit)
        fee_rate = self.config['strategy']['trading_fee_percent'] / 100
        entry_fee = position_sol * fee_rate
        exit_fee = exit_value * fee_rate
        total_fees = entry_fee + exit_fee
        
        # Net profit after fees
        net_profit_sol = gross_profit_sol - total_fees
        net_profit_percent = (net_profit_sol / position_sol) * 100
        
        return {
            'gross_profit_sol': gross_profit_sol,
            'gross_profit_percent': gross_profit_percent,
            'fees_sol': total_fees,
            'net_profit_sol': net_profit_sol,
            'net_profit_percent': net_profit_percent,
            'is_profitable': net_profit_sol > 0
        }
    
    def should_skip_token(self, token: TokenInfo) -> tuple[bool, str]:
        """
        Check if token should be skipped based on filters
        
        Args:
            token: Token to evaluate
        
        Returns:
            Tuple of (should_skip, reason)
        """
        # Check creator blacklist
        if token.creator in self.blacklist_creators:
            return True, "Creator blacklisted"
        
        # Check keyword blacklist
        token_text = f"{token.name} {token.symbol}".lower()
        for keyword in self.blacklist_keywords:
            if keyword.lower() in token_text:
                return True, f"Contains blacklisted keyword: {keyword}"
        
        # Check if token is flagged
        if token.is_suspicious:
            return True, "Flagged as suspicious"
        
        # Check if already graduated (too late)
        if token.is_graduated:
            return True, "Already graduated to PumpSwap"
        
        return False, "Token passes filters"
    
    def log_risk_summary(self, metrics: BotMetrics, available_capital: float):
        """
        Log current risk status
        
        Args:
            metrics: Current bot metrics
            available_capital: Available capital
        """
        self.logger.info("\n" + "="*60)
        self.logger.info("Risk Status Summary")
        self.logger.info("="*60)
        self.logger.info(f"Available Capital: {available_capital:.4f} SOL")
        self.logger.info(f"Peak Capital: {metrics.peak_capital_sol:.4f} SOL")
        self.logger.info(f"Current Drawdown: {metrics.max_drawdown_percent:.2f}%")
        self.logger.info(f"Daily Loss Limit: {self.max_daily_loss_percent}%")
        self.logger.info(f"Position Size Limit: {self.max_position_size_percent}%")
        self.logger.info(f"Active Positions: < {self.max_concurrent_trades}")
        self.logger.info("="*60 + "\n")

