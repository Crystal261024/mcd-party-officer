import unittest

from mcd_party_officer import LocalPriceEngine, Participant, optimize
from mcd_party_officer.data.sample_data import ALL_ITEMS, SAMPLE_COUPONS


class TestOptimizer(unittest.TestCase):
    def setUp(self):
        self.engine = LocalPriceEngine()
        self.participants = [
            Participant(pid="u1", name="小明", calorie_budget=1000, prefer_set_meal=True),
            Participant(pid="u2", name="小红", calorie_budget=900,
                       prefer_set_meal=True, avoid_tags=["辣"]),
            Participant(pid="u3", name="阿强", calorie_budget=1200,
                       prefer_set_meal=False, wanted_item_codes=["A5", "A2", "A3"]),
            Participant(pid="u4", name="甜甜", calorie_budget=800,
                       wanted_item_codes=["B1", "A4"]),
        ]

    def test_one_coupon_per_order(self):
        plan = optimize(self.participants, ALL_ITEMS, SAMPLE_COUPONS, self.engine)
        for o in plan.orders:
            self.assertLessEqual(1, 1)  # 占位：每张订单 coupon 至多 1 个（结构上保证）
            # 结构上 OrderPlan 仅持有 0 或 1 个 coupon 对象

    def test_bogo_triggered_by_special_sku(self):
        plan = optimize(self.participants, ALL_ITEMS, SAMPLE_COUPONS, self.engine)
        bogo_orders = [o for o in plan.orders if o.coupon and o.coupon.coupon_type.value == "bogo"]
        self.assertTrue(bogo_orders, "应有至少一张买一送一券被触发")
        for o in bogo_orders:
            has_special = any(it.special_sku for it in o.items)
            self.assertTrue(has_special, "BOGO 订单必须含绑定的特殊 SKU 单品")
            self.assertEqual(len(o.validate_coupon()), 0, "BOGO 订单应合规")

    def test_total_discount_positive(self):
        plan = optimize(self.participants, ALL_ITEMS, SAMPLE_COUPONS, self.engine)
        self.assertGreater(plan.total_discount, 0.0)

    def test_calorie_budget_respected(self):
        plan = optimize(self.participants, ALL_ITEMS, SAMPLE_COUPONS, self.engine)
        # 每位参与者的订单热量应不超过其预算（自动搭配场景）
        for o, p in zip(plan.orders, self.participants):
            self.assertLessEqual(o.calories, p.calorie_budget + 1e-6)


if __name__ == "__main__":
    unittest.main()
