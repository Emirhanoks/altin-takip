import numpy as np
import pandas as pd


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
