"""
State Manager for Trading Bot
Handles saving/loading bot state for persistence between restarts
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


class StateManager:
    """Manages bot state persistence"""
    
    def __init__(self, state_file: str = "bot_state.json"):
        self.state_file = Path(state_file)
        self.state = {}
    
    def save_state(self, state: Dict[str, Any]):
        """Save current bot state to file"""
        try:
            state['last_updated'] = datetime.now().isoformat()
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error saving state: {e}")
            return False
    
    def load_state(self) -> Optional[Dict[str, Any]]:
        """Load bot state from file"""
        try:
            if not self.state_file.exists():
                return None
            
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            return state
        except Exception as e:
            print(f"Error loading state: {e}")
            return None
    
    def clear_state(self):
        """Clear saved state"""
        try:
            if self.state_file.exists():
                self.state_file.unlink()
            return True
        except Exception as e:
            print(f"Error clearing state: {e}")
            return False
    
    def update_capital(self, current_capital: float):
        """Update capital in state"""
        state = self.load_state() or {}
        state['current_capital'] = current_capital
        state['last_updated'] = datetime.now().isoformat()
        return self.save_state(state)
    
    def get_capital(self, default: float = 2.0) -> float:
        """Get current capital from state"""
        state = self.load_state()
        if state and 'current_capital' in state:
            return state['current_capital']
        return default
    
    def save_metrics(self, metrics: Dict[str, Any]):
        """Save metrics to state"""
        state = self.load_state() or {}
        state['metrics'] = metrics
        return self.save_state(state)
    
    def get_metrics(self) -> Optional[Dict[str, Any]]:
        """Get metrics from state"""
        state = self.load_state()
        if state and 'metrics' in state:
            return state['metrics']
        return None

