"""拆单器：把多人的餐品按优惠规则拆成多张订单，最大化优惠。

关键规则（官方踩坑提醒，绝不违反）：
- 一单仅可挂载 1 张优惠券  -> 每张 OrderPlan 最多持有 1 个 coupon。
- 套餐可以和 1 张券叠加    -> 含套餐的订单可正常挂券。
- 买一送一(BOGO) 绑特殊SKU -> 只有含对应特殊单品的订单才能触发该券。
所有金额以 PriceEngine（生产=MCP calculate-price）返回为准。
"""

from __future__ import annotations

from typing import Optional

from .models import Coupon, CouponType, MenuItem, OrderPlan, SplitPlan
from .pricing import PriceEngine


def coupon_eligible(items: list[MenuItem], coupon: Coupon) -> bool:
    """判断该优惠券是否能挂到这份商品清单上。"""
    if coupon.coupon_type == CouponType.THRESHOLD:
        subtotal = sum(it.price for it in items)
        return subtotal >= coupon.min_order_amount
    if coupon.coupon_type == CouponType.PERCENT:
        if coupon.setmeal_only:
            return any(it.is_set_meal for it in items)
        return True
    if coupon.coupon_type == CouponType.BOGO:
        return any(it.special_sku == coupon.bound_sku for it in items)
    return True


def _best_coupon_for(
    items: list[MenuItem], coupons: list[Coupon], used: set[str], engine: PriceEngine
) -> tuple[Optional[Coupon], float]:
    """为一份商品清单挑选能使其应付最低的那张（未使用）券。"""
    base = engine.compute(items, None).payable
    best: Optional[Coupon] = None
    best_payable = base
    for c in coupons:
        if c.coupon_id in used:
            continue
        if not coupon_eligible(items, c):
            continue
        payable = engine.compute(items, c).payable
        if payable < best_payable - 1e-9:
            best, best_payable = c, payable
    return best, best_payable


def assign_coupons(
    item_groups: list[list[MenuItem]],
    coupons: list[Coupon],
    engine: PriceEngine,
) -> SplitPlan:
    """为每组餐品（通常每人一组）分配最优券，并做拆单。

    第一步：每人一组，贪心挑选使该单应付最低的券（每张券全局只用一次）。
    第二步：回收「买一送一」特殊 SKU —— 若某无券订单里躺着特殊 SKU 单品，
            且有未使用的 BOGO 券，则把它单独拆出成新订单挂上该券。
    """
    used: set[str] = set()
    orders: list[OrderPlan] = []

    for idx, group in enumerate(item_groups):
        if not group:
            continue
        coupon, payable = _best_coupon_for(group, coupons, used, engine)
        price = engine.compute(group, coupon)
        if coupon is not None:
            used.add(coupon.coupon_id)
        orders.append(
            OrderPlan(order_index=idx, items=list(group), coupon=coupon, price=price)
        )

    # 第二步：BOGO 特殊 SKU 回收
    leftover_bogo = [
        c for c in coupons
        if c.coupon_id not in used and c.coupon_type == CouponType.BOGO
    ]
    for bogo in leftover_bogo:
        for order in orders:
            if order.coupon is not None:
                continue
            sku_items = [it for it in order.items if it.special_sku == bogo.bound_sku]
            if not sku_items:
                continue
            # 把特殊 SKU 单品从原订单拆出，单独成单挂 BOGO 券
            moved = sku_items[0]
            order.items = [it for it in order.items if it is not moved]
            order.price = engine.compute(order.items, None)
            new_order = OrderPlan(
                order_index=len(orders),
                items=[moved],
                coupon=bogo,
                price=engine.compute([moved], bogo),
            )
            orders.append(new_order)
            used.add(bogo.coupon_id)
            break

    # 重新整理 order_index
    for i, o in enumerate(orders):
        o.order_index = i
    return SplitPlan(orders=orders)
