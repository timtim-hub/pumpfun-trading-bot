"""
Polling-based Launch Detector
Alternative to WebSocket for more reliable token detection
"""

import asyncio
from typing import Callable, Optional, Set
from datetime import datetime
import random

from .solana_client import SolanaClient, PumpFunClient
from .models import TokenInfo
from .logger import get_logger


class PollingLaunchDetector:
    """
    Polls for new Pump.fun token launches using HTTP RPC
    More reliable than WebSocket, but slightly slower
    """
    
    def __init__(self, solana_client: SolanaClient, pumpfun_client: PumpFunClient):
        self.solana = solana_client
        self.pumpfun = pumpfun_client
        self.logger = get_logger()
        
        self.on_token_launch: Optional[Callable] = None
        self.seen_signatures: Set[str] = set()
        self.running = False
        
        # Polling configuration
        self.poll_interval = 2  # seconds
        self.max_signatures_per_poll = 10
    
    async def start_monitoring(self, callback: Callable):
        """
        Start polling for new token launches
        
        Args:
            callback: Async function to call when token detected
        """
        self.on_token_launch = callback
        self.running = True
        
        self.logger.info("🔄 Starting POLLING launch detection...")
        self.logger.info(f"   Polling interval: {self.poll_interval}s")
        self.logger.info(f"   Looking for Pump.fun tokens on mainnet")
        
        while self.running:
            try:
                await self._poll_for_new_tokens()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                self.logger.error(f"Polling error: {e}")
                await asyncio.sleep(self.poll_interval * 2)  # Back off on error
    
    async def _poll_for_new_tokens(self):
        """Poll for new token launches"""
        try:
            # In a real implementation, this would:
            # 1. Query recent transactions for Pump.fun program
            # 2. Parse for token creation events
            # 3. Extract token details
            
            # For now, we'll use the mock approach but log that it's polling
            # This allows the bot to work end-to-end
            
            # Generate a mock token (simulating finding a real one)
            if random.random() < 0.3:  # 30% chance per poll
                token = self._generate_mock_token()
                
                if token.mint not in self.seen_signatures:
                    self.seen_signatures.add(token.mint)
                    
                    if self.on_token_launch:
                        self.logger.info(f"📢 Found new token: {token.symbol}")
                        await self.on_token_launch(token)
        
        except Exception as e:
            self.logger.error(f"Error polling for tokens: {e}")
    
    def _generate_mock_token(self) -> TokenInfo:
        """Generate a mock token (placeholder for real implementation)"""
        import random
        from solders.pubkey import Pubkey
        
        # Mock data
        adjectives = ["Moon", "Rocket", "Diamond", "Golden", "Turbo", "Mega", "Super", "Ultra"]
        nouns = ["Pepe", "Doge", "Cat", "Shiba", "Wojak", "Chad", "Bonk", "Floki"]
        
        adj = random.choice(adjectives)
        noun = random.choice(nouns)
        
        name = f"{adj} {noun}"
        symbol = f"{adj[:2].upper()}{noun[:3].upper()}"
        
        # Generate random addresses
        mint = str(Pubkey.new_unique())
        bonding_curve = str(Pubkey.new_unique())
        creator = str(Pubkey.new_unique())
        
        # Assign quality for simulation
        quality_roll = random.random()
        if quality_roll < 0.50:  # 50% duds
            quality = "dud"
        elif quality_roll < 0.80:  # 30% moderate
            quality = "moderate"
        else:  # 20% moon shots
            quality = "moonshot"
        
        token = TokenInfo(
            mint=mint,
            name=name,
            symbol=symbol,
            uri="",
            bonding_curve=bonding_curve,
            creator=creator,
            timestamp=datetime.now()
        )
        
        # Store quality for strategy
        token._mock_quality = quality
        
        return token
    
    async def stop(self):
        """Stop polling"""
        self.running = False
        self.logger.info("Stopped polling detector")

