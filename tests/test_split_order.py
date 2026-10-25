import unittest

from mcd_party_officer import LocalPriceEngine, assign_coupons, coupon_eligible
from mcd_party_officer.data.sample_data import (
    ALL_ITEMS,
    SAMPLE_COUPONS,
    item_by_code,
)


class TestSplitOrder(unittest.TestCase):
    def setUp(self):
        self.engine = LocalPriceEngine()

    def test_bogo_not_triggered_by_ordinary_item(self):
        # 普通单品（无特殊SKU）不能触发买一送一券
        ordinary = [item_by_code("A1"), item_by_code("A3")]
        bogo = next(c for c in SAMPLE_COUPONS if c.coupon_type.value == "bogo")
        self.assertFalse(coupon_eligible(ordinary, bogo))

    def test_bogo_triggered_by_special_sku(self):
        special = [item_by_code("B1")]
        bogo = next(c for c in SAMPLE_COUPONS if c.coupon_type.value == "bogo")
        self.assertTrue(coupon_eligible(special, bogo))

    def test_threshold_min_spend(self):
        small = [item_by_code("A4")]  # ¥10
        big = [item_by_code("M1")]    # ¥42.5
        c1 = next(c for c in SAMPLE_COUPONS if c.coupon_id == "C1")  # 满40减6
        self.assertFalse(coupon_eligible(small, c1))
        self.assertTrue(coupon_eligible(big, c1))

    def test_setmeal_only_coupon(self):
        no_meal = [item_by_code("A1"), item_by_code("A3")]
        with_meal = [item_by_code("M1")]
        c2 = next(c for c in SAMPLE_COUPONS if c.coupon_id == "C2")  # 套餐8折
        self.assertFalse(coupon_eligible(no_meal, c2))
        self.assertTrue(coupon_eligible(with_meal, c2))

    def test_assign_uses_one_coupon_per_order(self):
        groups = [
            [item_by_code("M1"), item_by_code("A3")],   # 可触发满减/套餐券
            [item_by_code("B1")],                        # 可触发 BOGO
        ]
        plan = assign_coupons(groups, SAMPLE_COUPONS, self.engine)
        used = [o.coupon.coupon_id for o in plan.orders if o.coupon]
        self.assertEqual(len(used), len(set(used)), "每张券至多使用一次")


if __name__ == "__main__":
    unittest.main()
