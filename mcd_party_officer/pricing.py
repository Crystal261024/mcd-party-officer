"""价格计算引擎。

核心原则（官方踩坑提醒）：价格、优惠必须来自 MCP 接口的 calculate-price，
不要让大模型自己估算。因此本模块提供两个实现：
- McpPriceEngine：生产环境，直接调用麦当劳 MCP 的 calculate-price。
- LocalPriceEngine：离线/测试用，本地复刻优惠规则，仅用于跑通逻辑。

优化器只依赖 PriceEngine 抽象接口，从而保证「真实环境一定走 MCP」。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable, Optional

from .client import McpClient
from .models import Coupon, MenuItem, PriceBreakdown


def _subtotal(items: Iterable[MenuItem]) -> float:
    return sum(it.price for it in items)


class PriceEngine(ABC):
    @abstractmethod
    def compute(self, items: list[MenuItem], coupon: Optional[Coupon]) -> PriceBreakdown:
        """计算给定商品列表（可挂一张券）的价格明细。"""
        raise NotImplementedError


class LocalPriceEngine(PriceEngine):
    """本地价格引擎（离线演示 / 单元测试）。

    仅用于在无 Token 时验证拆单与优化逻辑。其优惠规则与真实 MCP 保持一致：
    一单1券、套餐可叠券、BOGO 绑特殊 SKU。
    """

    def __init__(self, delivery_fee: float = 0.0) -> None:
        self.delivery_fee = delivery_fee

    def compute(self, items: list[MenuItem], coupon: Optional[Coupon]) -> PriceBreakdown:
        subtotal = _subtotal(items)
        discount = 0.0
        if coupon is not None:
            discount = self._coupon_discount(items, coupon)
        payable = max(0.0, subtotal + self.delivery_fee - discount)
        return PriceBreakdown(
            subtotal=subtotal,
            delivery_fee=self.delivery_fee,
            discount=discount,
            payable=payable,
        )

    @staticmethod
    def _coupon_discount(items: list[MenuItem], coupon: Coupon) -> float:
        if coupon.coupon_type.value == "threshold":
            if _subtotal(items) >= coupon.min_order_amount:
                return coupon.value
            return 0.0
        if coupon.coupon_type.value == "percent":
            # 仅对套餐部分打折；且要求订单含套餐（setmeal_only）
            if coupon.setmeal_only and not any(it.is_set_meal for it in items):
                return 0.0
            setmeal_sub = sum(it.price for it in items if it.is_set_meal)
            return round(setmeal_sub * (1.0 - coupon.ratio), 2)
        if coupon.coupon_type.value == "bogo":
            # 必须含绑定的特殊 SKU；优惠 = 一个免费单品的价格
            sku = coupon.bound_sku
            if sku and any(it.special_sku == sku for it in items):
                for it in items:
                    if it.special_sku == sku:
                        return it.price
            return 0.0
        return 0.0


class McpPriceEngine(PriceEngine):
    """生产价格引擎：调用麦当劳 MCP calculate-price（事实数据唯一来源）。

    按真实 schema：需要 storeCode + orderType + beType；优惠券挂在 **item 级**
    （couponId / couponCode）。一单仍只用一张券（由调用方保证每张订单只传一个 coupon）。
    """

    def __init__(
        self,
        client: McpClient,
        store_code: Optional[str] = None,
        order_type: int = 1,
        be_type: int = 1,
        be_code: Optional[str] = None,
    ) -> None:
        self.client = client
        self.store_code = store_code
        self.order_type = order_type
        self.be_type = be_type
        self.be_code = be_code

    def compute(self, items: list[MenuItem], coupon: Optional[Coupon]) -> PriceBreakdown:
        item_list: list[dict] = []
        for it in items:
            entry: dict = {"code": it.code, "quantity": 1}
            if coupon is not None:
                # 券挂到该单唯一一张券；有 ID 优先 couponId，否则用 couponCode/绑定 SKU
                if coupon.coupon_id:
                    entry["couponId"] = coupon.coupon_id
                elif coupon.bound_sku:
                    entry["couponCode"] = coupon.bound_sku
            item_list.append(entry)

        arguments: dict[str, Any] = {
            "items": item_list,
            "orderType": self.order_type,
            "beType": self.be_type,
        }
        if self.store_code:
            arguments["storeCode"] = self.store_code
        if self.be_code:
            arguments["beCode"] = self.be_code

        data = self.client.call_json("calculate-price", arguments) or {}
        d = data.get("data", data) if isinstance(data.get("data"), dict) else data

        def pick(*keys: str) -> float:
            for k in keys:
                if k in d and d[k] not in (None, ""):
                    try:
                        return float(d[k])
                    except (TypeError, ValueError):
                        continue
            return 0.0

        subtotal = pick("originalAmount", "subtotal", "totalPrice", "originalTotalPrice")
        delivery_fee = pick("deliveryFee", "deliveryAmount", "freight")
        discount = pick("discount", "couponAmount", "discountAmount", "promotionAmount")
        payable = pick("actualAmount", "payable", "payAmount", "totalAmount")
        if not payable:
            payable = max(0.0, subtotal + delivery_fee - discount)
        return PriceBreakdown(
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            discount=discount,
            payable=payable,
        )
