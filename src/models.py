"""
Data Models
Defines data structures for tokens, trades, and positions
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from decimal import Decimal


class TradeStatus(Enum):
    """Trade status enum"""
    PENDING = "pending"
    EVALUATING = "evaluating"
    BUYING = "buying"
    HOLDING = "holding"
    SELLING = "selling"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TradeOutcome(Enum):
    """Trade outcome enum"""
    PROFIT = "profit"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    FAILED = "failed"


@dataclass
class TokenInfo:
    """Information about a Pump.fun token"""
    mint: str
    name: str
    symbol: str
    creator: str
    bonding_curve: str
    associated_bonding_curve: str
    
    # Launch info
    created_at: datetime
    block_time: Optional[int] = None
    signature: Optional[str] = None
    
    # Market data
    initial_price: Optional[float] = None
    current_price: Optional[float] = None
    market_cap: Optional[float] = None
    bonding_curve_progress: Optional[float] = None  # % of curve filled
    
    # Volume and activity
    total_volume_sol: Optional[float] = None
    trade_count: Optional[int] = None
    holder_count: Optional[int] = None
    
    # Flags
    is_graduated: bool = False
    is_suspicious: bool = False
    
    def __repr__(self) -> str:
        return f"Token({self.symbol}/{self.mint[:8]}...)"


@dataclass
class Position:
    """Represents an open trading position"""
    token: TokenInfo
    
    # Entry details
    entry_time: datetime
    entry_price: float
    entry_sol_amount: float
    entry_token_amount: float
    entry_signature: Optional[str] = None
    
    # Current state
    current_price: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = 0.0
    
    # P&L tracking
    unrealized_pnl_sol: float = 0.0
    unrealized_pnl_percent: float = 0.0
    
    # Risk management
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    trailing_stop_price: Optional[float] = None
    
    # Status
    status: TradeStatus = TradeStatus.HOLDING
    
    def update_price(self, new_price: float):
        """Update current price and recalculate metrics"""
        self.current_price = new_price
        
        # Update highs/lows
        if new_price > self.highest_price:
            self.highest_price = new_price
        if self.lowest_price == 0 or new_price < self.lowest_price:
            self.lowest_price = new_price
        
        # Calculate unrealized P&L
        if self.entry_token_amount > 0:
            current_value = self.current_price * self.entry_token_amount
            self.unrealized_pnl_sol = current_value - self.entry_sol_amount
            self.unrealized_pnl_percent = (
                (self.current_price / self.entry_price - 1) * 100
            )
    
    def update_trailing_stop(self, trailing_stop_percent: float):
        """Update trailing stop based on highest price"""
        if self.highest_price > 0:
            self.trailing_stop_price = self.highest_price * (1 - trailing_stop_percent / 100)
    
    @property
    def hold_time_seconds(self) -> float:
        """Calculate how long position has been held"""
        return (datetime.now() - self.entry_time).total_seconds()
    
    @property
    def is_profitable(self) -> bool:
        """Check if position is currently profitable"""
        return self.unrealized_pnl_sol > 0
    
    def __repr__(self) -> str:
        return (
            f"Position({self.token.symbol}, "
            f"Entry: {self.entry_price:.6f}, "
            f"Current: {self.current_price:.6f}, "
            f"P&L: {self.unrealized_pnl_percent:.2f}%)"
        )


@dataclass
class Trade:
    """Completed trade record"""
    token: TokenInfo
    
    # Entry
    entry_time: datetime
    entry_price: float
    entry_sol_amount: float
    entry_token_amount: float
    entry_signature: Optional[str] = None
    
    # Exit
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_sol_amount: Optional[float] = None
    exit_signature: Optional[str] = None
    
    # Results
    pnl_sol: float = 0.0
    pnl_percent: float = 0.0
    outcome: TradeOutcome = TradeOutcome.BREAKEVEN
    
    # Trade details
    hold_time_seconds: float = 0.0
    fees_paid_sol: float = 0.0
    exit_reason: str = "unknown"
    
    # Status
    status: TradeStatus = TradeStatus.COMPLETED
    notes: str = ""
    
    @classmethod
    def from_position(cls, position: Position, exit_price: float, 
                      exit_sol_amount: float, exit_reason: str,
                      fees_paid: float = 0.0, exit_signature: str = None) -> 'Trade':
        """Create a Trade from a closed Position"""
        exit_time = datetime.now()
        hold_time = (exit_time - position.entry_time).total_seconds()
        
        pnl_sol = exit_sol_amount - position.entry_sol_amount - fees_paid
        pnl_percent = (exit_price / position.entry_price - 1) * 100
        
        # Determine outcome
        if pnl_sol > 0.001:  # Small threshold for floating point
            outcome = TradeOutcome.PROFIT
        elif pnl_sol < -0.001:
            outcome = TradeOutcome.LOSS
        else:
            outcome = TradeOutcome.BREAKEVEN
        
        return cls(
            token=position.token,
            entry_time=position.entry_time,
            entry_price=position.entry_price,
            entry_sol_amount=position.entry_sol_amount,
            entry_token_amount=position.entry_token_amount,
            entry_signature=position.entry_signature,
            exit_time=exit_time,
            exit_price=exit_price,
            exit_sol_amount=exit_sol_amount,
            exit_signature=exit_signature,
            pnl_sol=pnl_sol,
            pnl_percent=pnl_percent,
            outcome=outcome,
            hold_time_seconds=hold_time,
            fees_paid_sol=fees_paid,
            exit_reason=exit_reason,
            status=TradeStatus.COMPLETED
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trade to dictionary for logging"""
        return {
            'token_mint': self.token.mint,
            'token_symbol': self.token.symbol,
            'entry_time': self.entry_time.isoformat(),
            'entry_price': self.entry_price,
            'entry_sol': self.entry_sol_amount,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'exit_price': self.exit_price,
            'exit_sol': self.exit_sol_amount,
            'pnl_sol': self.pnl_sol,
            'pnl_percent': self.pnl_percent,
            'outcome': self.outcome.value,
            'hold_time_seconds': self.hold_time_seconds,
            'fees_paid_sol': self.fees_paid_sol,
            'exit_reason': self.exit_reason,
            'entry_signature': self.entry_signature,
            'exit_signature': self.exit_signature,
            'notes': self.notes
        }
    
    def __repr__(self) -> str:
        return (
            f"Trade({self.token.symbol}, "
            f"{self.outcome.value}, "
            f"P&L: {self.pnl_sol:.4f} SOL ({self.pnl_percent:.2f}%))"
        )


@dataclass
class BotMetrics:
    """Bot performance metrics"""
    start_time: datetime = field(default_factory=datetime.now)
    
    # Capital tracking
    initial_capital_sol: float = 0.0
    current_capital_sol: float = 0.0
    peak_capital_sol: float = 0.0
    
    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0
    
    # P&L
    total_pnl_sol: float = 0.0
    total_fees_paid_sol: float = 0.0
    best_trade_pnl_sol: float = 0.0
    worst_trade_pnl_sol: float = 0.0
    
    # Performance
    win_rate: float = 0.0
    average_pnl_sol: float = 0.0
    average_pnl_percent: float = 0.0
    
    # Risk
    max_drawdown_sol: float = 0.0
    max_drawdown_percent: float = 0.0
    
    # Activity
    tokens_evaluated: int = 0
    tokens_skipped: int = 0
    
    def update_from_trade(self, trade: Trade):
        """Update metrics after a trade"""
        self.total_trades += 1
        
        if trade.outcome == TradeOutcome.PROFIT:
            self.winning_trades += 1
        elif trade.outcome == TradeOutcome.LOSS:
            self.losing_trades += 1
        else:
            self.breakeven_trades += 1
        
        self.total_pnl_sol += trade.pnl_sol
        self.total_fees_paid_sol += trade.fees_paid_sol
        
        if trade.pnl_sol > self.best_trade_pnl_sol:
            self.best_trade_pnl_sol = trade.pnl_sol
        if trade.pnl_sol < self.worst_trade_pnl_sol:
            self.worst_trade_pnl_sol = trade.pnl_sol
        
        # Recalculate derived metrics
        if self.total_trades > 0:
            self.win_rate = (self.winning_trades / self.total_trades) * 100
            self.average_pnl_sol = self.total_pnl_sol / self.total_trades
    
    def update_capital(self, new_capital: float):
        """Update current capital and track peaks/drawdowns"""
        self.current_capital_sol = new_capital
        
        if new_capital > self.peak_capital_sol:
            self.peak_capital_sol = new_capital
        
        # Calculate drawdown from peak
        if self.peak_capital_sol > 0:
            drawdown = self.peak_capital_sol - new_capital
            drawdown_percent = (drawdown / self.peak_capital_sol) * 100
            
            if drawdown > self.max_drawdown_sol:
                self.max_drawdown_sol = drawdown
            if drawdown_percent > self.max_drawdown_percent:
                self.max_drawdown_percent = drawdown_percent
    
    @property
    def roi_percent(self) -> float:
        """Calculate return on investment"""
        if self.initial_capital_sol == 0:
            return 0.0
        return ((self.current_capital_sol - self.initial_capital_sol) / 
                self.initial_capital_sol) * 100
    
    @property
    def net_pnl(self) -> float:
        """Net P&L after fees"""
        return self.total_pnl_sol - self.total_fees_paid_sol
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            'start_time': self.start_time.isoformat(),
            'runtime_hours': (datetime.now() - self.start_time).total_seconds() / 3600,
            'initial_capital_sol': self.initial_capital_sol,
            'current_capital_sol': self.current_capital_sol,
            'peak_capital_sol': self.peak_capital_sol,
            'roi_percent': self.roi_percent,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'total_pnl_sol': self.total_pnl_sol,
            'net_pnl_sol': self.net_pnl,
            'total_fees_paid_sol': self.total_fees_paid_sol,
            'average_pnl_sol': self.average_pnl_sol,
            'best_trade_pnl_sol': self.best_trade_pnl_sol,
            'worst_trade_pnl_sol': self.worst_trade_pnl_sol,
            'max_drawdown_sol': self.max_drawdown_sol,
            'max_drawdown_percent': self.max_drawdown_percent,
            'tokens_evaluated': self.tokens_evaluated,
            'tokens_skipped': self.tokens_skipped
        }

