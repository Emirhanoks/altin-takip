"""Teknik gostergeler ve kural tabanli gorunum."""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=min(n, max(2, len(s) // 2))).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    kazanc = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    kayip = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = kazanc / kayip.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100.0).where(kazanc.notna())


def macd(s: pd.Series):
    hat = ema(s, 12) - ema(s, 26)
    sinyal = hat.ewm(span=9, adjust=False).mean()
    return hat, sinyal, hat - sinyal


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    onceki = df["close"].shift()
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - onceki).abs(), (df["low"] - onceki).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=min(n, len(df) // 2 or 1)).mean()


def seviyeler(df: pd.DataFrame, pencere: int = 5, adet: int = 2) -> dict:
    """Son fiyatin altindaki/ustundeki en yakin donus (pivot) bolgeleri."""
    son = float(df["close"].iloc[-1])
    a = float(atr(df).iloc[-1])
    hi, lo = df["high"].to_numpy(), df["low"].to_numpy()
    noktalar = []
    for i in range(pencere, len(df) - pencere):
        if hi[i] == hi[i - pencere : i + pencere + 1].max():
            noktalar.append(float(hi[i]))
        if lo[i] == lo[i - pencere : i + pencere + 1].min():
            noktalar.append(float(lo[i]))
    noktalar.sort()
    kumeler: list[list[float]] = []
    for p in noktalar:
        if kumeler and p - kumeler[-1][-1] <= 0.5 * a:
            kumeler[-1].append(p)
        else:
            kumeler.append([p])
    merkezler = [(float(np.mean(k)), len(k)) for k in kumeler]
    bosluk = 0.25 * a
    destek = sorted((m for m, _ in merkezler if m < son - bosluk), reverse=True)[:adet]
    direnc = sorted(m for m, _ in merkezler if m > son + bosluk)[:adet]
    tahmini = False
    if not direnc:  # tarihi zirve bolgesi: ATR projeksiyonu
        direnc, tahmini = [son + a * 1.5, son + a * 3], True
    if not destek:
        destek = [son - a * 1.5, son - a * 3]
    return {
        "destek": [round(x, 2) for x in destek],
        "direnc": [round(x, 2) for x in direnc],
        "direnc_projeksiyon": tahmini,
        "atr": round(a, 2),
    }


def gorunum(df: pd.DataFrame, kisa: int, uzun: int) -> dict:
    """Trend puani (-100..100) ve yon. Kural tabanli; AI analizi yoksa bu kullanilir."""
    c = df["close"]
    e_k, e_u = ema(c, kisa), ema(c, uzun)
    r = rsi(c)
    _, _, h = macd(c)
    son = float(c.iloc[-1])
    puan, neden = 0, []

    def ekle(kosul, artis, olumlu, olumsuz):
        nonlocal puan
        if kosul is None:
            return
        puan += artis if kosul else -artis
        neden.append(olumlu if kosul else olumsuz)

    ek, eu = float(e_k.iloc[-1]), float(e_u.iloc[-1])
    ekle(son > ek, 25, f"fiyat EMA{kisa} üstünde", f"fiyat EMA{kisa} altında")
    ekle(son > eu, 25, f"fiyat EMA{uzun} üstünde", f"fiyat EMA{uzun} altında")
    ekle(ek > eu, 20, f"EMA{kisa} > EMA{uzun}", f"EMA{kisa} < EMA{uzun}")
    geri = min(5, len(e_k) - 1)
    ekle(ek > float(e_k.iloc[-1 - geri]), 10, "kısa ortalama yükseliyor", "kısa ortalama düşüyor")
    hv = float(h.iloc[-1])
    ekle(hv > 0, 20, "MACD pozitif", "MACD negatif")
    rv = float(r.iloc[-1]) if pd.notna(r.iloc[-1]) else 50.0
    if rv >= 75:
        neden.append(f"RSI {rv:.0f}: aşırı alım, düzeltme riski")
        puan -= 10
    elif rv <= 25:
        neden.append(f"RSI {rv:.0f}: aşırı satım, tepki ihtimali")
        puan += 10
    yon = "yukari" if puan >= 30 else "asagi" if puan <= -30 else "yatay"
    return {
        "yon": yon,
        "puan": int(puan),
        "guven": int(min(85, 35 + abs(puan) * 0.5)),
        "nedenler": neden,
        "rsi": round(rv, 1),
        "macd_hist": round(hv, 3),
        f"ema{kisa}": round(ek, 2),
        f"ema{uzun}": round(eu, 2),
    }
