from typing import Dict, Optional

class Account:
    def __init__(self):
        self.balances: Dict[str, Dict[str, float]] = {}  # exchange -> {coin -> amount}
        self.fees: Dict[str, Dict[str, float]] = {}  # exchange -> {type -> fee_rate}

    def get_balance(self, exchange: str, coin: str) -> float:
        """获取指定交易所的指定币种余额"""
        return self.balances.get(exchange, {}).get(coin, 0.0)

    def update_balance(self, exchange: str, coin: str, amount: float):
        """更新指定交易所的指定币种余额"""
        if exchange not in self.balances:
            self.balances[exchange] = {}
        self.balances[exchange][coin] = self.get_balance(exchange, coin) + amount

    def get_fee(self, exchange: str, fee_type: str) -> float:
        """获取指定交易所的指定类型手续费率"""
        return self.fees.get(exchange, {}).get(fee_type, 0.001)  # 默认0.1%

    async def spot_buy(self, exchange: str, coin: str, amount: float, price: float) -> Optional[str]:
        """现货买入"""
        try:
            usdt_needed = amount * price
            if self.get_balance(exchange, "USDT") >= usdt_needed:
                self.update_balance(exchange, "USDT", -usdt_needed)
                self.update_balance(exchange, coin, amount)
                return "success"
            return None
        except Exception as e:
            print(f"买入失败: {str(e)}")
            return None

    async def spot_sell(self, exchange: str, coin: str, amount: float, price: float) -> Optional[str]:
        """现货卖出"""
        try:
            if self.get_balance(exchange, coin) >= amount:
                self.update_balance(exchange, coin, -amount)
                self.update_balance(exchange, "USDT", amount * price)
                return "success"
            return None
        except Exception as e:
            print(f"卖出失败: {str(e)}")
            return None 