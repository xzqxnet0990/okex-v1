import time
from typing import Dict, Any, Optional, Union, List
from datetime import datetime

from strategy.trade_status import TradeStatus
from strategy.trade_type import TradeType
from utils.calculations import _N
from utils.logger import Log


class TradeRecord:
    """交易记录类，用于创建和处理交易记录"""

    @staticmethod
    def create_balance_record(
            coin: str,
            source_exchange: str,
            target_exchange: str,
            amount: float,
            price: float,
            source_balance_before: float,
            source_balance_after: float,
            target_balance_before: float,
            target_balance_after: float,
            source_change: float,
            target_change: float,
            total_change: float,
            expected_profit_ratio: Optional[float] = None,
            expected_profit: Optional[float] = None,
            status: str = TradeStatus.SUCCESS
    ) -> Dict[str, Any]:
        """
        创建余额调整交易记录

        Args:
            coin: 币种
            source_exchange: 源交易所
            target_exchange: 目标交易所
            amount: 交易数量
            price: 交易价格
            source_balance_before: 交易前源交易所余额
            source_balance_after: 交易后源交易所余额
            target_balance_before: 交易前目标交易所余额
            target_balance_after: 交易后目标交易所余额
            source_change: 源交易所余额变化
            target_change: 目标交易所余额变化
            total_change: 总余额变化
            expected_profit_ratio: 预期利润率
            expected_profit: 预期利润
            status: 交易状态

        Returns:
            Dict[str, Any]: 交易记录字典
        """
        return {
            "type": TradeType.BALANCE_OPERATION,
            "coin": coin,
            "source_exchange": source_exchange,
            "target_exchange": target_exchange,
            "amount": amount,
            "price": price,
            "source_balance_before": source_balance_before,
            "source_balance_after": source_balance_after,
            "target_balance_before": target_balance_before,
            "target_balance_after": target_balance_after,
            "source_change": source_change,
            "target_change": target_change,
            "total_change": total_change,
            "expected_profit_ratio": expected_profit_ratio,
            "expected_profit": expected_profit,
            "status": status,
            "timestamp": time.time(),
            "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    @staticmethod
    def create_arbitrage_record(
            coin: str,
            buy_exchange: str,
            sell_exchange: str,
            amount: float,
            buy_price: float,
            sell_price: float,
            buy_fee: float,
            sell_fee: float,
            profit: float,
            status: str = TradeStatus.SUCCESS
    ) -> Dict[str, Any]:
        """
        创建套利交易记录

        Args:
            coin: 币种
            buy_exchange: 买入交易所
            sell_exchange: 卖出交易所
            amount: 交易数量
            buy_price: 买入价格
            sell_price: 卖出价格
            buy_fee: 买入手续费
            sell_fee: 卖出手续费
            profit: 利润
            status: 交易状态

        Returns:
            Dict[str, Any]: 交易记录字典
        """
        return {
            "type": TradeType.ARBITRAGE,
            "coin": coin,
            "buy_exchange": buy_exchange,
            "sell_exchange": sell_exchange,
            "amount": amount,
            "buy_price": buy_price,
            "sell_price": sell_price,
            "buy_fee": buy_fee,
            "sell_fee": sell_fee,
            "profit": profit,
            "status": status,
            "timestamp": time.time(),
            "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    @staticmethod
    def create_pending_trade_record(
            coin: str,
            exchange: str,
            order_type: str,  # 'buy' 或 'sell'
            amount: float,
            price: float,
            estimated_fee: float,
            balance_before: float,
            usdt_before: float,
            order_id: str = "",
            status: str = TradeStatus.PENDING,
            reason: str = ""
    ) -> Dict[str, Any]:
        """
        创建挂单交易记录

        Args:
            coin: 币种
            exchange: 交易所
            order_type: 订单类型（买入/卖出）
            amount: 交易数量
            price: 交易价格
            estimated_fee: 估计手续费
            balance_before: 交易前币种余额
            usdt_before: 交易前USDT余额
            order_id: 订单ID
            status: 交易状态
            reason: 备注信息

        Returns:
            Dict[str, Any]: 交易记录字典
        """
        return {
            "type": TradeType.PENDING_TRADE,
            "coin": coin,
            "exchange": exchange,
            "order_type": order_type,
            "amount": amount,
            "price": price,
            "estimated_fee": estimated_fee,
            "balance_before": balance_before,
            "usdt_before": usdt_before,
            "order_id": order_id,
            "status": status,
            "reason": reason,
            "timestamp": time.time(),
            "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    @staticmethod
    def create_reverse_pending_record(
            coin: str,
            exchange: str,
            original_order_type: str,  # 原始订单类型 'buy' 或 'sell'
            original_amount: float,
            original_price: float,
            original_order_id: str,
            reverse_amount: float,
            reverse_price: float,
            balance_before: float,
            usdt_before: float,
            status: str = TradeStatus.SUCCESS,
            reason: str = ""
    ) -> Dict[str, Any]:
        """
        创建撤销挂单交易记录

        Args:
            coin: 币种
            exchange: 交易所
            original_order_type: 原始订单类型（买入/卖出）
            original_amount: 原始订单数量
            original_price: 原始订单价格
            original_order_id: 原始订单ID
            reverse_amount: 撤销数量
            reverse_price: 撤销时的市场价格
            balance_before: 撤销前币种余额
            usdt_before: 撤销前USDT余额
            status: 交易状态
            reason: 撤销原因

        Returns:
            Dict[str, Any]: 交易记录字典
        """
        return {
            "type": TradeType.REVERSE_PENDING,
            "coin": coin,
            "exchange": exchange,
            "original_order_type": original_order_type,
            "original_amount": original_amount,
            "original_price": original_price,
            "original_order_id": original_order_id,
            "reverse_amount": reverse_amount,
            "reverse_price": reverse_price,
            "balance_before": balance_before,
            "usdt_before": usdt_before,
            "status": status,
            "reason": reason,
            "timestamp": time.time(),
            "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    @staticmethod
    def create_hedge_buy_record(
            coin: str,
            exchange: str,
            amount: float,
            price: float,
            fee: float,
            balance_before: float,
            balance_after: float,
            usdt_before: float,
            usdt_after: float,
            status: str = TradeStatus.SUCCESS,
            reason: str = ""
    ) -> Dict[str, Any]:
        """
        创建对冲买入交易记录

        Args:
            coin: 币种
            exchange: 交易所
            amount: 交易数量
            price: 交易价格
            fee: 手续费
            balance_before: 交易前币种余额
            balance_after: 交易后币种余额
            usdt_before: 交易前USDT余额
            usdt_after: 交易后USDT余额
            status: 交易状态
            reason: 失败原因（如果状态为失败）

        Returns:
            Dict[str, Any]: 交易记录字典
        """
        return {
            "type": TradeType.HEDGE_BUY,
            "coin": coin,
            "exchange": exchange,
            "amount": amount,
            "price": price,
            "fee": fee,
            "balance_before": balance_before,
            "balance_after": balance_after,
            "balance_change": balance_after - balance_before,
            "usdt_before": usdt_before,
            "usdt_after": usdt_after,
            "usdt_change": usdt_after - usdt_before,
            "status": status,
            "reason": reason if status != TradeStatus.SUCCESS else "",
            "timestamp": time.time(),
            "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    @staticmethod
    def create_hedge_sell_record(
            coin: str,
            exchange: str,
            amount: float,
            price: float,
            fee: float,
            balance_before: float,
            balance_after: float,
            usdt_before: float,
            usdt_after: float,
            status: str = TradeStatus.SUCCESS,
            reason: str = ""
    ) -> Dict[str, Any]:
        """
        创建对冲卖出交易记录

        Args:
            coin: 币种
            exchange: 交易所
            amount: 交易数量
            price: 交易价格
            fee: 手续费
            balance_before: 交易前币种余额
            balance_after: 交易后币种余额
            usdt_before: 交易前USDT余额
            usdt_after: 交易后USDT余额
            status: 交易状态
            reason: 失败原因（如果状态为失败）

        Returns:
            Dict[str, Any]: 交易记录字典
        """
        return {
            "type": TradeType.HEDGE_SELL,
            "coin": coin,
            "exchange": exchange,
            "amount": amount,
            "price": price,
            "fee": fee,
            "balance_before": balance_before,
            "balance_after": balance_after,
            "balance_change": balance_after - balance_before,
            "usdt_before": usdt_before,
            "usdt_after": usdt_after,
            "usdt_change": usdt_after - usdt_before,
            "status": status,
            "reason": reason if status != TradeStatus.SUCCESS else "",
            "timestamp": time.time(),
            "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    @staticmethod
    def create_hedge_record(
            coin: str,
            exchange: str,
            trade_type: str,
            amount: float,
            price: float,
            fee: float,
            balance_before: float,
            balance_after: float,
            usdt_before: Optional[float] = None,
            usdt_after: Optional[float] = None,
            status: str = TradeStatus.SUCCESS,
            reason: str = ""
    ) -> Dict[str, Any]:
        """
        创建对冲交易记录（兼容旧版本）

        Args:
            coin: 币种
            exchange: 交易所
            trade_type: 交易类型（买入/卖出）
            amount: 交易数量
            price: 交易价格
            fee: 手续费
            balance_before: 交易前余额
            balance_after: 交易后余额
            usdt_before: 交易前USDT余额
            usdt_after: 交易后USDT余额
            status: 交易状态
            reason: 失败原因（如果状态为失败）

        Returns:
            Dict[str, Any]: 交易记录字典
        """
        if trade_type.upper() == "BUY":
            return TradeRecord.create_hedge_buy_record(
                coin=coin,
                exchange=exchange,
                amount=amount,
                price=price,
                fee=fee,
                balance_before=balance_before,
                balance_after=balance_after,
                usdt_before=usdt_before if usdt_before is not None else 0,
                usdt_after=usdt_after if usdt_after is not None else 0,
                status=status,
                reason=reason
            )
        else:
            return TradeRecord.create_hedge_sell_record(
                coin=coin,
                exchange=exchange,
                amount=amount,
                price=price,
                fee=fee,
                balance_before=balance_before,
                balance_after=balance_after,
                usdt_before=usdt_before if usdt_before is not None else 0,
                usdt_after=usdt_after if usdt_after is not None else 0,
                status=status,
                reason=reason
            )

    @staticmethod
    def log_trade_record(record: Dict[str, Any]) -> None:
        """
        记录交易记录到日志

        Args:
            record: 交易记录字典
        """
        trade_type = record.get("type", "未知")
        
        if trade_type == TradeType.BALANCE_OPERATION:
            Log(f"余额调整交易记录:")
            Log(f"币种: {record.get('coin', '未知')}")
            Log(f"源交易所: {record.get('source_exchange', '未知')}")
            Log(f"目标交易所: {record.get('target_exchange', '未知')}")
            Log(f"数量: {_N(record.get('amount', 0), 6)}")
            Log(f"价格: {_N(record.get('price', 0), 6)}")
            Log(f"源交易所余额变化: {_N(record.get('source_change', 0), 6)}")
            Log(f"目标交易所余额变化: {_N(record.get('target_change', 0), 6)}")
            Log(f"总余额变化: {_N(record.get('total_change', 0), 6)}")
            
            if "expected_profit_ratio" in record and record["expected_profit_ratio"] is not None:
                Log(f"预期利润率: {_N(record.get('expected_profit_ratio', 0) * 100, 4)}%")
            
            if "expected_profit" in record and record["expected_profit"] is not None:
                Log(f"预期利润: {_N(record.get('expected_profit', 0), 6)} USDT")
            
            Log(f"状态: {record.get('status', '未知')}")
            
        elif trade_type == TradeType.ARBITRAGE:
            Log(f"套利交易记录:")
            Log(f"币种: {record.get('coin', '未知')}")
            Log(f"买入交易所: {record.get('buy_exchange', '未知')}")
            Log(f"卖出交易所: {record.get('sell_exchange', '未知')}")
            Log(f"数量: {_N(record.get('amount', 0), 6)}")
            Log(f"买入价格: {_N(record.get('buy_price', 0), 6)}")
            Log(f"卖出价格: {_N(record.get('sell_price', 0), 6)}")
            Log(f"买入手续费: {_N(record.get('buy_fee', 0), 6)}")
            Log(f"卖出手续费: {_N(record.get('sell_fee', 0), 6)}")
            Log(f"利润: {_N(record.get('profit', 0), 6)}")
            Log(f"状态: {record.get('status', '未知')}")
            
        elif trade_type == TradeType.PENDING_TRADE:
            Log(f"挂单交易记录:")
            Log(f"币种: {record.get('coin', '未知')}")
            Log(f"交易所: {record.get('exchange', '未知')}")
            Log(f"订单类型: {record.get('order_type', '未知')}")
            Log(f"数量: {_N(record.get('amount', 0), 6)}")
            Log(f"价格: {_N(record.get('price', 0), 6)}")
            Log(f"估计手续费: {_N(record.get('estimated_fee', 0), 6)}")
            Log(f"交易前币种余额: {_N(record.get('balance_before', 0), 6)}")
            Log(f"交易前USDT余额: {_N(record.get('usdt_before', 0), 6)}")
            if record.get('order_id'):
                Log(f"订单ID: {record.get('order_id', '')}")
            Log(f"状态: {record.get('status', '未知')}")
            if record.get('reason'):
                Log(f"备注: {record.get('reason', '')}")
                
        elif trade_type == TradeType.REVERSE_PENDING:
            Log(f"撤销挂单交易记录:")
            Log(f"币种: {record.get('coin', '未知')}")
            Log(f"交易所: {record.get('exchange', '未知')}")
            Log(f"原始订单类型: {record.get('original_order_type', '未知')}")
            Log(f"原始订单数量: {_N(record.get('original_amount', 0), 6)}")
            Log(f"原始订单价格: {_N(record.get('original_price', 0), 6)}")
            Log(f"原始订单ID: {record.get('original_order_id', '')}")
            Log(f"撤销数量: {_N(record.get('reverse_amount', 0), 6)}")
            Log(f"撤销时市场价格: {_N(record.get('reverse_price', 0), 6)}")
            Log(f"撤销前币种余额: {_N(record.get('balance_before', 0), 6)}")
            Log(f"撤销前USDT余额: {_N(record.get('usdt_before', 0), 6)}")
            Log(f"状态: {record.get('status', '未知')}")
            if record.get('reason'):
                Log(f"撤销原因: {record.get('reason', '')}")
            
        elif trade_type == TradeType.HEDGE_BUY:
            Log(f"对冲买入交易记录:")
            Log(f"币种: {record.get('coin', '未知')}")
            Log(f"交易所: {record.get('exchange', '未知')}")
            Log(f"数量: {_N(record.get('amount', 0), 6)}")
            Log(f"价格: {_N(record.get('price', 0), 6)}")
            Log(f"手续费: {_N(record.get('fee', 0), 6)}")
            Log(f"币种余额变化: {_N(record.get('balance_change', 0), 6)}")
            Log(f"USDT余额变化: {_N(record.get('usdt_change', 0), 6)}")
            Log(f"状态: {record.get('status', '未知')}")
            if record.get('reason'):
                Log(f"失败原因: {record.get('reason', '')}")
                
        elif trade_type == TradeType.HEDGE_SELL:
            Log(f"对冲卖出交易记录:")
            Log(f"币种: {record.get('coin', '未知')}")
            Log(f"交易所: {record.get('exchange', '未知')}")
            Log(f"数量: {_N(record.get('amount', 0), 6)}")
            Log(f"价格: {_N(record.get('price', 0), 6)}")
            Log(f"手续费: {_N(record.get('fee', 0), 6)}")
            Log(f"币种余额变化: {_N(record.get('balance_change', 0), 6)}")
            Log(f"USDT余额变化: {_N(record.get('usdt_change', 0), 6)}")
            Log(f"状态: {record.get('status', '未知')}")
            if record.get('reason'):
                Log(f"失败原因: {record.get('reason', '')}")
            
        elif trade_type == TradeType.HEDGE:
            # 兼容旧版本
            Log(f"对冲交易记录:")
            Log(f"币种: {record.get('coin', '未知')}")
            Log(f"交易所: {record.get('exchange', '未知')}")
            Log(f"交易类型: {record.get('trade_type', '未知')}")
            Log(f"数量: {_N(record.get('amount', 0), 6)}")
            Log(f"价格: {_N(record.get('price', 0), 6)}")
            Log(f"手续费: {_N(record.get('fee', 0), 6)}")
            Log(f"余额变化: {_N(record.get('balance_change', 0), 6)}")
            Log(f"状态: {record.get('status', '未知')}")
            
        else:
            Log(f"未知交易类型记录: {record}") 