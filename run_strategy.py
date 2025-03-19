import asyncio
import json
from pathlib import Path
from utils import Log, _G
from web_server import web_server
from okex import State, Config, init, main_loop

def load_config():
    """加载配置文件"""
    config_path = Path('config/config.json')
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    return None

async def run_strategy():
    """运行策略"""
    try:
        # 加载配置
        config = load_config()
        if config:
            # 更新配置参数
            for key, value in config.get('strategy', {}).items():
                if hasattr(Config, key.upper()):
                    setattr(Config, key.upper(), value)
        
        # 初始化策略
        Log("正在初始化策略...")
        if not init():
            Log("策略初始化失败")
            return
        
        # 运行主循环
        Log("策略初始化成功，开始运行...")
        await main_loop()
        
    except KeyboardInterrupt:
        Log("收到终止信号，正在停止策略...")
    except Exception as e:
        Log(f"策略运行出错: {str(e)}")
    finally:
        # 保存最终状态
        _G("final_state", {
            "total_profit": State.total_profit,
            "daily_profit": State.daily_profit,
            "last_trade_time": State.last_trade_time
        })
        Log("策略已停止运行")

def main():
    """主入口函数"""
    # 设置事件循环策略
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # 加载配置
    config = load_config()
    if not config:
        Log("配置文件不存在")
        return
    
    # 启动web服务器
    Log("启动Web监控服务器...")
    web_server.run(config, host='localhost', port=8084)
    
    # 运行策略
    asyncio.run(run_strategy())

if __name__ == "__main__":
    import sys
    main() 