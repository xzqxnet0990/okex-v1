# 加密货币交易系统


本项目实现了一个统一的接口，用于与多个加密货币交易所进行交互。它提供了一致的API，用于跨不同交易所进行账户管理、市场数据检索和订单执行。

<h4 align="center">
<p>
<a href="https://github.com/xzqxnet0990/okex-v1/tree/main/README.md">简体中文</a> |
<a href="https://github.com/xzqxnet0990/okex-v1/tree/main/README_EN.md">English</a> 
</p>
</h4>

## 支持的交易所

- OKX (OKEx)
- MEXC
- HTX (火币)
- CoinEx
- KuCoin
- Gate.io
- Bitget
- 币安 (Binance)

## 功能特点

- 所有支持交易所的统一接口
- 账户余额检索
- 市场深度数据
- 订单管理（买入、卖出、取消）
- 订单状态跟踪
- 异步操作
- 错误处理和自动重试
- 日志系统
- 基于Web的可视化界面

## 项目结构

- `exchanges/`: 交易所集成模块
- `strategy/`: 交易策略实现
- `utils/`: 实用工具和辅助函数
- `models/`: 数据模型
- `config/`: 配置文件
- `examples/`: 示例脚本
- `web-vue/`: 前端Web应用（Vue.js）

## 策略描述
本策略为现货套利策略，通过检测不同交易所之间的价格差异，实现低买高卖的套利交易。原理上检测的币种、交易所越多，机会就越多。
策略的核心逻辑如下：

- 套利：在两个交易所之间进行套利交易，即在一个交易所买入某种资产，然后在另一个交易所卖出同一种资产，从而获得利润。
- 对冲操作：分为正向、反向两种模式，由于挂单可能存在未成交交易，记录未成交交易，将未成交部分进行对冲。
- 挂单套利：分为正向、反向两种模式，1）在A交易所卖出同时在B交易所买入。2）在A交易所买入同时在B交易所卖出。获取期盼中的利润。
- 均衡操作：由于长时间交易后各个交易所仓位存在不平衡问题，需要找到机会调整。

## 配置

创建一个包含交易所API凭证的`config/config.json`文件：

```json
{
  "okx": {
    "api_key": "你的API密钥",
    "api_secret": "你的API密钥",
    "passphrase": "你的密码短语"
  },
  "binance": {
    "api_key": "你的API密钥",
    "api_secret": "你的API密钥"
  }
  // 根据需要添加其他交易所
}
```

## 运行应用程序

### 后端

运行后端模拟：

```bash
python examples/simulate_okex_strategy.py
```

这将在http://localhost:8083启动后端服务器，在ws://localhost:8083/ws启动WebSocket服务器。

### 前端

前端位于`web-vue`目录中。运行开发服务器：

```bash
cd web-vue
npm install
npm run serve
```

### 全栈

同时运行前端和后端：

```bash
npm run build --prefix web-vue && python examples/simulate_okex_strategy.py
```

或使用wrangler.toml中定义的自定义脚本：

```bash
# 运行前端开发服务器
npm run frontend_dev

# 构建前端
npm run frontend_build

# 运行后端
npm run backend_run

# 运行全栈
npm run fullstack
```

## 使用示例

```python
from exchanges import ExchangeFactory

# 初始化交易所
config = load_config()
exchange = ExchangeFactory.create_exchange("okx", config["okx"])

# 获取账户信息
account = await exchange.GetAccount()
Log(f"余额: {account.Balance} USDT")
Log(f"持仓: {account.Stocks} BTC")

# 获取市场深度
depth = await exchange.GetDepth("BTC")
Log(f"最佳卖价: {depth.Asks[0]}")
Log(f"最佳买价: {depth.Bids[0]}")

# 下单
buy_order = await exchange.Buy("BTC", price=50000, amount=0.01)
sell_order = await exchange.Sell("BTC", price=51000, amount=0.01)

# 取消订单
cancelled = await exchange.CancelOrder("BTC", order_id="123")

# 关闭连接
await ExchangeFactory.close_all()
```

## 依赖项

- Python 3.7+
- ccxt
- aiohttp
- typing_extensions
- Vue.js (前端)

## 安装

1. 克隆仓库
2. 安装后端依赖: `pip install -r requirements.txt`
3. 安装前端依赖: `cd web-vue && npm install`
4. 创建并配置 `config/config.json`
5. 使用上述方法之一运行应用程序

## 许可证

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