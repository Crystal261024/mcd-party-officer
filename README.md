# 🍔 麦算盘 · mcd-party-officer

> 基于 **麦当劳 MCP（open.mcd.cn/mcp）** 的「多人聚餐时间协调 + 团餐最优配单」开源 Skill。
> 自动组合套餐与优惠券、按减脂热量约束配单、多人团餐一键比价拆单下单。

本项目为 **麦当劳程序员节创意开发大赛（M-CODE / mcd-developer-innovation-challenge）** 参赛作品。

---

## ✨ 它能做什么

1. **多人聚餐时间协调（多人聚餐时间 Skill）**
   - 发起人提出若干时间档位 → 参与者逐一反馈「有空 / 没空」。
   - 当**所有参与者对某个档位都有空**时，聚餐自动达成共识（confirmed），并持久化到本地 JSON。
   - 达成共识后，即可把确认时间交给麦算盘去做配单下单。

2. **麦算盘优化器（团餐最优配单）**
   - 为每位参与者在**热量预算（减脂约束）**内搭配餐品。
   - 汇总多人点餐后，按 **「一单 1 券 / 套餐可叠券 / 买一送一绑特殊 SKU」** 规则做最优拆单，最大化优惠。
   - 价格、营养、优惠**一律以麦当劳 MCP 接口返回为准**，不自行估算。

---

## 🎯 目标用户

| 用户 | 场景 |
| --- | --- |
| 健身 / 减脂人群 | 想控制热量又想用券省钱 |
| 团建 / 聚餐组织者 | 协调时间 + 多人均摊最优配单 |
| 省钱党 | 自动领券、比价、拆单叠加优惠 |
| 开发者 / 学生 | 学习 MCP + WorkBuddy Skill 开发的参考实现 |

---

## 🚀 快速开始

### 1. 获取麦当劳 MCP Token
1. 打开 [open.mcd.cn/mcp](https://open.mcd.cn/mcp)，右上角【登录】→ 手机号验证登录。
2. 点击右上角【控制台】→【激活】→ 同意协议 → 一键复制 **MCP Token**。

### 2. 配置 Token（⚠️ 绝不提交到 GitHub）
```bash
cp .env.example .env
# 编辑 .env，填入：MCD_MCP_TOKEN=你的真实Token
```

### 3. 安装与运行（仅用标准库，无需第三方依赖）
```bash
cd mcd-party-officer
export PYTHONPATH=$PWD        # 或直接 pip install -e .

# 离线演示（无需 Token，使用示例数据）
python examples/demo_optimizer.py     # 麦算盘配单演示
python examples/demo_party_time.py    # 聚餐时间协调演示

# 单元测试
python -m unittest discover -s tests -t .

# 或者一键测试（自动跑 单元测试 + 离线演示，路径含中文也没关系）
python run.py
```

### 3.5 用真实 Token 跑实时 demo（调用真实 MCP）
1. 编辑项目根目录 `.env`（由 `.env.example` 复制而来），把 `MCD_MCP_TOKEN=` 后面换成你申请到的真实 Token：
   ```env
   MCD_MCP_TOKEN=你的真实Token
   ```
   > `.env` 已被 `.gitignore` 忽略，不会提交；**切勿**把 Token 贴进对话或提交到 GitHub。
   > 也可以用环境变量代替：Git Bash `export MCD_MCP_TOKEN=xxx`；PowerShell `$env:MCD_MCP_TOKEN="xxx"`。
2. 运行实时 demo：
   ```bash
   python examples/demo_mcp_live.py            # 验证Token + 查看菜单/营养/券原始返回
   python examples/demo_mcp_live.py --optimize # 用真实价格跑一次配单
   ```
   实时 demo 会先连接 MCP 并列出工具证明 Token 有效，再打印各工具原始返回，最后用
   `McpPriceEngine`（真实 `calculate-price`）试算。**默认不会创建订单**；如需下单请自行
   基于 `mcd_party_officer.order.submit_split_plan` 扩展，并三思（会产生真实订单）。

> **真实接口注意事项（2026-10-25 实测校准）**
> - 返回常被包成 Markdown，真 JSON 或在 `## Original Response` 之后、或**内嵌在指令文本中**；`client.extract_json` 已做稳健抽取。
> - `list-nutrition-foods` 的 `data` 是自定义分隔字符串（`[N]{productName,...,energyKcal,...}:`+逗号行），已专用解析，实测 158 条。
> - `query-my-coupons` 返回 Markdown（卡包展示，通常**无券 ID**）；下单可用券应以 `query-store-coupons`（按门店）为准。
> - **菜单/算价/下单都需要 `storeCode`**（外加 `orderType`/`beType`）。用 `--store-code` 指定；`query-nearby-stores` 的 `searchType=2` 按位置搜索，仅给城市名可能被拒，可先从 App/对话里拿到门店编码。
> - `calculate-price`/`create-order` 的优惠券挂在 **item 级**（`couponId`/`couponCode`）。

### 4. 接入 WorkBuddy（推荐）
在 WorkBuddy 左侧【连接器】→【自定义连接器】→【配置 MCP】，填入：
```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": { "Authorization": "Bearer 你的Token" }
    }
  }
}
```
启用后，直接在对话框说「帮我组织周五团建点麦当劳，控制热量还要用券最省钱」即可。

---

## 🧩 使用示例（Python API）

### 多人聚餐时间协调
```python
from mcd_party_officer import PartyTimeCoordinator, TimeSlot

coord = PartyTimeCoordinator()
slots = [TimeSlot("s1", "周五 18:30", "2026-10-30T18:30", "2026-10-30T20:00")]
coord.new_session("party1", "沙", "周末团建", slots)
coord.join("party1", "m", "小明")
coord.respond("party1", "m", {"s1": True})   # 反馈有空
print(coord.summary("party1"))
```

### 麦算盘配单（生产环境用 McpPriceEngine）
```python
from mcd_party_officer import Participant, LocalPriceEngine, optimize
from mcd_party_officer.data.sample_data import ALL_ITEMS, SAMPLE_COUPONS

plan = optimize(
    [Participant(pid="u1", name="小明", calorie_budget=1000)],
    ALL_ITEMS, SAMPLE_COUPONS, LocalPriceEngine(),
)
for o in plan.orders:
    print(o.coupon.name if o.coupon else "无券", o.price.payable)
```

---

## 🛡️ 高频踩坑规避（已内置防护）

| 踩坑点 | 本项目做法 |
| --- | --- |
| Token 明文提交 GitHub | Token 仅从环境变量 `MCD_MCP_TOKEN` 读取；`.env` 已被 `.gitignore` 忽略；`CONTEST_DECLARATION.md` 信息安全声明一致 |
| 一单仅可挂 1 张券 | `OrderPlan` 结构上至多持有 1 个 `coupon`；多券自动拆成多张订单 |
| 套餐可叠 1 张券 | `coupon_eligible` 允许含套餐订单正常挂券 |
| 买一送一券绑特殊 SKU | BOGO 券仅在订单含对应 `special_sku` 单品时触发，普通单品无法使用 |
| 大模型自行估算价格 | 价格统一走 `PriceEngine`；生产环境 = MCP `calculate-price`，绝不在代码里写死价格 |

---

## 📁 目录结构
```
mcd-party-officer/
├── README.md                # 项目介绍/教程/目标用户
├── CONTEST_DECLARATION.md   # 官方固定参赛声明（不可修改）
├── MCP_INTEGRATION.md       # MCP 接口调用说明
├── workbuddy.md             # WorkBuddy 联动奖励用对话上下文
├── SKILL.md                 # WorkBuddy 技能定义
├── ISSUE_TEMPLATE.md        # GitHub Issue 报名模板
├── pyproject.toml
├── requirements.txt
├── .env.example             # Token 占位（绝不提交真实 Token）
├── mcd_party_officer/
│   ├── client.py            # MCP Streamable HTTP 客户端（Token 走环境变量）
│   ├── models.py            # 数据模型
│   ├── pricing.py           # 价格引擎（MCP / 本地）
│   ├── menu.py / order.py   # MCP 业务适配层
│   ├── optimizer.py         # 套餐+热量约束优化
│   ├── split_order.py       # 拆单（一单1券/叠券/BOGO）
│   ├── party_time.py        # 多人聚餐时间协调
│   └── data/sample_data.py  # 离线示例数据（非真实价格）
├── tests/                  # 单元测试（12 项全过）
└── examples/               # 可运行演示
```

---

## 📜 许可证
MIT —— 仅用于非商业学习与交流，遵守麦当劳 MCP 服务规则。
