"""Ag erisimi olmadan uctan uca deneme: sentetik fiyatla grafik ve mesaj uretir.
Kullanim: KURU_CALISMA=1 python -m tests.sentetik
"""
import datetime as dt
import json
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

os.environ["KURU_CALISMA"] = "1"
from bot import data, main as m  # noqa: E402


def _seri(n, frek, bas, oynaklik, egim, tohum):
    rng = np.random.default_rng(tohum)
    bitis = pd.Timestamp.now(tz="UTC").floor(frek)
    idx = pd.date_range(end=bitis, periods=n, freq=frek)
    c = bas * np.exp(np.cumsum(rng.normal(egim, oynaklik, n)))
    df = pd.DataFrame({"close": c}, index=idx)
    df["open"] = df["close"].shift().fillna(df["close"])
    df["high"] = df[["open", "close"]].max(axis=1) * (1 + rng.uniform(0, oynaklik, n))
    df["low"] = df[["open", "close"]].min(axis=1) * (1 - rng.uniform(0, oynaklik, n))
    return df


def sahte(sembol, aralik, donem, deneme=3):
    saatlik = aralik == "1h"
    n = 480 if saatlik else 2500
    if sembol == "GC=F":
        return _seri(n, "h" if saatlik else "D", 4100 if saatlik else 1250, 0.002 if saatlik else 0.009, 0.0001 if saatlik else 0.0005, 1)
    if sembol == "USDTRY=X":
        return _seri(n, "h" if saatlik else "D", 46.0 if saatlik else 3.0, 0.0004 if saatlik else 0.004, 0.00003 if saatlik else 0.0011, 2)
    return _seri(70, "D", 100, 0.006, 0, 3)


data.seri_cek = sahte
data.kapalicarsi = lambda: {"alis": 6105.0, "satis": 6190.0, "kaynak": "sentetik"}

gecici = Path(tempfile.mkdtemp())
m.DURUM, m.CIKTI, m.ANALIZ = gecici / "durum", Path("cikti"), gecici / "latest.json"
ornek = json.loads(Path("analiz/ornek.json").read_text(encoding="utf-8"))
ornek["olusturma"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
m.ANALIZ.write_text(json.dumps(ornek, ensure_ascii=False), encoding="utf-8")
print(m.calistir())
print(Path("cikti/mesaj.html").read_text(encoding="utf-8"))
# ikinci tur: analiz yok + eski tahminlerin puanlanmasi
m.ANALIZ.unlink()
t = json.loads((m.DURUM / "tahminler.json").read_text())
for x in t:
    x["zaman"] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=100)).isoformat(timespec="seconds")
    x["fiyat"] *= 0.9
(m.DURUM / "tahminler.json").write_text(json.dumps(t))
print(m.calistir())
print(Path("cikti/mesaj.html").read_text(encoding="utf-8")[-700:])
print(json.dumps(json.loads((m.DURUM / "piyasa.json").read_text())["karne"]))
shutil.rmtree(gecici)
