"""
Solana Blockchain Integration
Handles RPC calls, WebSocket subscriptions, and transaction building
"""

import asyncio
import json
import base58
import base64
from typing import Optional, Dict, Any, Callable, List
from pathlib import Path
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed, Finalized
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import Transaction
from solders.system_program import transfer, TransferParams
from solders.compute_budget import set_compute_unit_price
from solders.instruction import Instruction, AccountMeta
from spl.token.async_client import AsyncToken
from spl.token.constants import TOKEN_PROGRAM_ID
import websockets

from .logger import get_logger


class SolanaClient:
    """Async Solana client for blockchain interactions"""
    
    def __init__(self, rpc_endpoint: str, ws_endpoint: str, 
                 commitment: str = "confirmed"):
        """
        Initialize Solana client
        
        Args:
            rpc_endpoint: Solana RPC HTTP endpoint
            ws_endpoint: Solana WebSocket endpoint
            commitment: Transaction commitment level
        """
        self.rpc_endpoint = rpc_endpoint
        self.ws_endpoint = ws_endpoint
        self.commitment = commitment
        self.client: Optional[AsyncClient] = None
        self.ws_connection: Optional[websockets.WebSocketClientProtocol] = None
        self.logger = get_logger()
        
        # Pump.fun program ID
        self.pumpfun_program_id = Pubkey.from_string(
            "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
        )
    
    async def connect(self):
        """Establish connection to Solana RPC"""
        try:
            self.client = AsyncClient(self.rpc_endpoint)
            
            # Test connection by getting slot
            response = await self.client.get_slot()
            if response:
                self.logger.info(f"✓ Connected to Solana RPC: {self.rpc_endpoint}")
                return True
            else:
                self.logger.error("Failed to connect to Solana RPC")
                return False
        except Exception as e:
            self.logger.error(f"Failed to connect to Solana RPC: {e}")
            return False
    
    async def disconnect(self):
        """Close Solana connections"""
        if self.client:
            await self.client.close()
            self.logger.info("Disconnected from Solana RPC")
        
        if self.ws_connection:
            await self.ws_connection.close()
            self.logger.info("Closed WebSocket connection")
    
    async def get_balance(self, pubkey: Pubkey) -> float:
        """
        Get SOL balance for a wallet
        
        Args:
            pubkey: Wallet public key
        
        Returns:
            Balance in SOL
        """
        try:
            response = await self.client.get_balance(pubkey)
            if response.value is not None:
                return response.value / 1e9  # Convert lamports to SOL
            return 0.0
        except Exception as e:
            self.logger.error(f"Error getting balance: {e}")
            return 0.0
    
    async def get_token_balance(self, token_account: Pubkey) -> float:
        """
        Get SPL token balance
        
        Args:
            token_account: Token account public key
        
        Returns:
            Token balance
        """
        try:
            response = await self.client.get_token_account_balance(token_account)
            if response.value:
                return float(response.value.amount) / (10 ** response.value.decimals)
            return 0.0
        except Exception as e:
            self.logger.error(f"Error getting token balance: {e}")
            return 0.0
    
    async def get_account_info(self, pubkey: Pubkey) -> Optional[Dict[str, Any]]:
        """
        Get account information
        
        Args:
            pubkey: Account public key
        
        Returns:
            Account data or None
        """
        try:
            response = await self.client.get_account_info(pubkey)
            if response.value:
                return {
                    'lamports': response.value.lamports,
                    'owner': str(response.value.owner),
                    'data': response.value.data,
                    'executable': response.value.executable,
                    'rent_epoch': response.value.rent_epoch
                }
            return None
        except Exception as e:
            self.logger.error(f"Error getting account info: {e}")
            return None
    
    async def get_recent_blockhash(self) -> Optional[str]:
        """
        Get recent blockhash for transactions
        
        Returns:
            Recent blockhash string or None
        """
        try:
            response = await self.client.get_latest_blockhash()
            if response.value:
                return str(response.value.blockhash)
            return None
        except Exception as e:
            self.logger.error(f"Error getting blockhash: {e}")
            return None
    
    async def send_transaction(self, transaction: Transaction, 
                               keypair: Keypair,
                               skip_preflight: bool = False) -> Optional[str]:
        """
        Send a transaction to Solana
        
        Args:
            transaction: Transaction to send
            keypair: Keypair to sign with
            skip_preflight: Skip preflight checks for speed
        
        Returns:
            Transaction signature or None
        """
        try:
            # Send transaction
            response = await self.client.send_transaction(
                transaction,
                keypair,
                opts={'skip_preflight': skip_preflight}
            )
            
            if response.value:
                signature = str(response.value)
                self.logger.debug(f"Transaction sent: {signature}")
                return signature
            
            return None
        except Exception as e:
            self.logger.error(f"Error sending transaction: {e}")
            return None
    
    async def confirm_transaction(self, signature: str, 
                                  timeout: int = 30) -> bool:
        """
        Wait for transaction confirmation
        
        Args:
            signature: Transaction signature
            timeout: Timeout in seconds
        
        Returns:
            True if confirmed, False otherwise
        """
        try:
            start_time = asyncio.get_event_loop().time()
            
            while True:
                # Check if timed out
                if asyncio.get_event_loop().time() - start_time > timeout:
                    self.logger.warning(f"Transaction confirmation timeout: {signature}")
                    return False
                
                # Check transaction status
                response = await self.client.get_signature_statuses([signature])
                
                if response.value and response.value[0]:
                    status = response.value[0]
                    if status.confirmation_status:
                        self.logger.debug(f"Transaction confirmed: {signature}")
                        return True
                
                await asyncio.sleep(1)
        
        except Exception as e:
            self.logger.error(f"Error confirming transaction: {e}")
            return False
    
    async def subscribe_to_logs(self, callback: Callable, 
                               program_id: Optional[Pubkey] = None):
        """
        Subscribe to program logs via WebSocket
        
        Args:
            callback: Async function to call with log data
            program_id: Optional program ID to filter (uses Pump.fun by default)
        """
        if program_id is None:
            program_id = self.pumpfun_program_id
        
        try:
            self.logger.info(f"Subscribing to logs for program: {program_id}")
            
            async with websockets.connect(self.ws_endpoint) as websocket:
                self.ws_connection = websocket
                
                # Subscribe to logs
                subscribe_message = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "logsSubscribe",
                    "params": [
                        {
                            "mentions": [str(program_id)]
                        },
                        {
                            "commitment": self.commitment
                        }
                    ]
                }
                
                await websocket.send(json.dumps(subscribe_message))
                self.logger.info("✓ WebSocket subscription active")
                
                # Listen for messages
                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        
                        # Call callback with log data
                        if 'params' in data:
                            await callback(data['params'])
                    
                    except websockets.exceptions.ConnectionClosed:
                        self.logger.warning("WebSocket connection closed, reconnecting...")
                        await asyncio.sleep(5)
                        # Recursively reconnect
                        await self.subscribe_to_logs(callback, program_id)
                        break
                    
                    except Exception as e:
                        self.logger.error(f"Error processing WebSocket message: {e}")
        
        except Exception as e:
            self.logger.error(f"WebSocket subscription error: {e}")
    
    def load_keypair(self, keypair_path: str) -> Optional[Keypair]:
        """
        Load keypair from JSON file
        
        Args:
            keypair_path: Path to keypair JSON file
        
        Returns:
            Keypair or None
        """
        try:
            path = Path(keypair_path)
            if not path.exists():
                self.logger.error(f"Keypair file not found: {keypair_path}")
                return None
            
            with open(path, 'r') as f:
                secret_key = json.load(f)
            
            # Convert to bytes if needed
            if isinstance(secret_key, list):
                secret_key = bytes(secret_key)
            
            keypair = Keypair.from_bytes(secret_key)
            self.logger.info(f"✓ Loaded keypair: {keypair.pubkey()}")
            
            return keypair
        
        except Exception as e:
            self.logger.error(f"Error loading keypair: {e}")
            return None
    
    def create_keypair(self, save_path: Optional[str] = None) -> Keypair:
        """
        Create a new keypair
        
        Args:
            save_path: Optional path to save keypair JSON
        
        Returns:
            New keypair
        """
        keypair = Keypair()
        
        if save_path:
            path = Path(save_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w') as f:
                json.dump(list(bytes(keypair)), f)
            
            self.logger.info(f"Keypair saved to: {save_path}")
        
        self.logger.info(f"Created new keypair: {keypair.pubkey()}")
        return keypair


class PumpFunClient:
    """Client for interacting with Pump.fun smart contracts"""
    
    def __init__(self, solana_client: SolanaClient):
        """
        Initialize Pump.fun client
        
        Args:
            solana_client: Solana client instance
        """
        self.solana = solana_client
        self.logger = get_logger()
        
        # Pump.fun program ID
        self.program_id = solana_client.pumpfun_program_id
        
        # Instruction discriminators (8-byte identifiers for Anchor instructions)
        # These would normally come from the IDL, but we hardcode for speed
        self.DISCRIMINATORS = {
            'create': bytes.fromhex('181ec828051c0777'),  # Create token
            'buy': bytes.fromhex('66063d1201daebea'),      # Buy tokens
            'sell': bytes.fromhex('33e685a4017f83ad')      # Sell tokens
        }
    
    async def get_bonding_curve_data(self, bonding_curve: Pubkey) -> Optional[Dict[str, Any]]:
        """
        Get bonding curve account data
        
        Args:
            bonding_curve: Bonding curve public key
        
        Returns:
            Parsed bonding curve data or None
        """
        try:
            account_info = await self.solana.get_account_info(bonding_curve)
            
            if not account_info or not account_info['data']:
                return None
            
            # Decode account data
            # Note: This is a simplified version. Full implementation would
            # use the Anchor IDL to properly decode the struct.
            data = account_info['data']
            
            # For now, return raw data
            # In production, decode based on Pump.fun's account structure
            return {
                'raw_data': data,
                'owner': account_info['owner'],
                'lamports': account_info['lamports']
            }
        
        except Exception as e:
            self.logger.error(f"Error getting bonding curve data: {e}")
            return None
    
    async def estimate_price(self, bonding_curve: Pubkey, sol_amount: float) -> Optional[float]:
        """
        Estimate token price for a given SOL amount
        
        Args:
            bonding_curve: Bonding curve public key
            sol_amount: Amount of SOL to spend
        
        Returns:
            Estimated tokens received or None
        """
        # This would use the bonding curve formula
        # For now, return a placeholder
        # In production, calculate based on current curve state
        
        try:
            curve_data = await self.get_bonding_curve_data(bonding_curve)
            if not curve_data:
                return None
            
            # Simplified estimation (would use actual curve math)
            # Price increases as curve fills
            estimated_tokens = sol_amount * 1000000  # Placeholder
            
            return estimated_tokens
        
        except Exception as e:
            self.logger.error(f"Error estimating price: {e}")
            return None
    
    async def create_buy_instruction(self, 
                                    payer: Pubkey,
                                    mint: Pubkey,
                                    bonding_curve: Pubkey,
                                    associated_bonding_curve: Pubkey,
                                    associated_user: Pubkey,
                                    amount_sol: int,
                                    max_sol_cost: int) -> Instruction:
        """
        Create a buy instruction for Pump.fun
        
        Args:
            payer: User's public key
            mint: Token mint
            bonding_curve: Bonding curve account
            associated_bonding_curve: Associated token account for bonding curve
            associated_user: User's associated token account
            amount_sol: Amount of SOL to spend (in lamports)
            max_sol_cost: Max SOL willing to pay (slippage protection)
        
        Returns:
            Buy instruction
        """
        # Account metas for buy instruction
        # Note: This is simplified. Full implementation would include all
        # required accounts from the Pump.fun IDL
        keys = [
            AccountMeta(pubkey=payer, is_signer=True, is_writable=True),
            AccountMeta(pubkey=mint, is_signer=False, is_writable=False),
            AccountMeta(pubkey=bonding_curve, is_signer=False, is_writable=True),
            AccountMeta(pubkey=associated_bonding_curve, is_signer=False, is_writable=True),
            AccountMeta(pubkey=associated_user, is_signer=False, is_writable=True),
            # Add system program, token program, etc.
        ]
        
        # Instruction data: discriminator + amount + max_sol_cost
        data = self.DISCRIMINATORS['buy'] + amount_sol.to_bytes(8, 'little') + max_sol_cost.to_bytes(8, 'little')
        
        return Instruction(
            program_id=self.program_id,
            accounts=keys,
            data=data
        )
    
    async def create_sell_instruction(self,
                                     payer: Pubkey,
                                     mint: Pubkey,
                                     bonding_curve: Pubkey,
                                     associated_bonding_curve: Pubkey,
                                     associated_user: Pubkey,
                                     amount_tokens: int,
                                     min_sol_output: int) -> Instruction:
        """
        Create a sell instruction for Pump.fun
        
        Args:
            payer: User's public key
            mint: Token mint
            bonding_curve: Bonding curve account
            associated_bonding_curve: Associated token account for bonding curve
            associated_user: User's associated token account
            amount_tokens: Amount of tokens to sell
            min_sol_output: Minimum SOL to receive (slippage protection)
        
        Returns:
            Sell instruction
        """
        # Similar to buy, but for selling
        keys = [
            AccountMeta(pubkey=payer, is_signer=True, is_writable=True),
            AccountMeta(pubkey=mint, is_signer=False, is_writable=False),
            AccountMeta(pubkey=bonding_curve, is_signer=False, is_writable=True),
            AccountMeta(pubkey=associated_bonding_curve, is_signer=False, is_writable=True),
            AccountMeta(pubkey=associated_user, is_signer=False, is_writable=True),
        ]
        
        data = self.DISCRIMINATORS['sell'] + amount_tokens.to_bytes(8, 'little') + min_sol_output.to_bytes(8, 'little')
        
        return Instruction(
            program_id=self.program_id,
            accounts=keys,
            data=data
        )


# Helper function to derive associated token address
def get_associated_token_address(owner: Pubkey, mint: Pubkey) -> Pubkey:
    """
    Derive associated token account address
    
    Args:
        owner: Owner's public key
        mint: Token mint
    
    Returns:
        Associated token account public key
    """
    # This is a simplified version
    # In production, use spl.token.client.Token.get_associated_token_address()
    from spl.token.instructions import get_associated_token_address as get_ata
    return get_ata(owner, mint)

