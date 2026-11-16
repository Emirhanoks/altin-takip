"""Fiyat verisi: ons altin (GC=F) x USD/TRY -> gram altin (TL)."""
from __future__ import annotations

import time

import pandas as pd
import requests

ONS_GRAM = 31.1034768
UA = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
}


def _yahoo_ham(sembol: str, aralik: str, donem: str) -> pd.DataFrame:
    son_hata = None
    for host in ("query1", "query2"):
        try:
            r = requests.get(
                f"https://{host}.finance.yahoo.com/v8/finance/chart/{sembol}",
                params={"interval": aralik, "range": donem, "includePrePost": "false"},
                headers=UA,
                timeout=25,
            )
            r.raise_for_status()
            sonuc = r.json()["chart"]["result"][0]
            q = sonuc["indicators"]["quote"][0]
            df = pd.DataFrame(
                {k: q[k] for k in ("open", "high", "low", "close")},
                index=pd.to_datetime(sonuc["timestamp"], unit="s", utc=True),
            )
            df = df.dropna(subset=["close"]).astype(float)
            if len(df) >= 5:
                return df
            son_hata = RuntimeError(f"{sembol}: yetersiz veri ({len(df)})")
        except Exception as e:  # noqa: BLE001
            son_hata = e
    raise RuntimeError(f"Yahoo ham istek basarisiz: {sembol}: {type(son_hata).__name__}")


def _yahoo_yf(sembol: str, aralik: str, donem: str) -> pd.DataFrame:
    import yfinance as yf

    df = yf.Ticker(sembol).history(period=donem, interval=aralik, auto_adjust=False)
    if df is None or df.empty:
        raise RuntimeError(f"yfinance bos dondu: {sembol}")
    df = df.rename(columns=str.lower)[["open", "high", "low", "close"]].dropna(subset=["close"])
    idx = pd.DatetimeIndex(df.index)
    df.index = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    return df.astype(float)


def seri_cek(sembol: str, aralik: str, donem: str, deneme: int = 3) -> pd.DataFrame:
    """Once hafif ham istek, olmazsa yfinance; ikisi de birkac kez denenir."""
    hata = None
    for i in range(deneme):
        for fn in (_yahoo_ham, _yahoo_yf):
            try:
                return fn(sembol, aralik, donem)
            except Exception as e:  # noqa: BLE001
                hata = e
        time.sleep(4 * (i + 1))
    raise RuntimeError(f"Veri alinamadi: {sembol} {aralik}/{donem}: {hata}")


def _gram(altin: pd.DataFrame, kur: pd.DataFrame) -> pd.DataFrame:
    a = altin.sort_index()
    k = kur[["close"]].rename(columns={"close": "kur"}).sort_index()
    a = a.reset_index(names="t")
    k = k.reset_index(names="t")
    a["t"] = a["t"].astype("datetime64[ns, UTC]")
    k["t"] = k["t"].astype("datetime64[ns, UTC]")
    m = pd.merge_asof(a, k, on="t", direction="backward", tolerance=pd.Timedelta("4D"))
    m = m.dropna(subset=["kur"]).set_index("t")
    out = pd.DataFrame(index=m.index)
    for c in ("open", "high", "low", "close"):
        out[c] = m[c] * m["kur"] / ONS_GRAM
    out["ons"] = m["close"]
    out["kur"] = m["kur"]
    return out


def gram_serileri() -> dict[str, pd.DataFrame]:
    """saatlik (~1 ay), gunluk (10 yil), haftalik (gunlukten) gram altin TL serileri."""
    saatlik = _gram(seri_cek("GC=F", "1h", "1mo"), seri_cek("USDTRY=X", "1h", "1mo"))
    ga, gk = seri_cek("GC=F", "1d", "10y"), seri_cek("USDTRY=X", "1d", "10y")
    ga.index, gk.index = ga.index.normalize(), gk.index.normalize()
    ga = ga[~ga.index.duplicated(keep="last")]
    gk = gk[~gk.index.duplicated(keep="last")]
    gunluk = _gram(ga, gk)
    # gunluk serinin son mumunu canli (saatlik) fiyatla esitle: tum vadeler ayni son fiyati gostersin
    if saatlik.index[-1] >= gunluk.index[-1]:
        canli = float(saatlik["close"].iloc[-1])
        i = gunluk.index[-1]
        gunluk.loc[i, "close"] = canli
        gunluk.loc[i, "high"] = max(float(gunluk.loc[i, "high"]), canli)
        gunluk.loc[i, "low"] = min(float(gunluk.loc[i, "low"]), canli)
        gunluk.loc[i, ["ons", "kur"]] = saatlik[["ons", "kur"]].iloc[-1].to_numpy()
    haftalik = (
        gunluk.resample("W-FRI")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "ons": "last", "kur": "last"})
        .dropna(subset=["close"])
    )
    return {"saatlik": saatlik, "gunluk": gunluk, "haftalik": haftalik}


BAGLAM = {
    "dolar_endeksi": "DX-Y.NYB",
    "abd_10y_faiz": "^TNX",
    "gumus_ons": "SI=F",
    "brent": "BZ=F",
    "sp500": "^GSPC",
    "vix": "^VIX",
}


def baglam() -> dict:
    """Altini etkileyen yan gostergeler; herhangi biri alinamazsa atlanir."""
    out = {}
    for ad, sembol in BAGLAM.items():
        try:
            df = seri_cek(sembol, "1d", "3mo", deneme=1)
            son, onceki = float(df["close"].iloc[-1]), float(df["close"].iloc[-2])
            ay = float(df["close"].iloc[-22]) if len(df) > 22 else float(df["close"].iloc[0])
            out[ad] = {
                "son": round(son, 4),
                "gunluk_degisim_yuzde": round((son / onceki - 1) * 100, 2),
                "aylik_degisim_yuzde": round((son / ay - 1) * 100, 2),
            }
        except Exception:  # noqa: BLE001
            continue
    return out


def _sayi(v):
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("₺", "").replace("%", "").strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s)


def kapalicarsi() -> dict | None:
    """Serbest piyasa gram altin alis/satis (varsa). Bulunamazsa None."""
    try:
        r = requests.get("https://finans.truncgil.com/v4/today.json", headers=UA, timeout=20)
        r.raise_for_status()
        g = r.json().get("GRA") or {}
        alis = _sayi(g.get("Buying", g.get("Alış")))
        satis = _sayi(g.get("Selling", g.get("Satış")))
        if alis > 0 and satis > 0:
            return {"alis": round(alis, 2), "satis": round(satis, 2), "kaynak": "finans.truncgil.com"}
    except Exception:  # noqa: BLE001
        pass
    return None
