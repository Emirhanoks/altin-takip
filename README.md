# Altın Takip

3 saatte bir Telegram'a gram altın raporu gönderir: fiyat, kısa/orta/uzun vadeli görünüm,
üç grafik, haberler, trader ve kurum görüşleri, takvim ve tahmin karnesi.

## Nasıl çalışır

1. **Analiz:** Zamanlanmış Claude görevi 3 saatte bir haberleri ve yorumları tarar,
   `analiz/latest.json` dosyasını yazıp gönderir (`ANALIZ_TALIMATI.md`).
2. **Rapor:** Bu push, `.github/workflows/rapor.yml` otomasyonunu tetikler. Otomasyon fiyat verisini
   çeker (ons altın vadeli × USD/TRY ÷ 31,1035), göstergeleri hesaplar, grafikleri çizer ve
   Telegram'a gönderir.
3. **Yedek:** Otomasyon saat başı 17 geçe kontrol eder; son rapordan 215 dakikadan fazla geçtiyse
   yalnızca teknik verilerle rapor gönderir.
4. **Karne:** Her tahmin `durum/tahminler.json` içine yazılır; kısa vade 24 saat, orta vade 14 gün,
   uzun vade 90 gün sonra puanlanır.

## Kurulum

- Repo secret: `TELEGRAM_BOT_TOKEN` (Settings → Secrets and variables → Actions).
- Telegram'da bota bir kez `/start` yazın; sohbet kimliği ilk çalışmada bulunup
  `durum/durum.json` içine kaydedilir. İsterseniz `TELEGRAM_CHAT_ID` secret'ı ile sabitleyin.
- Elle çalıştırma: Actions → Altın Raporu → Run workflow.

## Yerelde deneme

```
pip install -r requirements.txt
KURU_CALISMA=1 python -m tests.sentetik   # ağ olmadan; cikti/ altına grafik ve mesaj yazar
```

Sorun olursa `durum/son_calisma.json` son çalışmanın sonucunu ve hata iletisini gösterir.

Bilgi amaçlıdır, yatırım tavsiyesi değildir.
