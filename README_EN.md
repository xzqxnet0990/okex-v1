# Cryptocurrency Exchange Integration

This project implements a unified interface for interacting with multiple cryptocurrency exchanges. It provides a consistent API for account management, market data retrieval, and order execution across different exchanges.
<h4 align="center">
    <p>
<a href="https://github.com/xzqxnet0990/okex-v1/tree/main/README.md">简体中文</a> |
<a href="https://github.com/xzqxnet0990/okex-v1/tree/main/README_EN.md">English</a> 
    </p>
</h4>

## Supported Exchanges

- OKX (OKEx)
- MEXC
- HTX (Huobi)
- CoinEx
- KuCoin
- Gate.io
- Bitget
- Binance

## Features

- Unified interface for all supported exchanges
- Account balance retrieval
- Market depth data
- Order management (buy, sell, cancel)
- Order status tracking
- Asynchronous operations
- Error handling and automatic retries
- Logging system
- Web-based visualization interface

## Project Structure

- `exchanges/`: Exchange integration modules
- `strategy/`: Trading strategy implementations
- `utils/`: Utility functions and helpers
- `models/`: Data models
- `config/`: Configuration files
- `examples/`: Example scripts
- `web-vue/`: Frontend web application (Vue.js)

## Strategy Description
This strategy is a spot arbitrage strategy that aims to capitalize on price discrepancies between different exchanges, enabling low-risk profit opportunities through buying low and selling high. Theoretically, the more currencies and exchanges monitored, the greater the potential for arbitrage opportunities.

The core logic of the strategy is as follows:

- Arbitrage: Execute arbitrage trades between two exchanges by purchasing an asset on one exchange and simultaneously selling the same asset on another exchange to capture profits from price differences.

- Hedging Operations: Divided into two modes—forward and reverse. Due to the possibility of unfilled orders, the strategy records unexecuted trades and hedges the remaining portion to mitigate risk.

- Order Book Arbitrage: Also divided into two modes—forward and reverse, Sell on Exchange A while simultaneously buying on Exchange B. Buy on Exchange A while simultaneously selling on Exchange B.
The goal is to achieve the anticipated profit from these operations.

- Rebalancing Operations: Over time, positions across exchanges may become imbalanced due to prolonged trading. The strategy identifies opportunities to rebalance these positions to maintain equilibrium.

## Configuration

Create a `config/config.json` file with your exchange API credentials:

```json
{
    "okx": {
        "api_key": "your_api_key",
        "api_secret": "your_api_secret",
        "passphrase": "your_passphrase"
    },
    "binance": {
        "api_key": "your_api_key",
        "api_secret": "your_api_secret"
    }
    // Add other exchanges as needed
}
```

## Running the Application

### Backend

To run the backend simulation:

```bash
python examples/simulate_okex_strategy.py
```

This will start the backend server on http://localhost:8083 and WebSocket server on ws://localhost:8083/ws.

### Frontend

The frontend is located in the `web-vue` directory. To run the development server:

```bash
cd web-vue
npm install
npm run serve
```

### Full Stack

To run both frontend and backend together:

```bash
npm run build --prefix web-vue && python examples/simulate_okex_strategy.py
```

Or use the custom scripts defined in wrangler.toml:

```bash
# Run frontend development server
npm run frontend_dev

# Build frontend
npm run frontend_build

# Run backend
npm run backend_run

# Run full stack
npm run fullstack
```

## Usage

```python
from exchanges import ExchangeFactory

# Initialize exchanges
config = load_config()
exchange = ExchangeFactory.create_exchange("okx", config["okx"])

# Get account information
account = await exchange.GetAccount()
Log(f"Balance: {account.Balance} USDT")
Log(f"Stocks: {account.Stocks} BTC")

# Get market depth
depth = await exchange.GetDepth("BTC")
Log(f"Best ask: {depth.Asks[0]}")
Log(f"Best bid: {depth.Bids[0]}")

# Place orders
buy_order = await exchange.Buy("BTC", price=50000, amount=0.01)
sell_order = await exchange.Sell("BTC", price=51000, amount=0.01)

# Cancel order
cancelled = await exchange.CancelOrder("BTC", order_id="123")

# Close connections
await ExchangeFactory.close_all()
```

## Dependencies

- Python 3.7+
- ccxt
- aiohttp
- typing_extensions
- Vue.js (for frontend)

## Installation

1. Clone the repository
2. Install backend dependencies: `pip install -r requirements.txt`
3. Install frontend dependencies: `cd web-vue && npm install`
4. Create and configure `config/config.json`
5. Run the application using one of the methods described above

## License

Apache License 2.0

Copyright 2025 The OKEx-V1 Authors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.