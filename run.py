"""一键测试入口：跑离线单元测试 + 离线配单演示。

用法（在任意目录都能跑，路径含中文也没关系）：
    "<python路径>" run.py
例如：
    "C:/Users/skyfire/.workbuddy/binaries/python/versions/3.13.12/python.exe" run.py
    py run.py
    python run.py
"""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def run_tests() -> bool:
    print("=" * 56)
    print("[1/2] 单元测试（tests/）")
    print("=" * 56)
    loader = unittest.TestLoader()
    suite = loader.discover(os.path.join(ROOT, "tests"), top_level_dir=ROOT)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful()


def run_offline_demo() -> None:
    print("\n" + "=" * 56)
    print("[2/2] 离线配单演示（无需 Token）")
    print("=" * 56)
    demo_path = os.path.join(ROOT, "examples", "demo_optimizer.py")
    spec = importlib.util.spec_from_file_location("demo_optimizer", demo_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    module.main()


def main() -> int:
    print(f"项目目录: {ROOT}")
    print(f"Python: {sys.executable} ({sys.version.split()[0]})")
    ok = run_tests()
    if ok:
        try:
            run_offline_demo()
        except Exception as e:  # noqa: BLE001
            print(f"离线演示出错: {type(e).__name__}: {e}")
    print("\n" + "-" * 56)
    print("✅ 全部通过！" if ok else "❌ 有测试未通过，请向上查看报错。")
    print("实时 demo（需 Token + 门店编码）:")
    print('    python examples/demo_mcp_live.py --optimize --store-code 门店编码')
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
