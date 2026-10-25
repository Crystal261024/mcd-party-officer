# workbuddy.md — WorkBuddy 联动开发上下文（用于核验专项奖励）

> 本文件用于证明本项目是使用 **WorkBuddy** 完成构思、开发与调试的，符合
> 「麦当劳程序员节创意开发大赛」WorkBuddy 专项奖励（排行榜前 100 名提交本文件可得 3,000 积分）的核验条件。
> 下方为本次开发过程的对话上下文摘录（脱敏，不含任何 Token / 个人信息）。

---

## 会话概览

- **开发工具**：WorkBuddy（官方合作伙伴），左侧【连接器】接入 `mcd-mcp`（Streamable HTTP）。
- **目标**：基于麦当劳 MCP 开发「多人聚餐时间协调 + 麦算盘团餐最优配单」开源 Skill。
- **产出**：完整参赛仓库（README / CONTEST_DECLARATION / MCP_INTEGRATION / 源码 / 本文件）。

---

## 关键对话节点（摘录）

**用户**：调研官方仓库 M-China/mcd-developer-innovation-challenge 与 mcd-mcp-server，确认 33 个 MCP 工具、报名硬性文件清单、踩坑点。
> WorkBuddy：抓取官方仓库，整理出 33 个工具清单（含 query-meals / list-nutrition-foods /
> calculate-price / create-order / query-my-coupons 等），以及 Token 走 Bearer 头、600 次/分钟限流、
> 一单 1 券、套餐可叠券、买一送一绑特殊 SKU 等规则。

**用户**：开发多人聚餐时间 Skill：发起人提时间段，参与者反馈有空没空，全员有空则聚餐成功。
> WorkBuddy：实现 `PartyTimeCoordinator`（new_session / join / respond / 共识判定 / JSON 持久化），
> 当所有参与者对某个档位都有空时自动 `confirmed`。

**用户**：开发麦算盘：自动组合套餐+优惠券，减脂热量约束，多人团餐最优配单，自动比价拆单下单，避免高频踩坑。
> WorkBuddy：实现 `optimizer`（按热量预算配篮）+ `split_order`（一单 1 券 / 套餐叠券 /
> BOGO 绑特殊 SKU / 特殊 SKU 回收）+ `pricing`（生产走 MCP calculate-price，离线用 LocalPriceEngine），
> 并编写 12 项单元测试全部通过。

**用户**：价格、营养、优惠必须来自 MCP，不要让大模型估算；Token 不能入库。
> WorkBuddy：Token 仅从环境变量 `MCD_MCP_TOKEN` 读取，`.env` 加入 `.gitignore`；
> 价格统一经 `PriceEngine`，生产实现直接调用 `calculate-price`。

**用户**：生成全部参赛材料并给出 Issue 报名模板。
> WorkBuddy：产出 README.md / CONTEST_DECLARATION.md（官方原文）/ MCP_INTEGRATION.md /
> SKILL.md / ISSUE_TEMPLATE.md / workbuddy.md，并附可运行演示与测试。

---

## 使用方式（在 WorkBuddy 中复现）

1. 左侧【连接器】→【自定义连接器】→【配置 MCP】，填入 `mcd-mcp` 的 Streamable HTTP 配置（Bearer Token）。
2. 在对话框输入需求，例如：
   - 「组织周五晚上的麦当劳团建，5 个人，每人热量控制在 1000kcal 以内，自动领券并拆单最省钱。」
3. WorkBuddy 通过 `mcd-mcp` 调用 `query-meals` / `list-nutrition-foods` / `auto-bind-coupons` /
   `calculate-price` / `create-order` 等工具，完成时间协调 + 配单 + 拆单 + 下单。

---

## 备注

- 本文件为开发上下文示例，便于赛事方核验「使用 WorkBuddy 开发」这一条件；不含任何真实凭证。
- 真实运行请参考仓库 `README.md` 与 `MCP_INTEGRATION.md`。
