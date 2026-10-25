"""多人聚餐时间协调器（多人聚餐时间 Skill 核心）。

业务：发起人提出若干时间档位 -> 参与者逐一反馈「有空/没空」->
当所有参与者对某个档位都「有空」时，聚餐达成共识（confirmed）。

该模块只负责「时间协调」这一本地逻辑；一旦达成共识，即可把确认的时间
交给麦算盘优化器去组合套餐 + 优惠券并下单（见 optimizer / order 模块）。
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Optional

from .models import Availability, PartySession, TimeSlot


class PartyTimeCoordinator:
    """管理多个聚餐会话的创建、反馈与共识判定。"""

    def __init__(self, store_path: str = "party_sessions.json") -> None:
        self.store_path = store_path
        self.sessions: dict[str, PartySession] = {}
        self.load()

    # ---------- 会话生命周期 ----------

    def new_session(
        self,
        session_id: str,
        initiator: str,
        title: str,
        slots: list[TimeSlot],
    ) -> PartySession:
        if session_id in self.sessions:
            raise ValueError(f"会话 {session_id} 已存在")
        session = PartySession(
            session_id=session_id,
            initiator=initiator,
            title=title,
            slots=slots,
            participants=[initiator],
            availabilities=[Availability(pid=initiator, name=initiator)],
            status="collecting",
        )
        self.sessions[session_id] = session
        self.save()
        return session

    def join(self, session_id: str, pid: str, name: str) -> PartySession:
        session = self._get(session_id)
        if pid not in session.participants:
            session.participants.append(pid)
            session.availabilities.append(Availability(pid=pid, name=name))
            self.save()
        return session

    def respond(
        self, session_id: str, pid: str, responses: dict[str, bool]
    ) -> PartySession:
        """提交某参与者对各档位的反馈。提交后自动判定共识。"""
        session = self._get(session_id)
        av = self._availability(session, pid)
        for slot_id, ok in responses.items():
            av.responses[slot_id] = bool(ok)
        self._try_consensus(session)
        self.save()
        return session

    # ---------- 共识判定 ----------

    def common_slots(self, session: PartySession) -> list[str]:
        """返回所有参与者都有空的档位 id 列表。"""
        if not session.participants:
            return []
        common: set[str] = set(session.slots and [s.slot_id for s in session.slots])
        for av in session.availabilities:
            available = {sid for sid, ok in av.responses.items() if ok}
            common &= available
        return [sid for sid in (s.slot_id for s in session.slots) if sid in common]

    def _all_responded(self, session: PartySession) -> bool:
        if not session.slots:
            return False
        for av in session.availabilities:
            if not all(sid in av.responses for sid in (s.slot_id for s in session.slots)):
                return False
        return True

    def _try_consensus(self, session: PartySession) -> bool:
        if session.status != "collecting":
            return False
        if not self._all_responded(session):
            return False
        commons = self.common_slots(session)
        if commons:
            # 默认确认最早的共同档位；也可由发起人手动 confirm 指定
            session.confirmed_slot = commons[0]
            session.status = "confirmed"
            return True
        return False

    def confirm(self, session_id: str, slot_id: Optional[str] = None) -> PartySession:
        """发起人手动确认聚餐时间（可指定某个共同档位）。"""
        session = self._get(session_id)
        if slot_id is None:
            commons = self.common_slots(session)
            if not commons:
                raise ValueError("当前无全员可参加的档位，无法确认")
            slot_id = commons[0]
        else:
            if slot_id not in self.common_slots(session):
                raise ValueError(f"档位 {slot_id} 并非全员可参加，不能确认")
        session.confirmed_slot = slot_id
        session.status = "confirmed"
        self.save()
        return session

    def cancel(self, session_id: str) -> PartySession:
        session = self._get(session_id)
        session.status = "cancelled"
        self.save()
        return session

    def summary(self, session_id: str) -> str:
        session = self._get(session_id)
        lines = [f"聚餐「{session.title}」发起人：{session.initiator}  状态：{session.status}"]
        slot_label = {s.slot_id: s.label for s in session.slots}
        lines.append("时间档位：")
        for s in session.slots:
            lines.append(f"  - {s.label} ({s.slot_id})")
        lines.append(f"参与人数：{len(session.participants)}")
        for av in session.availabilities:
            resp = "、".join(
                f"{slot_label.get(sid, sid)}={'有空' if ok else '没空'}"
                for sid, ok in av.responses.items()
            ) or "（未反馈）"
            lines.append(f"  {av.name}: {resp}")
        commons = self.common_slots(session)
        if commons:
            lines.append("全员可参加档位：" + "、".join(slot_label.get(c, c) for c in commons))
        if session.confirmed_slot:
            lines.append(f"✅ 已确认时间：{slot_label.get(session.confirmed_slot, session.confirmed_slot)}")
        else:
            lines.append("⏳ 暂未达成共识，继续收集反馈中……")
        return "\n".join(lines)

    # ---------- 持久化 ----------

    def _get(self, session_id: str) -> PartySession:
        if session_id not in self.sessions:
            raise KeyError(f"会话 {session_id} 不存在")
        return self.sessions[session_id]

    @staticmethod
    def _availability(session: PartySession, pid: str) -> Availability:
        for av in session.availabilities:
            if av.pid == pid:
                return av
        raise KeyError(f"参与者 {pid} 不在会话中")

    def save(self) -> None:
        data = {sid: asdict(s) for sid, s in self.sessions.items()}
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self) -> None:
        if not os.path.exists(self.store_path):
            return
        with open(self.store_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for sid, d in data.items():
            slots = [TimeSlot(**s) for s in d.get("slots", [])]
            avs = [Availability(**a) for a in d.get("availabilities", [])]
            self.sessions[sid] = PartySession(
                session_id=d["session_id"],
                initiator=d["initiator"],
                title=d["title"],
                slots=slots,
                participants=d.get("participants", []),
                availabilities=avs,
                confirmed_slot=d.get("confirmed_slot"),
                status=d.get("status", "collecting"),
            )
