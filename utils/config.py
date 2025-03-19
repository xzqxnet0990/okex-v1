import json
import os
from typing import Dict, Any
from utils.logger import Log

def load_supported_exchanges() -> Dict[str, list]:
    """加载支持的交易所配置"""
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, 'config', 'supported_exchanges.json')

        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        Log(f"加载supported_exchanges.json失败: {str(e)}")
    return {}

def get_exchange_fee(exchange: str, symbol: str = None, is_maker: bool = False) -> float:
    """获取交易所费率"""
    try:
        config = load_config()
        exchange_config = config['exchanges'].get(exchange, {})

        # 如果有币种特定费率，使用币种特定费率
        if symbol and 'symbol_fees' in exchange_config:
            symbol_fees = exchange_config['symbol_fees'].get(symbol)
            if symbol_fees:
                return symbol_fees['maker'] if is_maker else symbol_fees['taker']

        # 否则使用默认费率
        default_fees = exchange_config.get('default_fees', {'maker': 0.001, 'taker': 0.0015})  # 降低默认费率
        return default_fees['maker'] if is_maker else default_fees['taker']
    except Exception as e:
        Log(f"获取{exchange}费率失败: {str(e)}")
        return 0.0015  # 返回较保守的taker费率作为默认值

def load_config() -> Dict[str, Any]:
    """加载配置"""
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, 'config', 'config.json')

        if not os.path.exists(config_path):
            Log(f"配置文件不存在: {config_path}")
            return {}

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 验证必要的配置项
        required_sections = ['strategy', 'exchanges', 'risk_control', 'web_server', 'logging']
        for section in required_sections:
            if section not in config:
                Log(f"配置文件缺少必要的部分: {section}")
                return {}

        # 设置默认值
        strategy_defaults = {
            'MIN_AMOUNT': 0.01,
            'SAFE_AMOUNT': 50,
            'MAX_DELTA_AMOUNT': 10,
            'MIN_PROFIT_PERCENT': 0.1,
            'MIGRATE_PROFIT_PERCENT': 0.05,
            'SLIPPAGE': 0.001,
            'PRICE_PRECISION': 8,
            'SAFE_PRICE': 100,
            'MAX_TRADE_PRICE': 500,
            'UPDATE_INTERVAL': 1,
            'MAX_DELAY': 100,
            'BALANCE_CHECK_INTERVAL': 60,

            # 添加对冲策略的默认配置
            'hedge': {
                'TARGET_BALANCE_MULTIPLIER': 3.0,
                'BALANCE_THRESHOLD_RATIO': 0.3,
                'MAX_POSITION_VALUE': 1000,
                'FEE_MULTIPLIER': 0.8,
                'USE_ASK_BID': True,
                'MIN_BASIS_PERCENT': 0.1  # 最小基差要求（百分比）
            }
        }

        risk_control_defaults = {
            'SINGLE_TRADE_LOSS_LIMIT': -50,
            'TOTAL_LOSS_LIMIT': -1000,
            'POSITION_LOSS_PERCENT': 0.1,
            'MAX_DRAWDOWN_PERCENT': 0.2,
            'DAILY_LOSS_LIMIT': -200,
            'MAX_POSITION_RATIO': 0.5,
            'MIN_LIQUIDITY_RATIO': 0.3,
            'MAX_SINGLE_EXPOSURE': 0.2
        }

        # 使用默认值填充缺失的配置项
        for key, value in strategy_defaults.items():
            if key not in config['strategy']:
                config['strategy'][key] = value

        for key, value in risk_control_defaults.items():
            if key not in config['risk_control']:
                config['risk_control'][key] = value

        return config

    except Exception as e:
        Log(f"加载配置文件失败: {str(e)}")
        return {} 