"""麦算盘演示（离线模式，无需 Token）。

使用 data/sample_data.py 的示例数据 + 本地价格引擎，跑通：
套餐组合 + 热量约束 + 多券拆单 + 价格计算。
真实环境把 LocalPriceEngine 换成 McpPriceEngine(client) 即可。
"""

import os
import sys

# 允许从任意目录运行本脚本（如 examples/ 目录下）：把项目根目录加入搜索路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcd_party_officer import (
    LocalPriceEngine,
    Participant,
    optimize,
)
from mcd_party_officer.data.sample_data import (
    ALL_ITEMS,
    SAMPLE_COUPONS,
    item_by_code,
)


def main() -> None:
    engine = LocalPriceEngine()

    participants = [
        Participant(pid="u1", name="小明", calorie_budget=1000, prefer_set_meal=True),
        Participant(pid="u2", name="小红", calorie_budget=900, prefer_set_meal=True,
                   avoid_tags=["辣"]),
        Participant(pid="u3", name="阿强", calorie_budget=1200, prefer_set_meal=False,
                   wanted_item_codes=["A5", "A2", "A3"]),
        # 想要派（买一送一特殊SKU）的人，用来触发 BOGO 券
        Participant(pid="u4", name="甜甜", calorie_budget=800,
                   wanted_item_codes=["B1", "A4"]),
    ]

    plan = optimize(participants, ALL_ITEMS, SAMPLE_COUPONS, engine)

    print("=" * 60)
    print("麦算盘 · 多人团餐最优配单结果（离线演示）")
    print("=" * 60)
    for o in plan.orders:
        coupon_name = o.coupon.name if o.coupon else "（无券）"
        items_str = " + ".join(it.name for it in o.items)
        price = o.price
        print(f"\n订单 #{o.order_index + 1}  [券: {coupon_name}]")
        print(f"  餐品: {items_str}")
        print(f"  热量: {o.calories:.0f} kcal")
        print(f"  小计: ¥{price.subtotal:.2f}  优惠: ¥{price.discount:.2f}  "
              f"应付: ¥{price.payable:.2f}")
        issues = o.validate_coupon()
        if issues:
            print("  ⚠️ 合规问题:", "; ".join(issues))

    print("\n" + "-" * 60)
    print(f"总应付: ¥{plan.total_payable:.2f}    总优惠: ¥{plan.total_discount:.2f}")
    print(f"总热量: {plan.total_calories:.0f} kcal    拆单张数: {len(plan.orders)}")
    print("-" * 60)


if __name__ == "__main__":
    main()
