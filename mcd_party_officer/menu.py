"""麦当劳 MCP 业务适配层：把 MCP 工具返回解析为本地模型。

已按**真实返回结构**校准（2026-10-25 实测）：
- 结果常被包成 Markdown，真 JSON 在 `## Original Response` 之后（client.extract_json 负责抽取）。
- query-meals：`data.categories[].meals[].code/tags` + `data.meals[code] -> {name,currentPrice,...}`。
- list-nutrition-foods：`data` 是一段自定义分隔字符串 `[N]{列名}:` + 逗号分隔行。
- query-my-coupons：Markdown 文本（卡包展示，通常不含 couponId，不能直接下单用）。
- query-store-coupons：按门店/订单类型的**可用券**（可能含 couponId/couponCode），下单前应以此为准。
"""

from __future__ import annotations

import re
from typing import Any, Optional

from .client import McpClient
from .models import Coupon, CouponType, MenuItem, NutritionInfo

_NUTRI_COLS = [
    "productName", "nutritionDescription", "energyKj", "energyKcal",
    "protein", "fat", "carbohydrate", "sodium", "calcium",
]


def _to_float(v: Any) -> float:
    try:
        if v is None:
            return 0.0
        s = str(v).strip()
        if s in ("", "null", "None"):
            return 0.0
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def _inner(data: Optional[dict]) -> Any:
    if not data:
        return {}
    inner = data.get("data", data)
    return inner if isinstance(inner, (dict, list)) else data


# -------------------- 菜单 --------------------

def fetch_menu(
    client: McpClient,
    store_code: Optional[str] = None,
    order_type: int = 1,
    be_type: int = 1,
) -> list[MenuItem]:
    """拉取餐品列表（含价格）。到店自提默认 order_type=1, be_type=1。"""
    args: dict[str, Any] = {"orderType": order_type, "beType": be_type}
    if store_code:
        args["storeCode"] = store_code
    data = client.call_json("query-meals", args) or {}
    d = _inner(data)
    cats = d.get("categories", []) or []
    meals_map = d.get("meals", {}) or {}

    items: list[MenuItem] = []
    for cat in cats:
        cname = str(cat.get("name", ""))
        for m in cat.get("meals", []) or []:
            code = m.get("code")
            if not code:
                continue
            detail = meals_map.get(code, {}) if isinstance(meals_map, dict) else {}
            name = str(detail.get("name") or m.get("name") or "")
            price = detail.get("currentPrice") or detail.get("originalPrice") or m.get("currentPrice") or 0
            is_set = ("套餐" in cname) or ("套餐" in name) or bool(detail.get("setMeal"))
            items.append(
                MenuItem(
                    code=str(code),
                    name=name,
                    category=cname,
                    price=_to_float(price),
                    is_set_meal=bool(is_set),
                    tags=list(m.get("tags") or detail.get("tags") or []),
                )
            )
    return items


# -------------------- 营养 --------------------

def fetch_nutrition(client: McpClient) -> dict[str, NutritionInfo]:
    """返回 {餐品名称: NutritionInfo}。data 为自定义分隔字符串，需专用解析。"""
    data = client.call_json("list-nutrition-foods", {}) or {}
    s = data.get("data")
    if not isinstance(s, str):
        return {}
    m = re.search(r"\{([^}]*)\}", s)
    cols = [c.strip() for c in m.group(1).split(",")] if m else _NUTRI_COLS
    body = s.split(":", 1)[1] if ":" in s else s
    out: dict[str, NutritionInfo] = {}
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        rec = dict(zip(cols, parts))
        name = rec.get("productName", "")
        if not name:
            continue
        out[name] = NutritionInfo(
            calories=_to_float(rec.get("energyKcal")),
            protein=_to_float(rec.get("protein")),
            fat=_to_float(rec.get("fat")),
            carbohydrate=_to_float(rec.get("carbohydrate")),
            sodium=_to_float(rec.get("sodium")),
            calcium=_to_float(rec.get("calcium")),
        )
    return out


def attach_nutrition(
    items: list[MenuItem], nutrition_by_name: dict[str, NutritionInfo]
) -> int:
    """把营养按『餐品名称』挂到菜单项上，返回成功挂上的数量。"""
    hit = 0
    for it in items:
        if it.name in nutrition_by_name:
            it.nutrition = nutrition_by_name[it.name]
            hit += 1
    return hit


# -------------------- 优惠券 --------------------

def _guess_type(name: str, raw: dict) -> CouponType:
    text = f"{name} {raw.get('couponType', '')} {raw.get('type', '')}".lower()
    if "bogo" in text or "买一送一" in text or "赠" in text:
        return CouponType.BOGO
    if "折" in text or "percent" in text:
        return CouponType.PERCENT
    return CouponType.THRESHOLD


def _parse_coupon_obj(c: dict) -> Optional[Coupon]:
    name = str(c.get("couponName") or c.get("name") or c.get("title") or "")
    cid = str(c.get("couponId") or c.get("id") or c.get("couponCode") or "")
    if not name and not cid:
        return None
    value = c.get("couponAmount") or c.get("value") or c.get("discountAmount") or 0
    min_amt = c.get("minOrderAmount") or c.get("threshold") or c.get("minAmount") or 0
    return Coupon(
        coupon_id=cid,
        name=name,
        coupon_type=_guess_type(name, c),
        value=_to_float(value),
        ratio=_to_float(c.get("ratio")) or 1.0,
        min_order_amount=_to_float(min_amt),
        bound_sku=c.get("boundSku") or c.get("sku") or c.get("couponCode") or None,
        setmeal_only=("套餐" in name) or bool(c.get("setmealOnly")),
    )


def fetch_store_coupons(
    client: McpClient,
    store_code: str,
    order_type: int = 1,
    be_type: int = 1,
    be_code: Optional[str] = None,
) -> list[Coupon]:
    """查询【门店+订单类型】下可用券（下单前以此为准）。"""
    args: dict[str, Any] = {"orderType": order_type, "beType": be_type, "storeCode": store_code}
    if be_code:
        args["beCode"] = be_code
    data = client.call_json("query-store-coupons", args) or {}
    d = _inner(data)
    rows = d.get("coupons") or d.get("data") or d.get("list") or []
    coupons: list[Coupon] = []
    for c in rows if isinstance(rows, list) else []:
        obj = _parse_coupon_obj(c) if isinstance(c, dict) else None
        if obj:
            coupons.append(obj)
    return coupons


def parse_my_coupons_markdown(text: str) -> list[Coupon]:
    """把 query-my-coupons 的 Markdown 文本尽力解析为券（多为展示用，可能无 ID）。"""
    coupons: list[Coupon] = []
    cur_name = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("## "):
            cur_name = line[3:].strip()
        elif line.startswith("- **优惠**") and cur_name:
            mval = re.search(r"¥\s*([0-9.]+)", line)
            value = _to_float(mval.group(1)) if mval else 0.0
            coupons.append(
                Coupon(
                    coupon_id="",  # 卡包展示通常不含 couponId
                    name=cur_name,
                    coupon_type=_guess_type(cur_name, {}),
                    value=value,
                )
            )
            cur_name = None
    return coupons


def fetch_my_coupons(client: McpClient) -> list[Coupon]:
    """查询卡包券（Markdown）。注意：不含下单可用性校验，可能无券 ID。"""
    text = client.call_text("query-my-coupons", {})
    return parse_my_coupons_markdown(text)


def auto_bind_coupons(client: McpClient) -> dict:
    """麦麦省一键领券（无参数）。"""
    data = client.call_json("auto-bind-coupons", {})
    return data or {}


def fetch_nearby_stores(
    client: McpClient, be_type: int = 1, city: str = "", keyword: str = ""
) -> list[dict]:
    """查询可点餐门店。be_type=1 到店自提 / 5 得来速。"""
    args: dict[str, Any] = {"beType": be_type, "searchType": 2}
    if city:
        args["city"] = city
    if keyword:
        args["keyword"] = keyword
    data = client.call_json("query-nearby-stores", args) or {}
    d = _inner(data)
    return d.get("stores") or d.get("data") or (d if isinstance(d, list) else [])
