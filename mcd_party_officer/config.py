"""零依赖 .env 加载器（仅标准库）。

把项目根目录 `.env` 中的 KEY=VALUE 写入 os.environ（不覆盖已存在的环境变量），
便于本地开发时把 MCD_MCP_TOKEN 放进 `.env`，而无需在系统里设环境变量。

⚠️ `.env` 已被 .gitignore 忽略，切勿把真实 Token 提交到 GitHub。
"""

from __future__ import annotations

import os


def load_dotenv(path: str = ".env", override: bool = False) -> bool:
    """读取 .env 并写入环境变量。返回是否成功加载到文件。"""
    if not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if not key:
                continue
            if override:
                os.environ[key] = value
            else:
                os.environ.setdefault(key, value)
    return True
