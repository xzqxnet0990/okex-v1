import asyncio
import json
from aiohttp import web
import aiohttp_cors
from datetime import datetime
import os
from pathlib import Path
from utils.logger import Log

class WebServer:
    def __init__(self):
        self.app = web.Application()
        self.setup_routes()
        self.websockets = set()
        self.running = False

    def setup_routes(self):
        # 获取web目录的绝对路径
        web_dir = Path(__file__).parent / 'web'
        
        # 设置 CORS
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*"
            )
        })

        # 添加路由
        cors.add(self.app.router.add_get('/', self.handle_index))
        cors.add(self.app.router.add_get('/ws', self.handle_websocket))

        # 添加静态文件服务
        # self.app.router.add_static('/js', web_dir / 'js')
        #  self.app.router.add_static('/css', web_dir / 'css')
        
        # 添加Vue.js构建的静态文件
        web_vue_dist = Path(__file__).parent / 'web-vue' / 'dist'
        if web_vue_dist.exists():
            self.app.router.add_static('/', web_vue_dist)
            print(f"Serving Vue.js static files from {web_vue_dist}")
        
    async def handle_index(self, request):
        """处理主页请求"""
        # 首先尝试从Vue.js构建目录获取index.html
        web_vue_dist = Path(__file__).parent / 'web-vue' / 'dist'
        if web_vue_dist.exists() and (web_vue_dist / 'index.html').exists():
            return web.FileResponse(web_vue_dist / 'index.html')
        
        # 如果Vue.js构建目录不存在，则尝试从web目录获取
        web_dir = Path(__file__).parent / 'web'
        if web_dir.exists() and (web_dir / 'index.html').exists():
            return web.FileResponse(web_dir / 'index.html')
        
        # 如果都不存在，则返回一个简单的HTML页面
        return web.Response(
            text="<html><body><h1>API服务器正在运行</h1><p>前端文件未找到，请先构建前端。</p></body></html>",
            content_type="text/html"
        )
        
    async def handle_websocket(self, request):
        """处理 WebSocket 连接"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        print("New WebSocket connection established")
        self.websockets.add(ws)
        
        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        print(f"Received WebSocket message: {data}")
                        
                        if 'action' in data:
                            if data['action'] == 'fetch_balances':
                                print("Received fetch_balances request")
                                # This will be handled by the update_balance_loop
                                # Just log that we received the request
                                await ws.send_str(json.dumps({"log": "Received fetch_balances request, processing..."}))
                            elif data['action'] == 'close':
                                await ws.close()
                    except json.JSONDecodeError:
                        print(f"Invalid JSON received: {msg.data}")
                elif msg.type == web.WSMsgType.ERROR:
                    print(f'WebSocket connection closed with exception {ws.exception()}')
        finally:
            self.websockets.remove(ws)
            print("WebSocket connection closed")
        
        return ws
        
    async def broadcast(self, data):
        """广播数据到所有连接的客户端"""
        if not self.websockets:
            return
            
        try:
            # 如果是日志消息，直接发送
            if isinstance(data, dict) and 'log' in data and len(data) == 1:
                message = data
            else:
                # 检查recent_trades数据
                if 'recent_trades' in data and data['recent_trades']:
                    print(f"Broadcasting {len(data['recent_trades'])} recent trades")
                    # 检查第一条和最后一条交易记录
                    print(f"First trade: {data['recent_trades'][0]}")
                    print(f"Last trade: {data['recent_trades'][-1]}")
                    # 检查是否每条交易记录都有time字段
                    missing_time = [i for i, trade in enumerate(data['recent_trades']) if 'time' not in trade]
                    if missing_time:
                        print(f"Warning: {len(missing_time)} trades missing 'time' field at indices: {missing_time[:5]}...")
                        # 为缺少time字段的交易记录添加时间戳
                        for i in missing_time:
                            data['recent_trades'][i]['time'] = datetime.now().isoformat()
                else:
                    print("No recent trades data to broadcast")
                
                # 确保数据格式的一致性
                message = {
                    'initial_balance': data.get('initial_balance', 0),
                    'current_balance': data.get('current_balance', 0),
                    'total_asset_value': data.get('total_asset_value', 0),
                    'total_profit': data.get('total_profit', 0),
                    'profit_rate': data.get('profit_rate', 0),
                    'unhedged_value': data.get('unhedged_value', 0),
                    'short_position_value': data.get('short_position_value', 0),
                    'total_fees': data.get('total_fees', 0),
                    'frozen_assets': data.get('frozen_assets', 0),
                    'total_trades': data.get('total_trades', 0),
                    'success_trades': data.get('success_trades', 0),
                    'failed_trades': data.get('failed_trades', 0),
                    'win_rate': data.get('win_rate', 0),
                    'trade_types': data.get('trade_types', {}),
                    'unhedged_positions': data.get('unhedged_positions', []),
                    'futures_short_positions': data.get('futures_short_positions', []),
                    'recent_trades': data.get('recent_trades', []),
                    'depths': data.get('depths', {}),
                    'fees': data.get('fees', {}),
                    'balances': data.get('balances', {}),
                    'frozen_balances': data.get('frozen_balances', {}),
                    'pending_orders': data.get('pending_orders', []),
                    'timestamp': data.get('timestamp', datetime.now().isoformat())
                }
            
            # 转换为JSON字符串
            data_str = json.dumps(message)
            
            # 发送到所有连接的客户端
            closed_ws = set()
            for ws in self.websockets:
                try:
                    await ws.send_str(data_str)
                except Exception as e:
                    print(f"Error sending data to websocket: {e}")
                    closed_ws.add(ws)
            
            # 移除已关闭的连接
            self.websockets -= closed_ws
            
        except Exception as e:
            print(f"Error in broadcast: {e}")
            import traceback
            print(traceback.format_exc())

    async def update_balance_loop(self, config):
        """定期更新并广播余额信息"""
        self.running = True
        while self.running:
            try:
                balances = {}
                frozen_balances = {}
                depths = {}
                btc_price = 0
                
                # 获取各交易所余额
                for exchange_type, exchange_config in config.items():
                    if exchange_type == 'strategy' or exchange_type == 'assets' or exchange_type == 'supported_exchanges':
                        continue  # Skip non-exchange config sections
                        
                    try:
                        print(f"Fetching balance for exchange: {exchange_type}")
                        # Import ExchangeFactory here to avoid circular import
                        from exchanges import ExchangeFactory
                        exchange = ExchangeFactory.create_exchange(exchange_type, exchange_config)
                        if exchange:
                            # 获取账户信息
                            account = await exchange.GetAccount()
                            
                            # Initialize balance dictionaries for this exchange
                            balances[exchange_type] = {}
                            frozen_balances[exchange_type] = {}
                            
                            # Add USDT balances
                            balances[exchange_type]['usdt'] = account.Balance if hasattr(account, 'Balance') else 0
                            frozen_balances[exchange_type]['usdt'] = account.FrozenBalance if hasattr(account, 'FrozenBalance') else 0
                            
                            # Add coin balances for all supported coins
                            for coin in config.get('strategy', {}).get('COINS', []):
                                coin_lower = coin.lower()
                                if hasattr(account, 'Stocks') and isinstance(account.Stocks, dict) and coin_lower in account.Stocks:
                                    balances[exchange_type][coin_lower] = account.Stocks[coin_lower]
                                else:
                                    balances[exchange_type][coin_lower] = 0
                                    
                                if hasattr(account, 'FrozenStocks') and isinstance(account.FrozenStocks, dict) and coin_lower in account.FrozenStocks:
                                    frozen_balances[exchange_type][coin_lower] = account.FrozenStocks[coin_lower]
                                else:
                                    frozen_balances[exchange_type][coin_lower] = 0
                            
                            # 获取深度数据
                            for coin in config.get('strategy', {}).get('COINS', []):
                                try:
                                    if coin not in depths:
                                        depths[coin] = {}
                                        
                                    depth = await exchange.GetDepth(coin)
                                    if depth:
                                        depths[coin][exchange_type] = {
                                            'asks': depth.Asks if hasattr(depth, 'Asks') else [],
                                            'bids': depth.Bids if hasattr(depth, 'Bids') else []
                                        }
                                        
                                        # 获取BTC价格
                                        if coin.upper() == 'BTC' and not btc_price and hasattr(depth, 'Asks') and hasattr(depth, 'Bids') and depth.Asks and depth.Bids:
                                            btc_price = (depth.Asks[0][0] + depth.Bids[0][0]) / 2
                                except Exception as e:
                                    print(f"Error getting depth for {coin} from {exchange_type}: {str(e)}")
                            
                            await exchange.close()
                            
                    except Exception as e:
                        print(f"Error getting {exchange_type} balance: {str(e)}")
                        import traceback
                        print(traceback.format_exc())
                
                # 打印调试信息
                print(f"Balances: {balances}")
                print(f"Frozen balances: {frozen_balances}")
                
                # 广播数据
                await self.broadcast({
                    'balances': balances,
                    'frozen_balances': frozen_balances,
                    'depths': depths,
                    'btcPrice': btc_price,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                print(f"Error in balance update loop: {str(e)}")
                import traceback
                print(traceback.format_exc())
            
            await asyncio.sleep(5)  # 每5秒更新一次
    
    def stop(self):
        """停止服务器"""
        self.running = False
        
    async def cleanup(self):
        """清理资源"""
        # 关闭所有 WebSocket 连接
        for ws in self.websockets:
            await ws.close()
        self.websockets.clear()
                    
    def run(self, config, host='0.0.0.0', port=8084):
        """运行服务器"""
        runner = web.AppRunner(self.app)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, host, port)
        loop.run_until_complete(site.start())
        
        # 启动余额更新循环
        loop.create_task(self.update_balance_loop(config))
        
        self.running = True
        print(f"Web server started at http://{host}:{port}")
        
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            print("Shutting down web server...")
            self.stop()
            loop.run_until_complete(self.cleanup())
        finally:
            loop.run_until_complete(runner.cleanup())

# 创建全局 web 服务器实例
web_server = WebServer()

if __name__ == '__main__':
    web_server.run() 