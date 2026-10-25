"""麦当劳 MCP（Streamable HTTP）客户端。

安全红线（来自官方踩坑提醒）：
- MCP Token 一律从环境变量 MCD_MCP_TOKEN 读取，**绝不**硬编码、绝不写进仓库。
- 请求头使用 `Authorization: Bearer <TOKEN>`。
- 每个 Token 每分钟最多 600 次请求，超出返回 429；401 表示 Token 失效。

本模块只负责"传输 + JSON-RPC"，不臆造任何业务数据。
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import Any, Optional

DEFAULT_MCP_URL = "https://mcp.mcd.cn"


class McpAuthError(RuntimeError):
    """Token 缺失或失效。"""


class McpRateLimitError(RuntimeError):
    """触发限流（429）。"""


class McpClient:
    """极简麦当劳 MCP Streamable HTTP 客户端。"""

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: str = DEFAULT_MCP_URL,
        timeout: int = 30,
    ) -> None:
        self.token = token or os.environ.get("MCD_MCP_TOKEN")
        if not self.token:
            raise McpAuthError(
                "未找到 MCP Token。请设置环境变量 MCD_MCP_TOKEN "
                "(例如在 .env 中写入 MCD_MCP_TOKEN=你的Token)，切勿将 Token 提交到 GitHub。"
            )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session_id: Optional[str] = None
        self._initialized = False

    # ---------- 底层传输 ----------

    def _post(self, payload: dict[str, Any]) -> Any:
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        req = urllib.request.Request(
            self.base_url, data=body, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                # 捕获会话 ID，供后续请求复用
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    self.session_id = sid
                return self._parse_response(raw)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise McpAuthError("MCP Token 无效或已过期（401），请重新申请。") from e
            if e.code == 429:
                raise McpRateLimitError(
                    "触发限流（429）：超过 600 次/分钟，请降低请求频率。"
                ) from e
            detail = e.read().decode("utf-8", "ignore") if e.fp else ""
            raise RuntimeError(f"MCP 请求失败 HTTP {e.code}: {detail}") from e

    @staticmethod
    def _parse_response(raw: str) -> Any:
        """兼容 application/json 与 text/event-stream(SSE) 两种返回。"""
        raw = raw.strip()
        if not raw:
            return None
        # SSE：取第一个 data: 行
        if raw.startswith("event:") or "data:" in raw:
            for line in raw.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    data = line[len("data:"):].strip()
                    if data:
                        return json.loads(data)
        return json.loads(raw)

    # ---------- JSON-RPC 封装 ----------

    def _rpc(self, method: str, params: dict[str, Any], req_id: int = 1) -> Any:
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        return self._post(payload)

    def connect(self) -> None:
        """执行 initialize 握手，建立会话。"""
        result = self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "mcd-party-officer", "version": "1.0.0"},
            },
        )
        # 发送 initialized 通知（无需响应）
        try:
            self._post(
                {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
            )
        except Exception:
            pass
        self._initialized = True
        _ = result  # 初始化结果可用于能力协商，此处忽略

    def list_tools(self) -> list[dict[str, Any]]:
        resp = self._rpc("tools/list", {}, req_id=2)
        return (resp or {}).get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """调用一个 MCP 工具，返回其 result 字段。"""
        if not self._initialized:
            self.connect()
        resp = self._rpc(
            "tools/call", {"name": name, "arguments": arguments}, req_id=3
        )
        return (resp or {}).get("result")

    def call_text(self, name: str, arguments: dict[str, Any]) -> str:
        """许多 MCP 工具以 content[].text 返回，这里抽取拼接文本。"""
        result = self.call_tool(name, arguments)
        if not result:
            return ""
        parts = []
        for item in result.get("content", []):
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(parts)

    # ---------- 返回解析 ----------

    @staticmethod
    def join_text(result: Any) -> str:
        """拼接 tools/call 结果里的 content[].text。"""
        if not isinstance(result, dict):
            return ""
        parts = []
        for item in result.get("content", []):
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(parts)

    @classmethod
    def extract_json(cls, result: Any) -> Optional[dict]:
        """从麦当劳 MCP 返回中抽取真正的 JSON。

        麦当劳 MCP 的返回格式不统一，实测有两种：
        1) `# API Response Information ... ## Original Response\n<json>`（可能再包 ``` 代码块）；
        2) 指令文本里**内嵌**一段 JSON（如 query-nearby-stores：`...不能为空\n{...}## 展示结果...`）。
        策略：优先取 `## Original Response` 之后；否则用 raw_decode 从第一个 `{` 解析一个完整 JSON 对象。
        """
        text = cls.join_text(result)
        if not text:
            return None
        marker = "## Original Response"
        if marker in text:
            text = text.split(marker, 1)[1]
        start = text.find("{")
        if start == -1:
            return None
        try:
            obj, _ = json.JSONDecoder().raw_decode(text, start)
            return obj if isinstance(obj, dict) else {"data": obj}
        except Exception:
            return None

    def call_json(self, name: str, arguments: Optional[dict] = None) -> Optional[dict]:
        """调用工具并直接返回解析后的 JSON（含内层 data）。"""
        return self.extract_json(self.call_tool(name, arguments or {}))
