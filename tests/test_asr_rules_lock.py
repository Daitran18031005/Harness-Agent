"""Khóa luật ASR: ITN + trích thực thể + bảng cách đọc SKU phải đứng yên từ khi chốt (xem scripts/lock_asr_rules.py)."""
import json
import os
import unittest

from scripts import lock_asr_rules as lock


class AsrRulesLockTest(unittest.TestCase):
    def test_rules_match_the_recorded_lock(self):
        recorded = json.load(open(lock.LOCK_PATH, encoding="utf-8"))
        now = lock.current()
        for rel, digest in now["files"].items():
            self.assertEqual(recorded["files"].get(rel), digest,
                             f"{rel} đã đổi so với khóa {recorded['version']}. Nếu CỐ Ý đổi luật: "
                             "python scripts/lock_asr_rules.py --update --version <mới> --reason '...' "
                             "(và từ đó số đo trên D01–D04 không còn so được với trước).")
        self.assertEqual(recorded["normalizer_itn"], now["normalizer_itn"],
                         "phần ITN/ASR_FIXES của normalizer đã đổi so với khóa — cập nhật khóa có chủ đích.")

    def test_lock_records_dev_set_and_version(self):
        recorded = json.load(open(lock.LOCK_PATH, encoding="utf-8"))
        self.assertEqual(recorded["dev_set"], ["D01", "D02", "D03", "D04"])
        self.assertTrue(recorded["version"])
        self.assertIn("trong tập phát triển", recorded["note"])


if __name__ == "__main__":
    unittest.main()
