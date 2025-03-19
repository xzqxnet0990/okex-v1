from dataclasses import dataclass
from typing import List

@dataclass
class Order:
    price: float
    amount: float

@dataclass
class Depth:
    asks: List[Order]  # 卖单列表
    bids: List[Order]  # 买单列表 