"""Grafikler: her vade icin fiyat + ortalamalar + destek/direnc, altta RSI."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from .indicators import ema, rsi  # noqa: E402

YUZEY = "#fcfcfb"
METIN = "#0b0b0b"
METIN2 = "#52514e"
IZGARA = "#e7e6e1"
SEVIYE = "#8a8985"
FIYAT, ORT_KISA, ORT_UZUN = "#2a78d6", "#eb6834", "#1baf7a"  # sabit sira: mavi, turuncu, su yesili
TZ = "Europe/Istanbul"


def tl(x: float, ondalik: int = 0) -> str:
    return f"{x:,.{ondalik}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def ciz(df: pd.DataFrame, yol: str, baslik: str, alt_baslik: str, emalar: tuple[int, int],
        goster: int, sev: dict, tarih_bicim: str, dipnot: str, log: bool = False) -> str:
    c = df["close"]
    e1, e2, r = ema(c, emalar[0]), ema(c, emalar[1]), rsi(c)
    n = min(goster, len(df))
    c, e1, e2, r = c.iloc[-n:], e1.iloc[-n:], e2.iloc[-n:], r.iloc[-n:]
    x = np.arange(n)
    zaman = pd.DatetimeIndex(c.index).tz_convert(TZ)

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12})
    fig, (ax, ax2) = plt.subplots(
        2, 1, figsize=(12.8, 7.6), dpi=125, sharex=True,
        gridspec_kw={"height_ratios": [3.6, 1], "hspace": 0.09}, facecolor=YUZEY,
    )
    for a in (ax, ax2):
        a.set_facecolor(YUZEY)
        a.grid(axis="y", color=IZGARA, linewidth=0.8)
        a.set_axisbelow(True)
        for k in ("top", "right", "left"):
            a.spines[k].set_visible(False)
        a.spines["bottom"].set_color(IZGARA)
        a.tick_params(colors=METIN2, length=0, labelsize=11)

    (h3,) = ax.plot(x, e2.to_numpy(), color=ORT_UZUN, linewidth=1.6, label=f"EMA {emalar[1]}")
    (h2,) = ax.plot(x, e1.to_numpy(), color=ORT_KISA, linewidth=1.6, label=f"EMA {emalar[0]}")
    (h1,) = ax.plot(x, c.to_numpy(), color=FIYAT, linewidth=2.2, label="Gram altın (TL)")
    son = float(c.iloc[-1])
    ax.scatter([x[-1]], [son], s=64, color=FIYAT, edgecolor=YUZEY, linewidth=2, zorder=5)

    alt, ust = float(c.min()), float(c.max())
    if log:
        ax.set_yscale("log")
        oran = (ust / alt) ** 0.08
        y_alt, y_ust = alt / oran, ust * oran**1.8
    else:
        pay = (ust - alt) * 0.08 or son * 0.01
        y_alt, y_ust = alt - pay, ust + pay * 1.8
    ax.set_ylim(y_alt, y_ust)
    sag = n - 1 + max(3, n * 0.13)
    ax.set_xlim(-n * 0.01, sag)

    etiketler = [(son, f"{tl(son)} TL", METIN, "bold")]
    for ad, liste in (("Direnç", sev.get("direnc", [])), ("Destek", sev.get("destek", []))):
        for v in liste:
            if y_alt <= v <= y_ust:
                ax.axhline(v, color=SEVIYE, linewidth=1, linestyle=(0, (5, 4)), zorder=1)
                etiketler.append((v, f"{ad} {tl(v)}", METIN2, "normal"))
    # ust uste binen etiketleri dikeyde ayir
    etiketler.sort(key=lambda t: t[0])
    konum = []
    for v, *_ in etiketler:
        if log:
            konum.append(v if not konum else max(v, konum[-1] * (y_ust / y_alt) ** 0.045))
        else:
            konum.append(v if not konum else max(v, konum[-1] + (y_ust - y_alt) * 0.045))
    for (v, yazi, renk, kalin), y in zip(etiketler, konum):
        ax.text(n - 1 + n * 0.012, y, yazi, color=renk, fontsize=10.5, fontweight=kalin,
                va="center", ha="left", clip_on=False,
                bbox={"facecolor": YUZEY, "edgecolor": "none", "pad": 1.5})

    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: tl(v)))
    if log:
        from matplotlib.ticker import LogLocator, NullFormatter
        ax.yaxis.set_major_locator(LogLocator(base=10, subs=(1, 1.5, 2, 3, 5, 7), numticks=12))
        ax.yaxis.set_minor_formatter(NullFormatter())
        ax.tick_params(which="minor", length=0)
    ax.legend(handles=[h1, h2, h3], loc="upper left", frameon=False, ncol=3, fontsize=11, labelcolor=METIN2,
              handlelength=1.6, columnspacing=1.6, borderaxespad=0.2)
    fig.text(0.055, 0.955, baslik, fontsize=17, fontweight="bold", color=METIN, ha="left")
    fig.text(0.055, 0.915, alt_baslik, fontsize=12, color=METIN2, ha="left")

    ax2.plot(x, r.to_numpy(), color=METIN2, linewidth=1.6)
    for seviye in (30, 70):
        ax2.axhline(seviye, color=SEVIYE, linewidth=1, linestyle=(0, (5, 4)))
    ax2.set_ylim(0, 100)
    ax2.set_yticks([30, 50, 70])
    rson = float(r.dropna().iloc[-1]) if r.notna().any() else 50.0
    ax2.text(n - 1 + n * 0.012, rson, f"RSI {rson:.0f}", color=METIN, fontsize=10.5,
             fontweight="bold", va="center", ha="left")
    ax2.text(0.0, 1.04, "RSI (14) — 70 üstü aşırı alım, 30 altı aşırı satım", transform=ax2.transAxes,
             fontsize=10, color=METIN2, ha="left", va="bottom")

    adim = np.linspace(0, n - 1, 7).round().astype(int)
    ax2.set_xticks(adim)
    ax2.set_xticklabels([zaman[i].strftime(tarih_bicim) for i in adim])
    fig.text(0.055, 0.018, dipnot, fontsize=9, color=METIN2, ha="left")
    fig.subplots_adjust(left=0.075, right=0.985, top=0.875, bottom=0.085)
    fig.savefig(yol, facecolor=YUZEY)
    plt.close(fig)
    return yol
