"""Telegram mesaj metni (HTML)."""
from __future__ import annotations

import datetime as dt
import html
from zoneinfo import ZoneInfo

from .charts import tl

TZ = ZoneInfo("Europe/Istanbul")
YON = {"yukari": "▲ Yukarı", "asagi": "▼ Aşağı", "yatay": "◆ Yatay"}
ETKI = {"pozitif": "🟢", "negatif": "🔴", "notr": "⚪"}


def e(s, sinir: int | None = None) -> str:
    s = " ".join(str(s or "").split())
    if sinir and len(s) > sinir:
        s = s[: sinir - 1].rstrip() + "…"
    return html.escape(s, quote=False)


def yuzde(x) -> str:
    if x is None:
        return "–"
    return f"{'+' if x >= 0 else '−'}%{abs(x):.2f}".replace(".", ",")


def baslik(p: dict) -> str:
    z = dt.datetime.fromisoformat(p["zaman"]).astimezone(TZ)
    d = p["degisim"]
    return (
        f"🟡 <b>GRAM ALTIN — {tl(p['gram'], 2)} TL</b>\n"
        f"{z:%d.%m.%Y %H:%M} · 3s {yuzde(d.get('3s'))} · 24s {yuzde(d.get('24s'))} · 7g {yuzde(d.get('7g'))}\n"
        "Grafikler: kısa (saatlik), orta (günlük), uzun (haftalık)"
    )


def metin(p: dict, analiz: dict | None, karne: dict, teknik: dict) -> str:
    d = p["degisim"]
    b = []
    fiyat = [
        "💰 <b>Fiyat</b>",
        f"Gram altın: <b>{tl(p['gram'], 2)} TL</b>",
        f"Ons: {tl(p['ons'], 2)} $ · USD/TRY: {tl(p['kur'], 4)}",
        f"Değişim: 3s {yuzde(d.get('3s'))} · 24s {yuzde(d.get('24s'))} · 7g {yuzde(d.get('7g'))} · "
        f"30g {yuzde(d.get('30g'))} · 1y {yuzde(d.get('1y'))}",
    ]
    k = p.get("kapalicarsi")
    if k:
        fark = (k["satis"] / p["gram"] - 1) * 100
        fiyat.append(f"Serbest piyasa: alış {tl(k['alis'], 2)} / satış {tl(k['satis'], 2)} TL "
                     f"(hesaplanan fiyata göre {yuzde(fark)})")
    if p.get("piyasa_kapali"):
        fiyat.append("ℹ️ Uluslararası piyasa şu an kapalı; fiyat son kapanışa göredir.")
    b.append("\n".join(fiyat))

    if analiz and analiz.get("ozet"):
        b.append(f"🧭 <b>Özet</b>\n{e(analiz['ozet'], 700)}")

    vadeler = ["📊 <b>Görünüm</b>"]
    for anahtar, ad in (("kisa", "Kısa vade (1-3 gün)"), ("orta", "Orta vade (2-6 hafta)"), ("uzun", "Uzun vade (3-12 ay)")):
        t = teknik[anahtar]
        a = ((analiz or {}).get("vadeler") or {}).get(anahtar) or {}
        yon = a.get("yon") if a.get("yon") in YON else t["yon"]
        guven = a.get("guven") if isinstance(a.get("guven"), (int, float)) else t["guven"]
        satir = [f"<b>{ad}: {YON[yon]}</b> · güven %{int(guven)}"]
        if a.get("yorum"):
            satir.append(e(a["yorum"], 450))
        else:
            satir.append("Teknik: " + e(", ".join(t["nedenler"][:4])))
        if a.get("yon") in YON and a["yon"] != t["yon"]:
            satir.append(f"<i>Not: teknik göstergeler {YON[t['yon']].lower()} diyor (puan {t['puan']}).</i>")
        s = t["seviyeler"]
        satir.append(f"Destek: {' / '.join(tl(x) for x in s['destek'])} · "
                     f"Direnç: {' / '.join(tl(x) for x in s['direnc'])}"
                     f"{' (tahmini)' if s.get('direnc_projeksiyon') else ''} · RSI {t['rsi']:.0f}")
        for etiket, alan in (("Hedef", "hedef"), ("Görüş bozulur", "iptal")):
            if a.get(alan):
                satir.append(f"{etiket}: {e(a[alan], 160)}")
        vadeler.append("\n".join(satir))
    b.append("\n\n".join(vadeler))

    if analiz:
        if analiz.get("ana_senaryo"):
            s = f"🎯 <b>Senaryolar</b>\n<b>Ana:</b> {e(analiz['ana_senaryo'], 500)}"
            if analiz.get("alternatif_senaryo"):
                s += f"\n<b>Alternatif:</b> {e(analiz['alternatif_senaryo'], 400)}"
            b.append(s)
        haberler = [h for h in (analiz.get("haberler") or []) if isinstance(h, dict) and h.get("baslik")][:7]
        if haberler:
            satirlar = ["📰 <b>Haberler ve etkisi</b>"]
            for h in haberler:
                url = str(h.get("url") or "")
                kaynak = e(h.get("kaynak") or "kaynak", 40)
                if url.startswith("http"):
                    kaynak = f'<a href="{html.escape(url, quote=True)}">{kaynak}</a>'
                satirlar.append(f"{ETKI.get(h.get('etki'), '⚪')} <b>{e(h['baslik'], 140)}</b> ({kaynak})"
                                + (f"\n{e(h['yorum'], 260)}" if h.get("yorum") else ""))
            b.append("\n".join(satirlar))
        gorusler = [g for g in (analiz.get("trader_gorusleri") or []) if isinstance(g, dict) and g.get("gorus")][:6]
        if gorusler:
            satirlar = ["👥 <b>Trader ve kurum görüşleri</b>"]
            for g in gorusler:
                satirlar.append(f"• <b>{e(g.get('kim') or 'Analist', 60)}:</b> {e(g['gorus'], 260)}")
            b.append("\n".join(satirlar))
        takvim = [t for t in (analiz.get("takvim") or []) if isinstance(t, dict) and t.get("olay")][:6]
        if takvim:
            b.append("🗓 <b>Takvim</b>\n" + "\n".join(
                f"• {e(t.get('zaman'), 40)} — {e(t['olay'], 140)}" for t in takvim))
        riskler = [r for r in (analiz.get("riskler") or []) if r][:5]
        if riskler:
            b.append("⚠️ <b>Riskler</b>\n" + "\n".join(f"• {e(r, 200)}" for r in riskler))
    else:
        b.append("ℹ️ Bu turda haber/yorum analizi hazır değildi; rapor yalnızca teknik verilerle gönderildi.")

    bag = p.get("baglam") or {}
    adlar = {"dolar_endeksi": "DXY", "abd_10y_faiz": "ABD 10Y", "gumus_ons": "Gümüş", "brent": "Brent", "vix": "VIX"}
    parcalar = [f"{ad} {tl(bag[k]['son'], 2)} ({yuzde(bag[k]['gunluk_degisim_yuzde'])})" for k, ad in adlar.items() if k in bag]
    if parcalar:
        b.append("🌐 <b>Yan göstergeler</b>\n" + " · ".join(parcalar))

    satirlar = []
    for anahtar, ad in (("kisa", "Kısa"), ("orta", "Orta"), ("uzun", "Uzun")):
        ks = karne.get(anahtar) or {}
        if ks.get("toplam"):
            satirlar.append(f"{ad}: {ks['dogru']}/{ks['toplam']} (%{round(100 * ks['dogru'] / ks['toplam'])})")
    b.append("📈 <b>Tahmin karnesi</b>\n" + (" · ".join(satirlar) if satirlar
             else "Henüz değerlendirilen tahmin yok; ilk sonuçlar 24 saat sonra."))
    b.append("<i>Bilgi amaçlıdır, yatırım tavsiyesi değildir. Fiyat, ons vadeli × USD/TRY ile hesaplanır; "
             "kuyumcu fiyatlarından farklı olabilir.</i>")
    return "\n\n".join(b)
