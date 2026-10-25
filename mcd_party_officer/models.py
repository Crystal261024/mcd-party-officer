"""数据模型定义。

所有与麦当劳相关的实体（餐品、优惠券、营养、订单、聚餐会话）都在此集中定义。
注意：价格、营养、优惠等"事实数据"一律来自 MCP 接口返回，模型只负责承载，
绝不在此处臆造价格或营养数值。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CouponType(str, Enum):
    """优惠券类型。

    踩坑提醒：
    - 买一送一(BOGO) 类券绑定「特殊 SKU」，不是普通单品；直接点普通商品无法使用。
    - 满减 / 折扣券通常要求订单达到最低消费门槛。
    """

    THRESHOLD = "threshold"      # 满减：订单满 min_order_amount 减 value
    PERCENT = "percent"          # 折扣：按 ratio 打折
    BOGO = "bogo"                # 买一送一：必须包含绑定的 bound_sku 特殊单品
    SETMEAL = "setmeal"          # 套餐专属券：仅对套餐生效（可与套餐叠加）


@dataclass
class NutritionInfo:
    """营养成分。数值以 list-nutrition-foods 接口返回为准。"""

    calories: float = 0.0       # 能量 kcal
    protein: float = 0.0        # 蛋白质 g
    fat: float = 0.0            # 脂肪 g
    carbohydrate: float = 0.0   # 碳水化合物 g
    sodium: float = 0.0         # 钠 mg
    calcium: float = 0.0        # 钙 mg

    def __add__(self, other: "NutritionInfo") -> "NutritionInfo":
        return NutritionInfo(
            calories=self.calories + other.calories,
            protein=self.protein + other.protein,
            fat=self.fat + other.fat,
            carbohydrate=self.carbohydrate + other.carbohydrate,
            sodium=self.sodium + other.sodium,
            calcium=self.calcium + other.calcium,
        )


@dataclass
class MenuItem:
    """餐品 / 套餐项。

    price 与 nutrition 均由 MCP 接口（query-meals / query-meal-detail /
    list-nutrition-foods）返回，本模型仅为承载容器。
    """

    code: str
    name: str
    category: str = ""
    price: float = 0.0
    is_set_meal: bool = False
    tags: list[str] = field(default_factory=list)
    nutrition: Optional[NutritionInfo] = None
    # 是否为「买一送一」等特殊券绑定的特殊 SKU（普通单品为 None）
    special_sku: Optional[str] = None


@dataclass
class Coupon:
    """优惠券。

    约束规则（来自官方踩坑提醒）：
    1. 一单仅可挂载 1 张优惠券。
    2. 套餐可以和 1 张券叠加。
    3. 买一送一(BOGO) 券绑定特殊 SKU，普通单品无法触发。
    """

    coupon_id: str
    name: str
    coupon_type: CouponType
    # 满减金额 / 折扣后减免额（元）
    value: float = 0.0
    # 折扣比例（0~1，仅 PERCENT 使用），例如 0.8 表示 8 折
    ratio: float = 1.0
    # 满减门槛（元），订单实付（或原价）需达到
    min_order_amount: float = 0.0
    # BOGO 绑定的特殊 SKU 编码（仅 BOGO 使用）
    bound_sku: Optional[str] = None
    # 是否仅对套餐生效（可与套餐叠加）
    setmeal_only: bool = False


@dataclass
class Participant:
    """聚餐参与者及其点餐偏好。"""

    pid: str
    name: str
    # 该参与者的热量预算上限（减脂约束），单位 kcal
    calorie_budget: float = 2000.0
    # 期望的餐品编码（可为空，由优化器在预算内自由搭配）
    wanted_item_codes: list[str] = field(default_factory=list)
    # 偏好：是否必须含套餐
    prefer_set_meal: bool = True
    # 忌口标签（如 "no_spicy"），优化器会避开带该标签的餐品
    avoid_tags: list[str] = field(default_factory=list)


@dataclass
class TimeSlot:
    """聚餐时间候选档位。"""

    slot_id: str
    label: str          # 例如 "周五 18:30"
    start: str          # ISO 时间字符串
    end: str


@dataclass
class Availability:
    """某参与者对一组时间档位的反馈：slot_id -> 是否可参加。"""

    pid: str
    name: str
    responses: dict[str, bool] = field(default_factory=dict)


@dataclass
class PartySession:
    """多人聚餐时间协调会话。

    发起人提出若干时间档位，参与者逐一反馈有空 / 没空；
    当所有参与者对某个档位都有空时，该聚餐即「达成共识」。
    """

    session_id: str
    initiator: str
    title: str
    slots: list[TimeSlot] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)   # pid 列表
    availabilities: list[Availability] = field(default_factory=list)
    confirmed_slot: Optional[str] = None
    status: str = "collecting"   # collecting | confirmed | cancelled


@dataclass
class PriceBreakdown:
    """一次 calculate-price 的返回结果（事实数据，来自 MCP）。"""

    subtotal: float = 0.0        # 商品原价合计
    delivery_fee: float = 0.0    # 配送费
    discount: float = 0.0        # 优惠金额
    payable: float = 0.0         # 应付总价


@dataclass
class OrderPlan:
    """一张（拆单后的）订单方案。"""

    order_index: int
    items: list[MenuItem] = field(default_factory=list)
    coupon: Optional[Coupon] = None
    price: Optional[PriceBreakdown] = None

    @property
    def calories(self) -> float:
        return sum((it.nutrition.calories if it.nutrition else 0.0) for it in self.items)

    def validate_coupon(self) -> list[str]:
        """校验本订单挂载的优惠券是否合规，返回违规说明列表。"""
        issues: list[str] = []
        if self.coupon is None:
            return issues
        c = self.coupon
        # 规则1：一单至多1券（OrderPlan 仅持有1个 coupon 对象，天然满足；此处校验金额门槛）
        if self.price and self.price.subtotal < c.min_order_amount:
            issues.append(
                f"优惠券[{c.name}]要求最低消费 ¥{c.min_order_amount}，"
                f"当前小计 ¥{self.price.subtotal:.2f} 未达门槛"
            )
        if c.setmeal_only and not any(it.is_set_meal for it in self.items):
            issues.append(f"优惠券[{c.name}]仅对套餐生效，本单无套餐")
        if c.coupon_type == CouponType.BOGO:
            sku = c.bound_sku
            if not sku or not any(it.special_sku == sku for it in self.items):
                issues.append(
                    f"买一送一券[{c.name}]需绑定特殊 SKU[{sku}]，"
                    f"本单无对应特殊单品（普通单品不可触发）"
                )
        return issues


@dataclass
class SplitPlan:
    """多人团餐的最终拆单方案。"""

    orders: list[OrderPlan] = field(default_factory=list)

    @property
    def total_payable(self) -> float:
        return sum(o.price.payable for o in self.orders if o.price)

    @property
    def total_discount(self) -> float:
        return sum(o.price.discount for o in self.orders if o.price)

    @property
    def total_calories(self) -> float:
        return sum(o.calories for o in self.orders)
