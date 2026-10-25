"""麦算盘优化器（多人团餐最优配单）。

职责：
1. 为每位参与者在「热量预算」约束下搭配餐品（减脂约束）。
2. 把所有人点的餐汇总，交给拆单器按「一单1券 / 套餐可叠券 / BOGO绑特殊SKU」
   的规则做最优配单，最大化优惠。
3. 价格一律交由 PriceEngine（生产环境 = MCP calculate-price）计算，不自行估算。

注意：本模块只做「组合与约束求解」，所有价格/营养/券的"真值"来自 MCP。
"""

from __future__ import annotations

from typing import Optional

from .models import Coupon, MenuItem, Participant, SplitPlan
from .pricing import PriceEngine
from .split_order import assign_coupons


def build_basket(
    participant: Participant,
    catalog: list[MenuItem],
    engine: Optional[PriceEngine] = None,
) -> tuple[list[MenuItem], list[str]]:
    """为单个参与者构建点餐篮（满足热量预算与忌口）。

    返回 (篮内餐品, 警告信息列表)。
    """
    warnings: list[str] = []
    basket: list[MenuItem] = []

    if participant.wanted_item_codes:
        for code in participant.wanted_item_codes:
            item = next((it for it in catalog if it.code == code), None)
            if item is None:
                warnings.append(f"想要的餐品 {code} 不在菜单中，已忽略")
                continue
            if any(t in item.tags for t in participant.avoid_tags):
                warnings.append(f"{item.name} 含忌口标签，已忽略")
                continue
            basket.append(item)
        _check_calorie(basket, participant, warnings)
        return basket, warnings

    # 自动搭配：优先选一个契合预算、无忌口的套餐
    remaining = participant.calorie_budget
    set_meals = [
        it for it in catalog
        if it.is_set_meal
        and it.nutrition
        and it.nutrition.calories <= remaining
        and not any(t in it.tags for t in participant.avoid_tags)
    ]
    if participant.prefer_set_meal and set_meals:
        # 在预算内挑热量最低的套餐（减脂友好），剩余空间留给小食
        chosen = min(set_meals, key=lambda it: it.nutrition.calories)
        basket.append(chosen)
        remaining -= chosen.nutrition.calories

    # 预算内补充一杯饮品 + 一份低卡小食（如仍有空间）
    for it in catalog:
        if it in basket:
            continue
        if any(t in it.tags for t in participant.avoid_tags):
            continue
        if it.nutrition and it.nutrition.calories <= remaining:
            # 优先饮品，其次低卡小食
            if it.category == "饮品" or "低卡" in it.tags:
                basket.append(it)
                remaining -= it.nutrition.calories
        if remaining <= 0:
            break

    if not basket:
        warnings.append(
            f"{participant.name} 在 {participant.calorie_budget}kcal 预算内无可搭配餐品"
        )
    _check_calorie(basket, participant, warnings)
    return basket, warnings


def _check_calorie(basket: list[MenuItem], p: Participant, warnings: list[str]) -> None:
    total = sum((it.nutrition.calories if it.nutrition else 0.0) for it in basket)
    if total > p.calorie_budget + 1e-6:
        warnings.append(
            f"{p.name} 当前篮热量 {total:.0f}kcal 超过预算 {p.calorie_budget:.0f}kcal"
        )


def optimize(
    participants: list[Participant],
    catalog: list[MenuItem],
    coupons: list[Coupon],
    engine: PriceEngine,
) -> SplitPlan:
    """端到端优化：先按人配篮，再拆单挂券。"""
    groups: list[list[MenuItem]] = []
    for p in participants:
        basket, _warnings = build_basket(p, catalog, engine)
        groups.append(basket)

    plan = assign_coupons(groups, coupons, engine)
    # 最终合规校验
    for order in plan.orders:
        issues = order.validate_coupon()
        order.price = order.price  # 价格已由引擎计算
        if issues:
            # 若发现违规（理论上不应发生），记录但不静默
            setattr(order, "_issues", issues)
    return plan
