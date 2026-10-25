"""mcd-party-officer（麦算盘）：基于麦当劳 MCP 的多人团餐最优配单 Skill。

核心能力：
- 多人聚餐时间协调（party_time）
- 套餐 + 优惠券组合优化，带减脂热量约束（optimizer）
- 拆单下单，严格遵守「一单1券 / 套餐叠券 / BOGO绑特殊SKU」（split_order）
- 价格、营养、优惠一律来自麦当劳 MCP 接口（client / menu / pricing）

安全：MCP Token 仅从环境变量 MCD_MCP_TOKEN 读取，绝不入库。
"""

from __future__ import annotations

from .client import McpAuthError, McpClient, McpRateLimitError
from .models import (
    Availability,
    Coupon,
    CouponType,
    MenuItem,
    NutritionInfo,
    OrderPlan,
    Participant,
    PartySession,
    PriceBreakdown,
    SplitPlan,
    TimeSlot,
)
from .optimizer import build_basket, optimize
from .party_time import PartyTimeCoordinator
from .pricing import LocalPriceEngine, McpPriceEngine, PriceEngine
from .split_order import assign_coupons, coupon_eligible

__version__ = "1.0.0"
__all__ = [
    "McpClient",
    "McpAuthError",
    "McpRateLimitError",
    "MenuItem",
    "Coupon",
    "CouponType",
    "NutritionInfo",
    "Participant",
    "OrderPlan",
    "SplitPlan",
    "PriceBreakdown",
    "TimeSlot",
    "Availability",
    "PartySession",
    "PartyTimeCoordinator",
    "optimize",
    "build_basket",
    "assign_coupons",
    "coupon_eligible",
    "PriceEngine",
    "LocalPriceEngine",
    "McpPriceEngine",
]
