"""
Configuration Management
Handles loading and validating configuration from YAML and environment variables
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration manager for the trading bot"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize configuration
        
        Args:
            config_path: Path to YAML configuration file
        """
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._override_from_env()
        self._validate()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _override_from_env(self):
        """Override config values from environment variables"""
        # RPC endpoints
        if rpc := os.getenv('SOLANA_RPC_ENDPOINT'):
            self.config['solana']['rpc_endpoint'] = rpc
        if ws := os.getenv('SOLANA_WS_ENDPOINT'):
            self.config['solana']['ws_endpoint'] = ws
        
        # Trading mode
        if mode := os.getenv('TRADING_MODE'):
            self.config['mode'] = mode
        
        # API keys
        if bitquery_key := os.getenv('BITQUERY_API_KEY'):
            self.config['data_sources']['bitquery']['api_key'] = bitquery_key
        if helius_key := os.getenv('HELIUS_API_KEY'):
            self.config['data_sources']['helius']['api_key'] = helius_key
        
        # Telegram
        if tg_token := os.getenv('TELEGRAM_BOT_TOKEN'):
            self.config['logging']['telegram']['bot_token'] = tg_token
        if tg_chat := os.getenv('TELEGRAM_CHAT_ID'):
            self.config['logging']['telegram']['chat_id'] = tg_chat
    
    def _validate(self):
        """Validate configuration values"""
        # Check mode
        if self.config['mode'] not in ['dry_run', 'live']:
            raise ValueError("Mode must be 'dry_run' or 'live'")
        
        # Validate percentages
        strategy = self.config['strategy']
        if not 0 < strategy['max_position_size_percent'] <= 100:
            raise ValueError("max_position_size_percent must be between 0 and 100")
        
        # Check wallet file exists in live mode
        if self.config['mode'] == 'live':
            wallet_path = Path(self.config['wallet']['keypair_path'])
            if not wallet_path.exists():
                raise FileNotFoundError(
                    f"Wallet keypair not found: {wallet_path}. "
                    "Create one or switch to dry_run mode."
                )
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation path
        
        Args:
            key_path: Dot-separated path (e.g., 'solana.rpc_endpoint')
            default: Default value if key not found
        
        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def is_dry_run(self) -> bool:
        """Check if in dry-run mode"""
        return self.config['mode'] == 'dry_run'
    
    def is_live(self) -> bool:
        """Check if in live trading mode"""
        return self.config['mode'] == 'live'
    
    @property
    def trading_mode(self) -> str:
        """Get current trading mode"""
        return self.config['mode']
    
    def __repr__(self) -> str:
        return f"Config(mode={self.config['mode']}, path={self.config_path})"


# Global config instance
_config: Optional[Config] = None


def get_config(config_path: str = "config.yaml") -> Config:
    """
    Get global configuration instance
    
    Args:
        config_path: Path to configuration file
    
    Returns:
        Config instance
    """
    global _config
    if _config is None:
        _config = Config(config_path)
    return _config


def reload_config(config_path: str = "config.yaml") -> Config:
    """
    Reload configuration from file
    
    Args:
        config_path: Path to configuration file
    
    Returns:
        New Config instance
    """
    global _config
    _config = Config(config_path)
    return _config

