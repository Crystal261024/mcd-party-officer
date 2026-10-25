"""多人聚餐时间协调演示（离线模式，无需 Token）。

展示：发起人提出时间档位 -> 参与者反馈 -> 全员有空则自动达成共识。
达成共识后，即可把确认时间交给麦算盘去做配单下单。
"""

import os
import sys

# 允许从任意目录运行本脚本（如 examples/ 目录下）：把项目根目录加入搜索路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcd_party_officer import PartyTimeCoordinator, TimeSlot


def main() -> None:
    coord = PartyTimeCoordinator(store_path="demo_party_sessions.json")

    slots = [
        TimeSlot("s1", "周五 18:30", "2026-10-30T18:30", "2026-10-30T20:00"),
        TimeSlot("s2", "周六 12:00", "2026-10-31T12:00", "2026-10-31T13:30"),
        TimeSlot("s3", "周六 18:30", "2026-10-31T18:30", "2026-10-31T20:00"),
    ]

    coord.new_session("party1", "发起人-沙", "周末麦当劳团建", slots)
    coord.join("party1", "xiaoming", "小明")
    coord.join("party1", "xiaohong", "小红")

    print(coord.summary("party1"))

    # 反馈：小明周五没空，周六都有空；小红只有周六中午有空
    coord.respond("party1", "发起人-沙", {"s1": True, "s2": True, "s3": True})
    coord.respond("party1", "xiaoming", {"s1": False, "s2": True, "s3": True})
    coord.respond("party1", "xiaohong", {"s1": False, "s2": True, "s3": False})

    print("\n" + "=" * 50)
    print(coord.summary("party1"))
    print("=" * 50)


if __name__ == "__main__":
    main()
