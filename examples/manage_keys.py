import json
import os
from typing import Dict, Any
from utils.utils import Log

def load_config() -> Dict[str, Any]:
    """Load existing configuration"""
    try:
        config_path = '../config/config.json'
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        Log(f"Failed to load config: {str(e)}")
        return {}

def save_config(config: Dict[str, Any]) -> bool:
    """Save configuration to file"""
    try:
        # Ensure config directory exists
        os.makedirs('../config', exist_ok=True)
        
        # Save config with pretty formatting
        with open('../config/config.json', 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        Log(f"Failed to save config: {str(e)}")
        return False

def add_exchange():
    """Add or update exchange API keys"""
    config = load_config()
    
    # Get exchange type
    Log("\nAvailable exchanges:")
    Log("1. OKX")
    Log("2. MEXC")
    Log("3. HTX")
    Log("4. CoinEx")
    Log("6. Gate.io")
    Log("7. Bitget")
    Log("8. Binance")
    
    try:
        choice = int(input("\nSelect exchange (1-8): "))
        if choice < 1 or choice > 8:
            Log("Invalid choice")
            return
            
        exchange_map = {
            1: "okx",
            2: "mexc",
            3: "htx",
            4: "coinex",
            6: "gateio",
            7: "bitget",
            8: "binance"
        }
        
        exchange_type = exchange_map[choice]
        
        # Get API credentials
        Log(f"\nEnter API credentials for {exchange_type.upper()}:")
        api_key = input("API Key: ").strip()
        api_secret = input("API Secret: ").strip()
        
        # Some exchanges require additional credentials
        passphrase = None
        if exchange_type in ["okx",  "bitget"]:
            passphrase = input("Passphrase: ").strip()
        
        # Create or update exchange config
        exchange_config = {
            "api_key": api_key,
            "api_secret": api_secret
        }
        if passphrase:
            exchange_config["passphrase"] = passphrase
            
        config[exchange_type] = exchange_config
        
        # Save updated config
        if save_config(config):
            Log(f"\nSuccessfully saved {exchange_type.upper()} credentials")
        else:
            Log(f"\nFailed to save {exchange_type.upper()} credentials")
            
    except ValueError:
        Log("Invalid input")
    except Exception as e:
        Log(f"Error: {str(e)}")

def remove_exchange():
    """Remove exchange API keys"""
    config = load_config()
    
    if not config:
        Log("No exchanges configured")
        return
        
    Log("\nConfigured exchanges:")
    exchanges = list(config.keys())
    for i, exchange in enumerate(exchanges, 1):
        Log(f"{i}. {exchange.upper()}")
        
    try:
        choice = int(input("\nSelect exchange to remove (1-{}): ".format(len(exchanges))))
        if choice < 1 or choice > len(exchanges):
            Log("Invalid choice")
            return
            
        exchange_type = exchanges[choice - 1]
        del config[exchange_type]
        
        if save_config(config):
            Log(f"\nSuccessfully removed {exchange_type.upper()} credentials")
        else:
            Log(f"\nFailed to remove {exchange_type.upper()} credentials")
            
    except ValueError:
        Log("Invalid input")
    except Exception as e:
        Log(f"Error: {str(e)}")

def list_exchanges():
    """List configured exchanges"""
    config = load_config()
    
    if not config:
        Log("No exchanges configured")
        return
        
    Log("\nConfigured exchanges:")
    Log("=" * 40)
    for exchange in config:
        Log(f"- {exchange.upper()}")
        Log(f"  API Key: {'*' * 8}{config[exchange]['api_key'][-4:]}")
        if 'passphrase' in config[exchange]:
            Log(f"  Passphrase: Required")
    Log("=" * 40)

def main():
    """Main function"""
    while True:
        Log("\nExchange API Key Management")
        Log("1. Add/Update Exchange")
        Log("2. Remove Exchange")
        Log("3. List Exchanges")
        Log("4. Exit")
        
        try:
            choice = input("\nSelect option (1-4): ").strip()
            
            if choice == "1":
                add_exchange()
            elif choice == "2":
                remove_exchange()
            elif choice == "3":
                list_exchanges()
            elif choice == "4":
                Log("Goodbye!")
                break
            else:
                Log("Invalid choice")
                
        except KeyboardInterrupt:
            Log("\nGoodbye!")
            break
        except Exception as e:
            Log(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 