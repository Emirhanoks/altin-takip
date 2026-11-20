"""Zamanlanmis (yedek) calismada rapor gerekli mi? Yalnizca standart kutuphane kullanir."""
import datetime as dt
import json
import os
from pathlib import Path

YEDEK_ESIK_DK = 170  # son gonderimden bu kadar dakika gectiyse yedek rapor gonder

durum_yolu = Path(__file__).resolve().parent.parent / "durum" / "durum.json"
tetik = os.environ.get("TETIK", "manual")
calis = True
if tetik == "schedule" and durum_yolu.exists():
    try:
        son = json.loads(durum_yolu.read_text(encoding="utf-8")).get("son_gonderim")
        if son:
            gecen = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(son)
            calis = gecen > dt.timedelta(minutes=YEDEK_ESIK_DK)
    except Exception:  # noqa: BLE001
        calis = True
print(f"tetik={tetik} calis={calis}")
cikti = os.environ.get("GITHUB_OUTPUT")
if cikti:
    with open(cikti, "a", encoding="utf-8") as f:
        f.write(f"calis={'true' if calis else 'false'}\n")
