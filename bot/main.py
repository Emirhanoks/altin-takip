"""Calistirma: veri -> gostergeler -> grafikler -> Telegram -> durum kaydi."""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import traceback
from pathlib import Path

import pandas as pd

from . import charts, data, indicators, report, telegram

KOK = Path(__file__).resolve().parent.parent
DURUM = KOK / "durum"
ANALIZ = KOK / "analiz" / "latest.json"
CIKTI = KOK / "cikti"
ANALIZ_GECERLILIK = dt.timedelta(hours=4)
CIFT_GONDERIM_KORUMA = dt.timedelta(minutes=20)

VADELER = {
    "kisa": dict(ad="Kısa vade", seri="saatlik", emalar=(20, 50), goster=240, bicim="%d.%m %H:%M",
                 aciklama="saatlik, son ~10 işlem günü", pencere=5,
                 ufuk=dt.timedelta(hours=24), esik=0.15, yatay=0.6, kayit_araligi=dt.timedelta(hours=2)),
    "orta": dict(ad="Orta vade", seri="gunluk", emalar=(50, 200), goster=250, bicim="%d.%m.%y",
                 aciklama="günlük, son 1 yıl", pencere=7,
                 ufuk=dt.timedelta(days=14), esik=1.0, yatay=2.0, kayit_araligi=dt.timedelta(hours=23)),
    "uzun": dict(ad="Uzun vade", seri="haftalik", emalar=(20, 50), goster=260, bicim="%m.%Y",
                 aciklama="haftalık, son 5 yıl, logaritmik ölçek", pencere=6, log=True,
                 ufuk=dt.timedelta(days=90), esik=3.0, yatay=5.0, kayit_araligi=dt.timedelta(days=6, hours=20)),
}


def simdi() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def oku(yol: Path, varsayilan):
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return varsayilan


def yaz(yol: Path, veri) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(veri, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _gecmis_fiyat(seri: pd.Series, an: pd.Timestamp, geri: dt.timedelta) -> float | None:
    hedef = an - geri
    onceki = seri[seri.index <= hedef]
    if onceki.empty or (hedef - onceki.index[-1]) > max(geri * 0.5, dt.timedelta(days=4)):
        return None
    return float(onceki.iloc[-1])


def piyasa_ozeti(seriler: dict, z: dt.datetime) -> dict:
    s, g = seriler["saatlik"], seriler["gunluk"]
    son = float(s["close"].iloc[-1])
    an = pd.Timestamp(z)
    deg = {}
    for ad, seri, geri in (("3s", s, dt.timedelta(hours=3)), ("24s", s, dt.timedelta(hours=24)),
                           ("7g", s, dt.timedelta(days=7)), ("30g", g, dt.timedelta(days=30)),
                           ("1y", g, dt.timedelta(days=365))):
        # kapali piyasada "3s" degisimi son islem anina gore hesaplanir
        ref_an = min(an, seri.index[-1]) if ad in ("3s", "24s") else an
        eski = _gecmis_fiyat(seri["close"], ref_an, geri)
        deg[ad] = round((son / eski - 1) * 100, 2) if eski else None
    return {
        "zaman": z.isoformat(timespec="seconds"),
        "gram": round(son, 2),
        "ons": round(float(s["ons"].iloc[-1]), 2),
        "kur": round(float(s["kur"].iloc[-1]), 4),
        "son_veri_zamani": s.index[-1].isoformat(),
        "piyasa_kapali": bool(an - s.index[-1] > pd.Timedelta(hours=3)),
        "degisim": deg,
        "yil_ici_zirve": round(float(g["high"].iloc[-252:].max()), 2),
        "yil_ici_dip": round(float(g["low"].iloc[-252:].min()), 2),
    }


def teknik_analiz(seriler: dict) -> dict:
    out = {}
    for anahtar, v in VADELER.items():
        df = seriler[v["seri"]]
        g = indicators.gorunum(df, *v["emalar"])
        g["seviyeler"] = indicators.seviyeler(df.iloc[-max(v["goster"], 120):], v["pencere"])
        out[anahtar] = g
    return out


def analiz_yukle(z: dt.datetime) -> dict | None:
    a = oku(ANALIZ, None)
    if not isinstance(a, dict):
        return None
    try:
        olusturma = dt.datetime.fromisoformat(str(a["olusturma"]).replace("Z", "+00:00"))
        if olusturma.tzinfo is None:
            olusturma = olusturma.replace(tzinfo=dt.timezone.utc)
    except Exception:  # noqa: BLE001
        return None
    if not (-dt.timedelta(minutes=30) < z - olusturma < ANALIZ_GECERLILIK):
        return None
    return a


def karne_guncelle(tahminler: list, fiyat: float, z: dt.datetime, teknik: dict, analiz: dict | None) -> dict:
    """Vadesi dolan tahminleri puanla, yenilerini kaydet, isabet ozetini dondur."""
    for t in tahminler:
        if t.get("sonuc") is not None:
            continue
        v = VADELER[t["vade"]]
        if z - dt.datetime.fromisoformat(t["zaman"]) >= v["ufuk"]:
            deg = (fiyat / t["fiyat"] - 1) * 100
            dogru = {"yukari": deg >= v["esik"], "asagi": deg <= -v["esik"], "yatay": abs(deg) < v["yatay"]}[t["yon"]]
            t.update({"sonuc": "dogru" if dogru else "yanlis", "gerceklesen_yuzde": round(deg, 2),
                      "degerlendirme": z.isoformat(timespec="seconds")})
    for anahtar, v in VADELER.items():
        a = ((analiz or {}).get("vadeler") or {}).get(anahtar) or {}
        yon, kaynak = (a["yon"], "analiz") if a.get("yon") in report.YON else (teknik[anahtar]["yon"], "teknik")
        son = next((t for t in reversed(tahminler) if t["vade"] == anahtar), None)
        if son and z - dt.datetime.fromisoformat(son["zaman"]) < v["kayit_araligi"]:
            continue
        tahminler.append({"zaman": z.isoformat(timespec="seconds"), "vade": anahtar, "yon": yon,
                          "kaynak": kaynak, "fiyat": round(fiyat, 2), "sonuc": None})
    del tahminler[:-3000]
    ozet = {}
    for anahtar in VADELER:
        biten = [t for t in tahminler if t["vade"] == anahtar and t.get("sonuc")]
        ozet[anahtar] = {"toplam": len(biten), "dogru": sum(t["sonuc"] == "dogru" for t in biten),
                         "son_20_dogru": sum(t["sonuc"] == "dogru" for t in biten[-20:]),
                         "son_20_toplam": len(biten[-20:])}
    return ozet


def calistir() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    kuru = os.environ.get("KURU_CALISMA") == "1"  # Telegram'a gondermeden dene
    tetik = os.environ.get("TETIK", "manual")
    z = simdi()
    durum = oku(DURUM / "durum.json", {})
    son = durum.get("son_gonderim")
    if tetik == "push" and son and z - dt.datetime.fromisoformat(son) < CIFT_GONDERIM_KORUMA:
        return "atlandi: az once gonderildi"

    seriler = data.gram_serileri()
    p = piyasa_ozeti(seriler, z)
    p["baglam"] = data.baglam()
    p["kapalicarsi"] = data.kapalicarsi()
    teknik = teknik_analiz(seriler)
    analiz = analiz_yukle(z)

    tahminler = oku(DURUM / "tahminler.json", [])
    karne = karne_guncelle(tahminler, p["gram"], z, teknik, analiz)

    CIKTI.mkdir(exist_ok=True)
    z_tr = z.astimezone(report.TZ)
    gorseller = []
    for anahtar, v in VADELER.items():
        df = seriler[v["seri"]]
        t = teknik[anahtar]
        gorseller.append(charts.ciz(
            df, str(CIKTI / f"{anahtar}.png"),
            f"Gram Altın — {v['ad']}: {report.YON[t['yon']] if not analiz else report.YON.get(((analiz.get('vadeler') or {}).get(anahtar) or {}).get('yon'), report.YON[t['yon']])}",
            f"{charts.tl(p['gram'], 2)} TL · {v['aciklama']} · RSI {t['rsi']:.0f}",
            v["emalar"], v["goster"], t["seviyeler"], v["bicim"],
            f"Kaynak: ons altın vadeli (GC=F) × USD/TRY ÷ 31,1035 · {z_tr:%d.%m.%Y %H:%M} (İstanbul) · Yatırım tavsiyesi değildir",
            log=v.get("log", False),
        ))

    if not kuru:
        if not token:
            yaz(DURUM / "piyasa.json", {**p, "teknik": teknik, "karne": karne})
            raise RuntimeError("Veri ve grafikler hazir ama TELEGRAM_BOT_TOKEN tanimli degil "
                               "(repo Settings > Secrets and variables > Actions).")
        sohbet = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or durum.get("chat_id") or telegram.sohbet_bul(token)
        if not sohbet:
            raise RuntimeError("Sohbet bulunamadi: Telegram'da bota /start yazin, sonra tekrar calistirin.")
        durum["chat_id"] = str(sohbet)
        telegram.gonder(token, str(sohbet), gorseller, report.baslik(p), report.metin(p, analiz, karne, teknik))
        durum["son_gonderim"] = z.isoformat(timespec="seconds")
    else:
        (CIKTI / "mesaj.html").write_text(
            report.baslik(p) + "\n\n-----\n\n" + report.metin(p, analiz, karne, teknik), encoding="utf-8")

    durum["son_rapor_turu"] = "analizli" if analiz else "yalnizca_teknik"
    yaz(DURUM / "durum.json", durum)
    yaz(DURUM / "tahminler.json", tahminler)
    yaz(DURUM / "piyasa.json", {**p, "teknik": teknik, "karne": karne})
    return f"gonderildi ({durum['son_rapor_turu']}, tetik={tetik})"


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    z = simdi().isoformat(timespec="seconds")
    try:
        sonuc = calistir()
        yaz(DURUM / "son_calisma.json", {"zaman": z, "durum": "tamam", "sonuc": sonuc})
        print(sonuc)
        return 0
    except Exception as e:  # noqa: BLE001
        iz = traceback.format_exc()
        mesaj = f"{type(e).__name__}: {e}"
        if token:
            iz, mesaj = iz.replace(token, "***"), mesaj.replace(token, "***")
        yaz(DURUM / "son_calisma.json", {"zaman": z, "durum": "hata", "hata": mesaj, "iz": iz[-3000:]})
        print(iz, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
