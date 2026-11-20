"""Telegram Bot API: grafik albumu + metin."""
from __future__ import annotations

import json
import time

import requests

API = "https://api.telegram.org/bot{token}/{metod}"


class TelegramHata(RuntimeError):
    pass


def _cagri(token: str, metod: str, veri: dict | None = None, dosyalar: dict | None = None) -> dict:
    son = "bilinmiyor"
    for deneme in range(4):
        try:
            r = requests.post(API.format(token=token, metod=metod), data=veri, files=dosyalar, timeout=60)
            j = r.json()
            if j.get("ok"):
                return j
            son = f"{j.get('error_code')}: {j.get('description')}"
            bekle = (j.get("parameters") or {}).get("retry_after")
            if bekle:
                time.sleep(min(int(bekle) + 1, 30))
                continue
            if r.status_code < 500:
                break
        except requests.RequestException as e:
            son = type(e).__name__  # URL (token) sizmasin diye yalnizca tur adi
        time.sleep(3 * (deneme + 1))
    raise TelegramHata(f"Telegram {metod} basarisiz: {son}")


def tani(token: str) -> str:
    """Tanilama: bot kullanici adi, webhook var mi, bekleyen guncelleme sayisi (token yazmaz)."""
    try:
        ben = _cagri(token, "getMe").get("result", {})
        wh = _cagri(token, "getWebhookInfo").get("result", {})
        return f"@{ben.get('username')} webhook={'VAR' if wh.get('url') else 'yok'} bekleyen={wh.get('pending_update_count')}"
    except Exception as e:  # noqa: BLE001
        return f"tani hatasi: {type(e).__name__}"


def sohbetler_bul(token: str) -> list[str]:
    """Bota yazmis (veya gruba eklemis) tum sohbetlerin kimligi. Telegram bu bilgiyi ~24 saat tutar."""
    j = _cagri(token, "getUpdates", {"timeout": 0, "allowed_updates": json.dumps(["message", "channel_post", "my_chat_member"])})
    bulunan: list[str] = []
    for g in j.get("result", []):
        for anahtar in ("message", "channel_post", "my_chat_member"):
            sohbet = (g.get(anahtar) or {}).get("chat")
            if sohbet and "id" in sohbet and str(sohbet["id"]) not in bulunan:
                bulunan.append(str(sohbet["id"]))
    return bulunan


def parcala(metin: str, sinir: int = 3900) -> list[str]:
    """Telegram 4096 karakter sinirina gore, paragraf bozmadan bol."""
    parcalar, simdiki = [], ""
    for blok in metin.split("\n\n"):
        while len(blok) > sinir:
            kes = blok.rfind("\n", 0, sinir)
            kes = kes if kes > 0 else sinir
            if simdiki:
                parcalar.append(simdiki)
                simdiki = ""
            parcalar.append(blok[:kes])
            blok = blok[kes:].lstrip("\n")
        if simdiki and len(simdiki) + len(blok) + 2 > sinir:
            parcalar.append(simdiki)
            simdiki = blok
        else:
            simdiki = f"{simdiki}\n\n{blok}" if simdiki else blok
    if simdiki:
        parcalar.append(simdiki)
    return parcalar


def gonder(token: str, sohbet: str, gorseller: list[str], baslik: str, metin: str) -> None:
    if gorseller:
        medya, dosyalar, acik = [], {}, []
        try:
            for i, yol in enumerate(gorseller):
                f = open(yol, "rb")  # noqa: SIM115
                acik.append(f)
                dosyalar[f"g{i}"] = f
                oge = {"type": "photo", "media": f"attach://g{i}"}
                if i == 0:
                    oge.update({"caption": baslik[:1024], "parse_mode": "HTML"})
                medya.append(oge)
            if len(medya) == 1:
                _cagri(token, "sendPhoto", {"chat_id": sohbet, "caption": baslik[:1024], "parse_mode": "HTML"},
                       {"photo": acik[0]})
            else:
                _cagri(token, "sendMediaGroup", {"chat_id": sohbet, "media": json.dumps(medya)}, dosyalar)
        finally:
            for f in acik:
                f.close()
    for parca in parcala(metin):
        try:
            _cagri(token, "sendMessage", {"chat_id": sohbet, "text": parca, "parse_mode": "HTML",
                                          "disable_web_page_preview": "true"})
        except TelegramHata:
            import re
            duz = re.sub(r"<[^>]+>", "", parca)  # HTML bozuksa duz metin olarak gonder
            _cagri(token, "sendMessage", {"chat_id": sohbet, "text": duz, "disable_web_page_preview": "true"})
