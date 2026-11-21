"""Katmanın semantik giriş komutları: ebk_overlay.cpp CMD_NAMES ile overlay_feed'in komut kodları aynı sırada olmalı;
yoksa oyunda yanlış kontrole basılır (kontak kapatma yerine motor durdurma gibi)."""
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ets2bakim.overlay_feed import CMD_ENGINE_TOGGLE, CMD_IGNITION_OFF  # noqa: E402


class GameControlCodeTests(unittest.TestCase):
    def test_codes_match_overlay(self):
        with open(os.path.join(ROOT, "overlay", "src", "ebk_overlay.cpp"), encoding="utf-8") as fh:
            m = re.search(r"CMD_NAMES\[CMD_COUNT\] = \{([^}]*)\}", fh.read())
        names = re.findall(r'"(\w+)"', m.group(1))
        self.assertEqual(names[CMD_IGNITION_OFF - 1], "ignitionoff")
        self.assertEqual(names[CMD_ENGINE_TOGGLE - 1], "engine")

if __name__ == "__main__":
    unittest.main()
