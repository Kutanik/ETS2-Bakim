"""Uygulama içi güncelleme (ets2bakim.guncelleme): sürüm karşılaştırma, surum.json denetimi, indirme + özet + zip
açma. Ağ yerine sahte yanıtlar, kurulumu başlatmak yerine kayıt (çalışan uygulamaya ve Drive'a dokunmaz)."""
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ets2bakim import guncelleme as g  # noqa: E402

ZIP_URL = "https://example.invalid/paket.zip"


class _Resp(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("ETS2-Maintenance-Simulator-9.9.9/program/python/python.exe", b"")
            z.writestr("ETS2-Maintenance-Simulator-9.9.9/program/ets2bakim/__init__.py", b"")
        self.zip = buf.getvalue()
        self.info = {"surum": "9.9.9", "zip": ZIP_URL, "sha256": hashlib.sha256(self.zip).hexdigest(),
                     "boyut": len(self.zip), "notlar": {"tr": "yeni"}}
        self.files = {"info": json.dumps(self.info).encode(), ZIP_URL: self.zip}
        self._open = g._open
        g._open = lambda url, timeout=0: _Resp(self.files[url])
        self.launched = []

    def tearDown(self):
        g._open = self._open
        shutil.rmtree(self.tmp, ignore_errors=True)

    def updater(self, game=None):
        u = g.Updater(self.tmp, lambda: game, info_url="info", work_dir=os.path.join(self.tmp, "is"))
        u.launch = self.launched.append
        return u

    def test_versions(self):
        self.assertTrue(g.is_newer("1.3.0", "1.2.1"))
        self.assertTrue(g.is_newer("1.10.0", "1.9.9"))
        self.assertFalse(g.is_newer("1.3", "1.3.0"))
        self.assertFalse(g.is_newer("1.2.1", "1.3.0"))
        self.assertFalse(g.is_newer("abc", "1.0"))

    def test_check_download_install(self):
        u = self.updater()
        self.assertTrue(u.check(background=False))
        self.assertEqual((u.status["state"], u.status["latest"], u.status["notes"]), ("available", "9.9.9", {"tr": "yeni"}))
        self.assertEqual(u.install(background=False), "ok")
        self.assertEqual(u.status["state"], "installing")
        self.assertEqual(len(self.launched), 1)
        self.assertTrue(os.path.isfile(os.path.join(self.launched[0], "python", "python.exe")))

    def test_bad_hash_is_not_installed(self):
        self.info["sha256"] = "0" * 64
        self.files["info"] = json.dumps(self.info).encode()
        u = self.updater()
        u.check(background=False)
        self.assertEqual(u.install(background=False), "ok")
        self.assertEqual((u.status["state"], u.status["error"]), ("error", "sha"))
        self.assertEqual(self.launched, [])

    def test_refusals(self):
        self.assertFalse(g.Updater(None).check())
        self.assertEqual(g.Updater(None).install(), "off")
        u = self.updater(game="eurotrucks2.exe")
        u.check(background=False)
        self.assertEqual(u.install(background=False), "game")
        self.files["info"] = b"<html>Google Drive</html>"                # paylaşım kapalıyken Drive bir sayfa döndürür
        u = self.updater()
        u.check(background=False)
        self.assertEqual((u.status["state"], u.status["error"]), ("error", "info"))
        self.assertEqual(u.install(background=False), "none")

    def test_cleanup_keeps_only_log(self):
        u = self.updater()
        u.check(background=False)
        u.install(background=False)
        work = os.path.join(self.tmp, "is")
        open(os.path.join(work, "kurulum.log"), "w").close()
        self.assertGreater(len(os.listdir(work)), 1)                  # indirilen zip + açılmış paket + günlük
        u.busy = True
        self.assertFalse(u.cleanup())                                 # indirme / kurulum sürerken dokunmaz
        u.busy = False
        self.assertTrue(u.cleanup())
        self.assertEqual(os.listdir(work), ["kurulum.log"])


if __name__ == "__main__":
    unittest.main()
