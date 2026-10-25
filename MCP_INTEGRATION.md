# MCP_INTEGRATION.md — 麦当劳 MCP 集成说明

本文件说明 **mcd-party-officer（麦算盘）** 实际使用的麦当劳 MCP Server、调用的 Tool、
调用流程与业务价值。MCP 接入地址：`https://mcp.mcd.cn`，传输协议 **Streamable HTTP**，
鉴权：`Authorization: Bearer <MCP Token>`（Token 由 `open.mcd.cn/mcp` 手机号登录领取）。

---

## 一、本 Skill 使用的 MCP 工具（共调用 11 个）

| # | Tool 名称 | 作用 | 本项目的调用位置 |
| --- | --- | --- | --- |
| 1 | `now-time-info` | 获取当前时间 | 聚餐时间协调时确定默认档位 |
| 2 | `query-nearby-stores` | 查询附近可用门店 | 选门店 / 团餐前置 |
| 3 | `delivery-query-stores` | 查询可配送门店 | 外送场景选店 |
| 4 | `query-meals` | 查询当前可售餐品列表 | 拉取菜单（价格/分类/标签） |
| 5 | `query-meal-detail` | 查询餐品详情 / 套餐组成 | 解析套餐可替换项 |
| 6 | `list-nutrition-foods` | 餐品营养信息列表 | 减脂热量约束的数据来源 |
| 7 | `query-my-coupons` | 我的优惠券查询 | 读取用户可用券 |
| 8 | `query-store-coupons` | 当前门店可用券 | 门店级券校验 |
| 9 | `available-coupons` / `auto-bind-coupons` | 麦麦省券列表 / 一键领券 | 自动领券、扩充可用券池 |
| 10 | `calculate-price` | 商品价格计算 | **核心**：每单（含券）价格以它为准 |
| 11 | `create-order` | 创建订单 | 拆单后逐单下单，返回支付链接 |
| — | `query-order` / `order-list` / `cancel-order` | 订单查询/取消 | 下单后核验与售后（辅助） |

> 其余 22 个工具（麦麦商城、积分抽奖、主题活动派对等）不在本 Skill 主流程内使用，
> 但已随 MCP Server 一同开放，可扩展。完整 33 工具清单见官方仓库
> [M-China/mcd-mcp-server](https://github.com/M-China/mcd-mcp-server)。

---

## 二、调用流程（业务价值闭环）

```
┌──────────────────────── 多人聚餐时间协调 ────────────────────────┐
│ 1. 发起人提出时间档位 (now-time-info 取当前时间作默认)            │
│ 2. 参与者反馈有空/没空 (PartyTimeCoordinator)                     │
│ 3. 全员对某档位都有空 → 达成共识(confirmed)                       │
└───────────────────────────────┬──────────────────────────────────┘
                                 │ 确认时间 + 参与人
                                 ▼
┌──────────────────────── 麦算盘配单优化 ──────────────────────────┐
│ 4. query-nearby-stores / delivery-query-stores → 选门店          │
│ 5. query-meals + query-meal-detail → 拉菜单(价格/套餐组成)       │
│ 6. list-nutrition-foods → 营养(热量)数据                        │
│ 7. auto-bind-coupons → 一键领券；query-my-coupons/store-coupons  │
│    → 读取可用券                                                  │
│ 8. optimize(): 按每人热量预算搭配餐品(减脂约束)                  │
│ 9. assign_coupons(): 按「一单1券/套餐叠券/BOGO绑SKU」拆单        │
│ 10. calculate-price ×N → 每单(含券)价格，唯一事实来源            │
└───────────────────────────────┬──────────────────────────────────┘
                                 ▼
┌──────────────────────── 下单 ────────────────────────────────────┐
│ 11. create-order ×N (每单挂1券) → 返回订单详情与支付链接         │
│ 12. query-order / cancel-order → 核验与售后                      │
└──────────────────────────────────────────────────────────────────┘
```

---

## 三、关键约束的代码落地（避免踩坑）

1. **Token 不入库**：`client.py` 仅从环境变量 `MCD_MCP_TOKEN` 读取；配置用 `.env` + `.env.example`。
2. **一单 1 券**：`OrderPlan` 仅持有 0 或 1 个 `Coupon`；多券由 `split_order.assign_coupons` 拆成多张订单。
3. **套餐可叠 1 券**：`coupon_eligible()` 允许含套餐的订单挂券（如 8 折套餐券）。
4. **买一送一绑特殊 SKU**：`Coupon.bound_sku` + `MenuItem.special_sku`；仅当订单含对应特殊单品时 BOGO 才生效，普通单品无法触发；`split_order` 还做了「特殊 SKU 回收」——把无券订单里的特殊单品拆出单独成单挂 BOGO 券。
5. **价格以 MCP 为准**：`pricing.McpPriceEngine` 直接调用 `calculate-price`；离线测试用 `LocalPriceEngine`（仅复刻规则，非真实价格）。

---

## 四、业务价值

- **对用户**：把「协调时间 + 控制热量 + 比价用券 + 拆单」一步自动化，省时省钱、减脂可控。
- **对开发者**：提供一套**合规、可跑、可测**的麦当劳 MCP Skill 参考实现，规避所有官方列出的高频踩坑。
- **对赛事**：完整覆盖硬性文件清单（README / CONTEST_DECLARATION / MCP_INTEGRATION / 源码 / workbuddy.md），可直接提 Issue 报名。

---

## 五、错误码与限流处理

- `401`：Token 失效/未提供 → `McpAuthError`，提示重新申请。
- `429`：超过 600 次/分钟 → `McpRateLimitError`，提示降频。
- 客户端已在请求头携带 `Mcp-Session-Id`（initialize 握手后），并兼容 `application/json`
  与 `text/event-stream(SSE)` 两种返回。
