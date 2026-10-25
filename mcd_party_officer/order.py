"""下单适配层：调用麦当劳 MCP 的 create-order / calculate-price。

生产环境所有金额以 calculate-price 返回为准（见 pricing.McpPriceEngine）。
本模块只负责把本地 OrderPlan 转换为 MCP 下单参数并发起创建。
"""

from __future__ import annotations

from typing import Any, Optional

from .client import McpClient
from .models import OrderPlan


def build_order_args(
    store_id: str,
    fulfill_type: str,  # "delivery" | "pickup" | "drive_thru"
    order: OrderPlan,
    address: Optional[str] = None,
) -> dict:
    """把 OrderPlan 转成 create-order 入参。"""
    return {
        "storeId": store_id,
        "fulfillType": fulfill_type,
        "items": [{"code": it.code, "quantity": 1} for it in order.items],
        "couponId": order.coupon.coupon_id if order.coupon else None,
        "address": address,
    }


def create_order(
    client: McpClient,
    store_id: str,
    fulfill_type: str,
    order: OrderPlan,
    address: Optional[str] = None,
) -> dict:
    """创建一张订单，返回订单详情与支付链接（来自 MCP）。"""
    args = build_order_args(store_id, fulfill_type, order, address)
    result = client.call_tool("create-order", args)
    if isinstance(result, dict) and "content" in result:
        import json
        text = "\n".join(
            c.get("text", "") for c in result["content"] if c.get("type") == "text"
        )
        try:
            return json.loads(text)
        except Exception:
            return {"raw": text}
    return result or {}


def submit_split_plan(
    client: McpClient,
    store_id: str,
    fulfill_type: str,
    plan,
    address: Optional[str] = None,
) -> list[dict]:
    """依次提交拆单方案中的每一张订单（每单挂1券）。"""
    receipts: list[dict] = []
    for order in plan.orders:
        receipts.append(
            create_order(client, store_id, fulfill_type, order, address)
        )
    return receipts
