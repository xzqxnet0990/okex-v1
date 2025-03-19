import sys
import os
import time
import asyncio
from pathlib import Path
import aiohttp_cors

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy.spot_arbitrage import SpotArbitrage
from utils.simulated_account import SimulatedAccount
from utils.logger import Log, log_simulation_status
from datetime import datetime
from utils.config import load_config, load_supported_exchanges
from exchanges import ExchangeFactory
from utils.depth_data import fetch_all_depths_compat

from web_server import web_server
# 导入我们的WebSocket广播器
from utils import ws_broadcaster

 
 
async def simulate_strategy(initial_balance: float = 10000, update_interval: float = 1.0) -> None:
    """模拟策略"""
    # 加载配置
    config = load_config()
    if not config:
        Log("无法加载配置文件")
        return

    # 加载支持的交易所
    supported_exchanges = load_supported_exchanges()
    if not supported_exchanges:
        Log("无法加载支持的交易所配置")
        return
    config['supported_exchanges'] = supported_exchanges
    Log("配置文件中的交易所数量与交易对数量一致") \
        if (len(config.get('strategy', {}).get('COINS', [])) ==
            len(config.get('supported_exchanges', {}).keys())) \
        else Log("配置文件中的交易所数量与交易对数量不一致")

    # 初始化模拟账户
    Log(f"初始化模拟账户, 初始余额: {initial_balance}")
    account = SimulatedAccount(initial_balance, config)
    # 初始化所有交易所
    exchanges = {}
    try:
        # 获取所有需要初始化的交易所
        exchange_set = set()
        for coin, ex_list in supported_exchanges.items():
            exchange_set.update(ex_list)

        # 初始化每个交易所
        for exchange_type in exchange_set:
            exchange = ExchangeFactory.create_exchange(
                exchange_type,
                config.get('exchanges', {}).get(exchange_type.lower(), {}))
            if exchange:
                exchanges[exchange_type] = exchange
            else:
                Log(f"初始化交易所失败: {exchange_type}")

        if not exchanges:
            Log("没有成功初始化任何交易所")
            return
        Log(f"成功初始化 {len(exchanges)} 个交易所")
        Log(f"支持的交易所: {exchanges.keys()}")
        # 异步初始化账户
        await account.initialize()

        while True:
            # 处理每个币种的套利机会
            for coin in config.get('strategy', {}).get('COINS', []):

                current_time = datetime.now()
                Log(f"当前时间: {current_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")

                # 获取所有币种的深度数据
                start_time = time.time()
                spotArbitrage = SpotArbitrage(config)

                # 使用兼容模式获取深度数据
                all_depths = await fetch_all_depths_compat(coin, exchanges, supported_exchanges, config)
                
                elapsed_time = time.time() - start_time
                Log(f"获取所有深度数据耗时: {elapsed_time:.3f}秒")

                # 检查是否成功获取到深度数据
                if coin not in all_depths:
                    Log(f"{coin} 未获取到深度数据，跳过")
                    continue
                    
                coin_depths = all_depths[coin]  # 获取特定币种的深度数据
                
                # 检查是否有足够的交易所深度数据
                if len(coin_depths) < 2:
                    Log(f"{coin} 未获取到足够的深度数据，跳过")
                    continue

                # 处理该币种的套利机会
                await spotArbitrage.process_arbitrage_opportunities(coin, account, all_depths, current_time, config)

                # 更新状态显示
                await log_simulation_status(account, all_depths, current_time, config)

                # 短暂暂停，避免请求过于频繁
                await asyncio.sleep(0.1)

            # 等待下次更新周期
            await asyncio.sleep(update_interval)

    except KeyboardInterrupt:
        Log("模拟终止")
    finally:
        # 关闭所有交易所连接
        for ex in exchanges.values():
            await ex.close()


async def main():
    """主函数"""
    try:
        # 加载配置
        config = load_config()
        if not config:
            Log("配置文件不存在")
            return

        # 获取初始余额和更新间隔
        initial_balance = config['assets'].get('INITIAL_BALANCE', 10000)
        update_interval = config['strategy'].get('UPDATE_INTERVAL', 1.0)

        # 启动 WebSocket 服务器
        from aiohttp import web
        web_app = web.Application()
        
        # 添加WebSocket路由 - 使用我们的ws_broadcaster
        web_app.router.add_get('/ws', ws_broadcaster.handle_websocket)
        
        # 添加静态文件服务
        web_dir = Path(__file__).parent.parent / 'web-vue' / 'dist'
        if web_dir.exists():
            # 先添加根路径处理（重要：必须在静态文件服务之前）
            web_app.router.add_get('/', lambda request: web.FileResponse(web_dir / 'index.html'))
            # 再添加静态文件服务
            web_app.router.add_static('/', web_dir)
            Log(f"静态文件目录: {web_dir}")
        else:
            Log(f"警告: 静态文件目录不存在: {web_dir}")
            # 添加一个简单的根路径处理
            web_app.router.add_get('/', lambda request: web.Response(text="API服务器正在运行。前端文件未找到，请先构建前端。", content_type="text/html"))
        
        # 设置CORS
        cors = aiohttp_cors.setup(web_app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods=["GET", "POST", "OPTIONS"]
            )
        })
        
        # 确保所有路由都应用了CORS
        for route in list(web_app.router.routes()):
            try:
                cors.add(route)
            except Exception as e:
                Log(f"无法为路由添加CORS: {str(e)}")
        
        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', 8083)
        await site.start()
        Log("服务器已启动在 http://localhost:8083")
        Log("WebSocket 服务器已启动在 ws://localhost:8083/ws")

        # 运行策略
        await simulate_strategy(
            initial_balance=initial_balance,
            update_interval=update_interval
        )

    except KeyboardInterrupt:
        Log("程序被用户中断")
    except Exception as e:
        Log(f"程序异常退出: {str(e)}")
        import traceback
        Log(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())
