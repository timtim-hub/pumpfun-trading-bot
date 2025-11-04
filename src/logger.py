"""
Logging System
Handles console logging, file logging, and trade history recording
"""

import logging
import sys
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

from .models import Trade, BotMetrics


# Custom theme for rich console
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "trade": "bold magenta",
    "profit": "bold green",
    "loss": "bold red"
})

console = Console(theme=custom_theme)


class TradingLogger:
    """Enhanced logger for trading bot with rich formatting"""
    
    def __init__(self, name: str = "PumpFunBot", 
                 log_file: Optional[str] = None,
                 trade_log_file: Optional[str] = None,
                 level: str = "INFO"):
        """
        Initialize trading logger
        
        Args:
            name: Logger name
            log_file: Path to log file
            trade_log_file: Path to trade CSV log
            level: Logging level (DEBUG, INFO, WARNING, ERROR)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Remove existing handlers
        self.logger.handlers = []
        
        # Rich console handler
        console_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            rich_tracebacks=True
        )
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(console_handler)
        
        # File handler
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_path)
            file_handler.setFormatter(
                logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
            )
            self.logger.addHandler(file_handler)
        
        # Trade log CSV
        self.trade_log_file = trade_log_file
        if trade_log_file:
            trade_path = Path(trade_log_file)
            trade_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create CSV with headers if it doesn't exist
            if not trade_path.exists():
                with open(trade_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        'timestamp', 'token_mint', 'token_symbol',
                        'entry_time', 'entry_price', 'entry_sol',
                        'exit_time', 'exit_price', 'exit_sol',
                        'pnl_sol', 'pnl_percent', 'outcome',
                        'hold_time_seconds', 'fees_paid', 'exit_reason',
                        'entry_signature', 'exit_signature'
                    ])
    
    def info(self, message: str):
        """Log info message"""
        self.logger.info(message)
    
    def debug(self, message: str):
        """Log debug message"""
        self.logger.debug(message)
    
    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """Log error message"""
        self.logger.error(message)
    
    def success(self, message: str):
        """Log success message in green"""
        console.print(f"✓ {message}", style="success")
        self.logger.info(message)
    
    def trade_info(self, message: str):
        """Log trade-related message"""
        console.print(f"💰 {message}", style="trade")
        self.logger.info(message)
    
    def profit(self, message: str):
        """Log profit message"""
        console.print(f"📈 {message}", style="profit")
        self.logger.info(message)
    
    def loss(self, message: str):
        """Log loss message"""
        console.print(f"📉 {message}", style="loss")
        self.logger.info(message)
    
    def new_token(self, token_symbol: str, mint: str):
        """Log new token detection"""
        console.print(f"\n🚀 [bold cyan]New Token Detected:[/bold cyan] {token_symbol} ({mint[:8]}...)")
        self.logger.info(f"New token: {token_symbol} ({mint})")
    
    def log_trade(self, trade: Trade):
        """
        Log completed trade to CSV
        
        Args:
            trade: Completed trade object
        """
        if not self.trade_log_file:
            return
        
        try:
            with open(self.trade_log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    trade.token.mint,
                    trade.token.symbol,
                    trade.entry_time.isoformat(),
                    trade.entry_price,
                    trade.entry_sol_amount,
                    trade.exit_time.isoformat() if trade.exit_time else '',
                    trade.exit_price or '',
                    trade.exit_sol_amount or '',
                    trade.pnl_sol,
                    trade.pnl_percent,
                    trade.outcome.value,
                    trade.hold_time_seconds,
                    trade.fees_paid_sol,
                    trade.exit_reason,
                    trade.entry_signature or '',
                    trade.exit_signature or ''
                ])
        except Exception as e:
            self.error(f"Failed to log trade to CSV: {e}")
    
    def log_metrics(self, metrics: BotMetrics, metrics_file: Optional[str] = None):
        """
        Log bot metrics to JSON file
        
        Args:
            metrics: Bot metrics object
            metrics_file: Path to metrics JSON file
        """
        if not metrics_file:
            return
        
        try:
            metrics_path = Path(metrics_file)
            metrics_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(metrics_path, 'w') as f:
                json.dump(metrics.to_dict(), f, indent=2)
        except Exception as e:
            self.error(f"Failed to save metrics: {e}")
    
    def print_banner(self):
        """Print startup banner"""
        banner = """
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║           🚀 PUMP.FUN TRADING BOT 🚀                     ║
║                                                           ║
║     Automated Solana Meme Token Trading System           ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
        """
        console.print(banner, style="bold cyan")
    
    def print_config_summary(self, config: Dict[str, Any]):
        """Print configuration summary"""
        mode = config.get('mode', 'unknown')
        mode_style = "bold green" if mode == "dry_run" else "bold red"
        
        console.print(f"\n📋 [bold]Configuration:[/bold]")
        console.print(f"   Mode: [{mode_style}]{mode.upper()}[/{mode_style}]")
        console.print(f"   Max Position Size: {config.get('strategy', {}).get('max_position_size_percent', 0)}%")
        console.print(f"   Profit Target: {config.get('strategy', {}).get('profit_target_percent', 0)}%")
        console.print(f"   Stop Loss: {config.get('strategy', {}).get('stop_loss_percent', 0)}%")
        console.print(f"   Max Hold Time: {config.get('strategy', {}).get('max_hold_time_seconds', 0)}s\n")
    
    def print_metrics_summary(self, metrics: BotMetrics):
        """Print performance metrics summary"""
        console.print(f"\n📊 [bold]Performance Metrics:[/bold]")
        console.print(f"   Capital: {metrics.current_capital_sol:.4f} SOL")
        console.print(f"   ROI: {metrics.roi_percent:.2f}%")
        console.print(f"   Total Trades: {metrics.total_trades}")
        console.print(f"   Win Rate: {metrics.win_rate:.2f}%")
        console.print(f"   Total P&L: {metrics.total_pnl_sol:.4f} SOL")
        console.print(f"   Net P&L: {metrics.net_pnl:.4f} SOL (after fees)")
        console.print(f"   Max Drawdown: {metrics.max_drawdown_percent:.2f}%\n")


# Global logger instance
_logger: Optional[TradingLogger] = None


def get_logger(name: str = "PumpFunBot", 
               log_file: Optional[str] = None,
               trade_log_file: Optional[str] = None,
               level: str = "INFO") -> TradingLogger:
    """
    Get global logger instance
    
    Args:
        name: Logger name
        log_file: Path to log file
        trade_log_file: Path to trade CSV log
        level: Logging level
    
    Returns:
        TradingLogger instance
    """
    global _logger
    if _logger is None:
        _logger = TradingLogger(name, log_file, trade_log_file, level)
    return _logger

