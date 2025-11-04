#!/usr/bin/env python3
"""
Test if LaunchDetector can detect real tokens
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config import get_config
from src.logger import get_logger
from src.solana_client import SolanaClient, PumpFunClient
from src.detector import LaunchDetector, MockLaunchDetector

async def test_real_detector():
    """Test real LaunchDetector"""
    print("🔍 Testing Real LaunchDetector")
    print("=" * 60)
    
    config = get_config()
    logger = get_logger()
    
    # Initialize clients
    print("1️⃣  Initializing Solana client...")
    solana_client = SolanaClient(
        rpc_endpoint=config.get('solana.rpc_endpoint'),
        ws_endpoint=config.get('solana.ws_endpoint'),
        commitment=config.get('solana.commitment', 'confirmed')
    )
    
    connected = await solana_client.connect()
    if not connected:
        print("❌ Failed to connect to Solana RPC")
        return
    
    print("✅ Connected to Solana RPC")
    
    # Initialize Pump.fun client
    print("\n2️⃣  Initializing Pump.fun client...")
    pumpfun_client = PumpFunClient(solana_client)
    print("✅ Pump.fun client ready")
    
    # Test real detector
    print("\n3️⃣  Testing Real LaunchDetector...")
    try:
        detector = LaunchDetector(solana_client, pumpfun_client)
        
        detected_count = 0
        
        async def on_token(token_info):
            nonlocal detected_count
            detected_count += 1
            print(f"\n🎉 TOKEN DETECTED #{detected_count}")
            print(f"   Mint: {token_info.mint}")
            print(f"   Name: {token_info.name}")
            print(f"   Symbol: {token_info.symbol}")
            print(f"   Timestamp: {token_info.timestamp}")
        
        print("   Starting monitoring (will wait 30 seconds)...")
        
        # Start monitoring in background
        monitor_task = asyncio.create_task(
            detector.start_monitoring(on_token)
        )
        
        # Wait 30 seconds
        await asyncio.sleep(30)
        
        if detected_count == 0:
            print("\n❌ No tokens detected in 30 seconds")
            print("   This could mean:")
            print("   1. WebSocket is not connected properly")
            print("   2. No tokens launched in this period")
            print("   3. LaunchDetector implementation is incomplete")
        else:
            print(f"\n✅ Detected {detected_count} tokens!")
        
    except Exception as e:
        print(f"\n❌ Error with LaunchDetector: {e}")
        import traceback
        traceback.print_exc()

async def test_mock_detector():
    """Test MockLaunchDetector"""
    print("\n\n🧪 Testing MockLaunchDetector")
    print("=" * 60)
    
    config = get_config()
    
    solana_client = SolanaClient(
        rpc_endpoint=config.get('solana.rpc_endpoint'),
        ws_endpoint=config.get('solana.ws_endpoint'),
        commitment=config.get('solana.commitment', 'confirmed')
    )
    
    await solana_client.connect()
    pumpfun_client = PumpFunClient(solana_client)
    
    print("Testing Mock detector...")
    detector = MockLaunchDetector(solana_client, pumpfun_client)
    
    detected_count = 0
    
    async def on_token(token_info):
        nonlocal detected_count
        detected_count += 1
        print(f"\n🎉 MOCK TOKEN #{detected_count}")
        print(f"   Name: {token_info.name}")
        print(f"   Symbol: {token_info.symbol}")
    
    print("   Starting monitoring (will wait 15 seconds)...")
    
    # Start monitoring
    monitor_task = asyncio.create_task(
        detector.start_monitoring(on_token)
    )
    
    await asyncio.sleep(15)
    
    print(f"\n✅ Mock detector generated {detected_count} tokens")

async def main():
    print("🚀 Launch Detection Test Suite")
    print("=" * 60)
    print()
    
    # Test real detector
    await test_real_detector()
    
    # Test mock detector
    await test_mock_detector()
    
    print("\n" + "=" * 60)
    print("📊 Test Complete")

if __name__ == '__main__':
    asyncio.run(main())

