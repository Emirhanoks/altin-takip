"""Telegram'a dokunmadan: iki botlu gonderim mantigini dener.
Kullanim: python -m tests.coklu_bot
"""
import json
import os
import shutil
import tempfile
from pathlib import Path

os.environ.pop("KURU_CALISMA", None)
os.environ["TUM_SECRETLAR"] = json.dumps({
    "TELEGRAM_BOT": "1111111111:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    "IKINCI_BOT": "2222222222:BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
    "github_token": "ghs_x", "DIGER": "metin",
})
os.environ["TELEGRAM_CHAT_ID"] = "555"

from bot import data, main as m, telegram  # noqa: E402
from tests import sentetik_veri  # noqa: E402

data.seri_cek = sentetik_veri.sahte
data.kapalicarsi = lambda: None
gonderimler = []


def sahte_gonder(token, sohbet, gorseller, baslik, metin):
    if token.startswith("1111") and sohbet != "555":
        raise telegram.TelegramHata("chat not found")
    if token.startswith("2222") and sohbet == "555":
        raise telegram.TelegramHata("chat not found")
    gonderimler.append((token[:4], sohbet))


telegram.gonder = sahte_gonder
telegram.sohbetler_bul = lambda t: ["777", "888"] if t.startswith("2222") else []

gecici = Path(tempfile.mkdtemp())
m.DURUM, m.CIKTI, m.ANALIZ = gecici / "durum", Path("cikti"), gecici / "latest.json"
print(m.calistir())
print(sorted(gonderimler))
d = json.loads((m.DURUM / "durum.json").read_text())
print(json.dumps(d["botlar"]), d["uyarilar"])
assert sorted(gonderimler) == [("1111", "555"), ("2222", "777"), ("2222", "888")]
assert [ad for ad, _ in m.tokenlar()] == ["TELEGRAM_BOT", "IKINCI_BOT"]
shutil.rmtree(gecici)
print("TAMAM")
