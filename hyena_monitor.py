import asyncio
import json
import os
from datetime import datetime
from web3 import Web3
import requests
from dotenv import load_dotenv

load_dotenv()

CONFIG = {
    'RPC_URL': os.getenv('RPC_URL', 'https://rpc.hyperliquid.xyz/evm'),
    'VAULT_MANAGER_ADDRESS': '0x7E698EEa0709e4a0Dbbd790fC493D60691801157',
    'TOKEN_ADDRESS': '0x54a98ff45a7dbdf30c54e32fd330d3ea582a5559',
    'CHECK_INTERVAL': 60,
    'WEBHOOK_URL': None
}

VAULT_ABI = [
    {
        "inputs": [],
        "name": "maxDepositAmount",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "maxWithdrawalAmount",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "maxTokenSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "totalAssets",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]


class VaultCapMonitor:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(CONFIG['RPC_URL']))

        if not self.w3.is_connected():
            raise Exception("❌ Unable to connect to HyperEVM RPC")

        self.vault = self.w3.eth.contract(
            address=Web3.to_checksum_address(CONFIG['VAULT_MANAGER_ADDRESS']),
            abi=VAULT_ABI
        )
        self.previous_cap = None

        print("✅ Connected to HyperEVM network")

    def get_current_cap(self):
        try:
            max_deposit = self.vault.functions.maxDepositAmount().call()
            return self.w3.from_wei(max_deposit, 'ether')
        except Exception as e:
            print(f"⚠️  Error fetching cap: {e}")
            raise Exception(f"❌ Unable to retrieve vault cap")

    def get_max_token_supply(self):
        try:
            max_supply = self.vault.functions.maxTokenSupply().call()
            return self.w3.from_wei(max_supply, 'ether')
        except Exception:
            return 'N/A'

    def get_total_assets(self):
        try:
            total = self.vault.functions.totalAssets().call()
            return self.w3.from_wei(total, 'ether')
        except Exception:
            return 'N/A'

    def send_webhook_notification(self, data):
        if not CONFIG['WEBHOOK_URL']:
            return

        try:
            message = (
                f"🚨 Hyena Vault Cap Changed!\n"
                f"Old: {data['old_cap']:.2f} USDe\n"
                f"New: {data['new_cap']:.2f} USDe\n"
                f"Change: {'+' if data['change'] > 0 else ''}{data['change']:.2f} ({data['change_percent']:.2f}%)\n"
                f"Total Assets: {data['total_assets']} USDe\n"
                f"Max Supply: {data['max_supply']} HLPe\n"
                f"Time: {data['timestamp']}"
            )

            response = requests.post(
                CONFIG['WEBHOOK_URL'],
                json={'text': message},
                timeout=10
            )

            if response.ok:
                print("  ✅ Notification sent successfully")
            else:
                print(f"  ❌ Notification error: {response.status_code}")

        except Exception as e:
            print(f"  ❌ Error sending notification: {e}")

    def check_cap_change(self):
        try:
            current_cap = self.get_current_cap()
            total_assets = self.get_total_assets()
            max_supply = self.get_max_token_supply()

            timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

            print(f"\n[{timestamp}] Checking vault...")
            print(f"  Max deposit cap: {current_cap} USDe")
            print(f"  Total assets: {total_assets} USDe")
            print(f"  Max token supply: {max_supply} HLPe")

            if self.previous_cap is None:
                print(f"  📊 Initial cap detected: {current_cap} USDe")
                self.previous_cap = float(current_cap)
            elif float(current_cap) != self.previous_cap:
                change = float(current_cap) - self.previous_cap
                change_percent = (change / self.previous_cap * 100)

                print(f"\n{'='*60}")
                print(f"🚨 CAP CHANGE DETECTED! 🚨")
                print(f"{'='*60}")
                print(f"  Old cap: {self.previous_cap} USDe")
                print(f"  New cap: {current_cap} USDe")
                print(f"  Change: {'+' if change > 0 else ''}{change:.4f} USDe ({change_percent:.2f}%)")
                print(f"  Current total assets: {total_assets} USDe")
                print(f"  Timestamp: {timestamp}")
                print(f"{'='*60}\n")

                self.send_webhook_notification({
                    'old_cap': self.previous_cap,
                    'new_cap': float(current_cap),
                    'change': change,
                    'change_percent': change_percent,
                    'timestamp': timestamp,
                    'total_assets': total_assets,
                    'max_supply': max_supply
                })

                self.previous_cap = float(current_cap)

        except Exception as e:
            print(f"[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] ❌ Error: {e}")

    async def start(self):
        print("\n" + "="*60)
        print("🔍 Hyena Vault Cap Monitor started")
        print("="*60)
        print(f"📍 Vault Manager: {CONFIG['VAULT_MANAGER_ADDRESS']}")
        print(f"🔗 RPC: {CONFIG['RPC_URL']}")
        print(f"⏱️  Check interval: {CONFIG['CHECK_INTERVAL']}s")
        print("="*60)

        self.check_cap_change()

        while True:
            await asyncio.sleep(CONFIG['CHECK_INTERVAL'])
            self.check_cap_change()


async def main():
    try:
        monitor = VaultCapMonitor()
        await monitor.start()
    except KeyboardInterrupt:
        print("\n\n👋 Stopping monitoring...")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")


if __name__ == "__main__":
    asyncio.run(main())