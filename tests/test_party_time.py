import os
import unittest

from mcd_party_officer import PartyTimeCoordinator, TimeSlot

STORE = "test_party_sessions.json"


class TestPartyTime(unittest.TestCase):
    def setUp(self):
        if os.path.exists(STORE):
            os.remove(STORE)
        self.coord = PartyTimeCoordinator(store_path=STORE)
        self.slots = [
            TimeSlot("s1", "周五 18:30", "2026-10-30T18:30", "2026-10-30T20:00"),
            TimeSlot("s2", "周六 12:00", "2026-10-31T12:00", "2026-10-31T13:30"),
            TimeSlot("s3", "周六 18:30", "2026-10-31T18:30", "2026-10-31T20:00"),
        ]
        self.coord.new_session("p1", "沙", "团建", self.slots)
        self.coord.join("p1", "m", "小明")
        self.coord.join("p1", "h", "小红")

    def tearDown(self):
        if os.path.exists(STORE):
            os.remove(STORE)

    def test_not_confirmed_before_all_respond(self):
        self.coord.respond("p1", "沙", {"s1": True, "s2": True, "s3": True})
        self.assertEqual(self.coord.sessions["p1"].status, "collecting")

    def test_consensus_auto_confirm(self):
        self.coord.respond("p1", "沙", {"s1": True, "s2": True, "s3": True})
        self.coord.respond("p1", "m", {"s1": False, "s2": True, "s3": True})
        self.coord.respond("p1", "h", {"s1": False, "s2": True, "s3": False})
        sess = self.coord.sessions["p1"]
        self.assertEqual(sess.status, "confirmed")
        self.assertEqual(sess.confirmed_slot, "s2")  # 全员可参加的最早档位

    def test_no_common_slot(self):
        self.coord.respond("p1", "沙", {"s1": True, "s2": False, "s3": False})
        self.coord.respond("p1", "m", {"s1": False, "s2": True, "s3": False})
        self.coord.respond("p1", "h", {"s1": False, "s2": False, "s3": True})
        self.assertEqual(self.coord.sessions["p1"].status, "collecting")
        self.assertIsNone(self.coord.sessions["p1"].confirmed_slot)


if __name__ == "__main__":
    unittest.main()
