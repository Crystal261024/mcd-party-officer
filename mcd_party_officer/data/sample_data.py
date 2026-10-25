"""离线演示 / 测试用的示例数据。

⚠️ 重要：以下价格、营养、优惠券均为「示例占位数据」，仅用于在本机无 Token 时
跑通逻辑与单元测试。真实场景下这些值**必须**来自麦当劳 MCP 接口：
- 餐品与价格：query-meals / query-meal-detail
- 营养：list-nutrition-foods
- 优惠券：query-my-coupons / query-store-coupons / available-coupons
切勿让大模型自行估算价格或营养——这是官方明确的高频踩坑点。
"""

from __future__ import annotations

from ..models import Coupon, CouponType, MenuItem, NutritionInfo

# 套餐
SET_MEALS = [
    MenuItem(
        code="M1", name="巨无霸套餐", category="套餐", price=42.5, is_set_meal=True,
        tags=["经典", "牛肉"],
        nutrition=NutritionInfo(calories=900, protein=35, fat=40, carbohydrate=95, sodium=1100, calcium=200),
    ),
    MenuItem(
        code="M2", name="麦辣鸡腿堡套餐", category="套餐", price=39.5, is_set_meal=True,
        tags=["辣", "鸡肉"],
        nutrition=NutritionInfo(calories=850, protein=32, fat=38, carbohydrate=92, sodium=1050, calcium=180),
    ),
    MenuItem(
        code="M3", name="双层吉士套餐", category="套餐", price=45.0, is_set_meal=True,
        tags=["牛肉", "芝士"],
        nutrition=NutritionInfo(calories=950, protein=40, fat=45, carbohydrate=90, sodium=1200, calcium=300),
    ),
]

# 单点
A_LA_CARTE = [
    MenuItem(
        code="A1", name="麦辣鸡翅(2块)", category="小食", price=13.0,
        tags=["辣", "鸡肉"],
        nutrition=NutritionInfo(calories=300, protein=18, fat=18, carbohydrate=15, sodium=600, calcium=40),
    ),
    MenuItem(
        code="A2", name="中份薯条", category="小食", price=12.0,
        tags=["素食"],
        nutrition=NutritionInfo(calories=320, protein=4, fat=16, carbohydrate=40, sodium=250, calcium=10),
    ),
    MenuItem(
        code="A3", name="可口可乐(中)", category="饮品", price=9.5,
        tags=["饮品", "含糖"],
        nutrition=NutritionInfo(calories=110, protein=0, fat=0, carbohydrate=28, sodium=20, calcium=0),
    ),
    MenuItem(
        code="A4", name="玉米杯", category="小食", price=10.0,
        tags=["素食", "低卡"],
        nutrition=NutritionInfo(calories=90, protein=3, fat=1, carbohydrate=19, sodium=15, calcium=5),
    ),
    MenuItem(
        code="A5", name="麦香鸡", category="主食", price=15.0,
        tags=["鸡肉"],
        nutrition=NutritionInfo(calories=400, protein=20, fat=21, carbohydrate=35, sodium=700, calcium=60),
    ),
]

# 买一送一券绑定的「特殊 SKU」单品（注意：不是普通单品）
SPECIAL_SKU_ITEMS = [
    MenuItem(
        code="B1", name="香芋派(买一送一装)", category="甜品", price=7.0,
        tags=["甜品", "买一送一"], special_sku="PIE_BOGO",
        nutrition=NutritionInfo(calories=230, protein=3, fat=9, carbohydrate=34, sodium=180, calcium=50),
    ),
]

ALL_ITEMS = SET_MEALS + A_LA_CARTE + SPECIAL_SKU_ITEMS

# 示例优惠券（与上方规则一致：一单1券、套餐可叠券、BOGO绑特殊SKU）
SAMPLE_COUPONS = [
    Coupon(coupon_id="C1", name="满40减6", coupon_type=CouponType.THRESHOLD,
           value=6.0, min_order_amount=40.0),
    Coupon(coupon_id="C2", name="套餐8折券", coupon_type=CouponType.PERCENT,
           ratio=0.8, min_order_amount=0.0, setmeal_only=True),
    Coupon(coupon_id="C3", name="派买一送一", coupon_type=CouponType.BOGO,
           value=7.0, bound_sku="PIE_BOGO"),
    Coupon(coupon_id="C4", name="满60减12", coupon_type=CouponType.THRESHOLD,
           value=12.0, min_order_amount=60.0),
]


def item_by_code(code: str) -> MenuItem | None:
    for it in ALL_ITEMS:
        if it.code == code:
            return it
    return None
