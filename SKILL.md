---
name: mcd-party-officer
description: >-
  基于麦当劳 MCP 的「多人聚餐时间协调 + 团餐最优配单」技能。当用户需要：
  组织多人麦当劳聚餐并协调时间、按减脂/热量预算搭配套餐、自动领券并用券最省钱、
  多人团餐比价拆单下单时使用。覆盖场景关键词：麦当劳、麦算盘、团餐、聚餐时间、
  热量控制、优惠券、拆单、MCP、WorkBuddy 点餐。
---

# 麦算盘 · mcd-party-officer

本技能连接 **麦当劳 MCP（open.mcd.cn/mcp）**，提供两大能力：

## 能力一：多人聚餐时间协调
- 发起人提出若干时间档位，参与者反馈「有空 / 没空」。
- 当**所有参与者对某档位都有空**时，聚餐自动达成共识。
- 实现：`mcd_party_officer.party_time.PartyTimeCoordinator`（状态持久化到 JSON）。

## 能力二：麦算盘团餐最优配单
- 为每位参与者在**热量预算**内搭配餐品（减脂约束）。
- 汇总后按 **「一单 1 券 / 套餐可叠券 / 买一送一绑特殊 SKU」** 规则拆单，最大化优惠。
- 价格、营养、优惠**一律以麦当劳 MCP 返回为准**（生产环境走 `calculate-price`）。

---

## 工作流（对话中按此顺序执行）

1. **确认聚餐时间**：调用 `now-time-info` 取当前时间；用 PartyTimeCoordinator 收集参与者反馈，直到达成共识。
2. **选门店**：`query-nearby-stores` 或 `delivery-query-stores`（外送）。
3. **拉菜单与营养**：`query-meals` + `query-meal-detail` 取餐品与价格；`list-nutrition-foods` 取热量。
4. **领券 / 读券**：`auto-bind-coupons` 一键领券；`query-my-coupons` / `query-store-coupons` 读取可用券。
5. **优化配单**：运行 `optimize(participants, catalog, coupons, engine)`，按热量约束 + 拆单规则生成 `SplitPlan`。
6. **算价（事实来源）**：对每张拆单调用 `calculate-price`（MCP）得到应付。
7. **下单**：逐单 `create-order`（每单挂 1 券），返回支付链接；必要时 `query-order` / `cancel-order`。

---

## 调用麦当劳 MCP 工具清单（已验证）
`now-time-info` · `query-nearby-stores` · `delivery-query-stores` · `query-meals` ·
`query-meal-detail` · `list-nutrition-foods` · `auto-bind-coupons` · `query-my-coupons` ·
`query-store-coupons` · `calculate-price` · `create-order` · `query-order` / `cancel-order`

---

## ⚠️ 高频踩坑（务必遵守）
- **Token 绝不入库**：仅从环境变量 `MCD_MCP_TOKEN` 读取；配置文件用 `.env`（已被忽略）。
- **一单仅可挂 1 张券**：多券必须拆成多张订单。
- **套餐可叠 1 张券**：含套餐的订单可正常挂券。
- **买一送一券绑特殊 SKU**：只有订单含对应特殊单品才生效，普通单品无法触发。
- **价格不让大模型估算**：统一调用 `calculate-price`，不在代码里写死价格。

---

## 本地运行（无 Token 也可演示）
```bash
export PYTHONPATH=$PWD
python examples/demo_party_time.py   # 聚餐时间协调
python examples/demo_optimizer.py    # 麦算盘配单（示例数据）
python -m unittest discover -s tests -t .
```
接入 WorkBuddy 连接器 `mcd-mcp` 后，用户直接用自然语言描述需求即可触发上述流程。
