"""麦算盘 · 实时版 demo（真实调用麦当劳 MCP，需要有效 Token）。

运行前：在项目根目录 .env 中填入 MCD_MCP_TOKEN（或设置同名环境变量）。
    python examples/demo_mcp_live.py                       # 只读：验证Token + 查看菜单/营养/券
    python examples/demo_mcp_live.py --optimize            # 用真实数据 + 真实价格跑配单
    python examples/demo_mcp_live.py --optimize --store-code 123456 --city 上海   # 指定门店/城市

⚠️ 默认不会创建任何订单；--submit 会真实下单（可能产生费用），请谨慎。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# 允许直接 `python examples/demo_mcp_live.py` 运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcd_party_officer import McpAuthError, McpClient, McpRateLimitError
from mcd_party_officer.config import load_dotenv


def show(title: str, obj, maxlen: int = 900) -> None:
    text = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, indent=2)
    if len(text) > maxlen:
        text = text[:maxlen] + " ……（已截断）"
    print(f"\n### {title}\n{text}")


def safe_call(client: McpClient, name: str, args: dict | None = None):
    try:
        result = client.call_tool(name, args or {})
        show(f"{name} 原始返回", result)
        return result
    except (McpAuthError, McpRateLimitError) as e:
        print(f"\n### {name} 失败：{e}")
    except Exception as e:  # noqa: BLE001
        print(f"\n### {name} 调用异常：{type(e).__name__}: {e}")
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="麦算盘实时 demo")
    parser.add_argument("--optimize", action="store_true", help="用真实数据/价格跑一次配单")
    parser.add_argument("--submit", action="store_true", help="真实下单（默认关闭，谨慎）")
    parser.add_argument("--address", default="", help="外送地址（--submit 外送时需要）")
    parser.add_argument("--store-code", default="", help="门店编码 storeCode")
    parser.add_argument("--city", default="", help="城市（用于查询门店/菜单）")
    parser.add_argument("--order-type", type=int, default=1, help="1 到店 / 2 外送")
    parser.add_argument("--be-type", type=int, default=1, help="1 到店自提 / 5 得来速 / 6 团餐")
    args = parser.parse_args()

    # 1) 加载 .env
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    loaded = load_dotenv(os.path.join(root, ".env"))
    token = os.environ.get("MCD_MCP_TOKEN", "")
    if loaded:
        print(f"已加载 .env（{os.path.join(root, '.env')}）")
    if not token or "粘贴" in token or token == "YOUR_MCP_TOKEN_HERE":
        print(
            "\n❌ 未检测到有效 MCD_MCP_TOKEN。\n"
            "请在 .env 中把 MCD_MCP_TOKEN= 后面换成你申请到的真实 Token，"
            "或在终端设置环境变量后重试。切勿把 Token 贴进对话或提交到 GitHub。"
        )
        sys.exit(1)

    # 2) 连接 + 列出工具（验证 Token 是否有效）
    client = McpClient()
    try:
        client.connect()
    except McpAuthError as e:
        print(f"❌ Token 无效/未提供：{e}")
        sys.exit(1)
    except McpRateLimitError as e:
        print(f"⚠️ 触发限流：{e}")
        sys.exit(1)

    tools = client.list_tools()
    names = [t.get("name") for t in tools]
    print(f"\n✅ 连接成功，共 {len(names)} 个工具：")
    print("、".join(n for n in names if n))

    # 3) 逐条查看关键数据（原始返回，便于核对字段结构）
    safe_call(client, "now-time-info")
    safe_call(client, "list-nutrition-foods")
    safe_call(client, "query-my-coupons")
    meals_args: dict = {"orderType": args.order_type, "beType": args.be_type}
    if args.store_code:
        meals_args["storeCode"] = args.store_code
    safe_call(client, "query-meals", meals_args)

    # 4) 可选：用真实数据 + 真实价格跑一次配单
    if args.optimize:
        from mcd_party_officer import McpPriceEngine, Participant, optimize
        from mcd_party_officer import menu as menu_api

        print("\n===== 用真实数据跑配单 =====")
        # 门店：未提供则尝试按城市自动找店
        store_code = args.store_code
        if not store_code and args.city:
            stores = menu_api.fetch_nearby_stores(client, args.be_type, city=args.city)
            if stores:
                store_code = str(stores[0].get("storeCode") or stores[0].get("code") or "")
                print(f"自动选用门店：{stores[0].get('storeName', '')} (storeCode={store_code})")
        if not store_code:
            print("⚠️ 未获得 storeCode。菜单/算价/下单都需要门店编码。\n"
                  "   推荐：用 --store-code 直接指定（可先从麦当劳 App 或接入 MCP 的对话里\n"
                  "   『查一下我附近的门店』拿到 storeCode）。\n"
                  "   注意：query-nearby-stores 的 searchType=2 按位置搜索，仅给城市名可能被拒。")

        catalog = menu_api.fetch_menu(client, store_code or None, args.order_type, args.be_type)
        nutrition = menu_api.fetch_nutrition(client)
        hit = menu_api.attach_nutrition(catalog, nutrition)
        print(f"解析到菜单 {len(catalog)} 项（其中 {hit} 项挂上营养）；"
              f"营养表 {len(nutrition)} 条")

        try:
            menu_api.auto_bind_coupons(client)
        except Exception as e:  # noqa: BLE001
            print(f"（一键领券跳过：{e}）")

        if store_code:
            coupons = menu_api.fetch_store_coupons(
                client, store_code, args.order_type, args.be_type
            )
            print(f"门店可用券 {len(coupons)} 张")
        else:
            coupons = menu_api.fetch_my_coupons(client)
            print(f"卡包券 {len(coupons)} 张（卡包展示，可能无券ID，仅作演示）")

        # 用真实菜单自动选餐（不写死编码）
        participants = [Participant(pid="me", name="我", calorie_budget=1000, prefer_set_meal=True)]
        engine = McpPriceEngine(client, store_code or None, args.order_type, args.be_type)

        # 校准：打印一条 calculate-price 原始返回
        sample = next((it for it in catalog if it.is_set_meal), None) or (catalog[0] if catalog else None)
        if sample:
            print(f"\n### calculate-price 原始返回（样例餐品：{sample.name}）")
            show("calculate-price", client.call_tool(
                "calculate-price",
                {"items": [{"code": sample.code, "quantity": 1}],
                 "orderType": args.order_type, "beType": args.be_type,
                 **({"storeCode": store_code} if store_code else {})},
            ))

        try:
            plan = optimize(participants, catalog, coupons, engine)
            for o in plan.orders:
                name = o.coupon.name if o.coupon else "（无券）"
                price = o.price
                print(
                    f"订单#{o.order_index + 1} [{name}] "
                    f"餐品:{[it.name for it in o.items]} "
                    f"热量:{o.calories:.0f}kcal "
                    f"小计:¥{price.subtotal:.2f} 优惠:¥{price.discount:.2f} 应付:¥{price.payable:.2f}"
                )
            print(f"总应付:¥{plan.total_payable:.2f} 总优惠:¥{plan.total_discount:.2f}")
            print("\n💡 若价格/优惠对不上，多半是字段映射——把各工具『原始返回』JSON 发我（不含 Token）来校准。")
        except Exception as e:  # noqa: BLE001
            print(f"配单失败：{type(e).__name__}: {e}")

    # 5) 可选：真实下单（默认不执行）
    if args.submit:
        print("\n⚠️⚠️ 你选择了真实下单，即将创建麦当劳订单（可能产生费用）！")
        if args.order_type == 2 and not args.address:
            print("外送下单需要 --address，已中止。")
            sys.exit(1)
        print("演示出于安全未自动下单；如需接入，请基于 mcd_party_officer.order.submit_split_plan 扩展。")


if __name__ == "__main__":
    main()
