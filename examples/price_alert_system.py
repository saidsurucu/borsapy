"""
Fiyat Alarmı Sistemi
====================

Belirlenen fiyat seviyelerine ulaşınca uyarı veren sistem.

Alarm Tipleri:
- Fiyat üstüne çıkınca (breakout)
- Fiyat altına düşünce (breakdown)
- Yüzde değişim eşiği

Kullanım:
    python examples/price_alert_system.py

Not: Ctrl+C ile durdurun.
"""

import time
from datetime import datetime
from dataclasses import dataclass

import borsapy as bp


@dataclass
class Alert:
    """Fiyat alarmı."""
    symbol: str
    alert_type: str  # 'above', 'below', 'change_up', 'change_down'
    target: float
    message: str = ""
    triggered: bool = False
    triggered_at: datetime | None = None
    triggered_price: float | None = None


class AlertSystem:
    """Fiyat alarm sistemi."""

    def __init__(self):
        self.alerts: list[Alert] = []
        self.stream: bp.TradingViewStream | None = None
        self.triggered_alerts: list[Alert] = []

    def add_alert(
        self,
        symbol: str,
        alert_type: str,
        target: float,
        message: str = "",
    ) -> Alert:
        """
        Alarm ekle.

        Args:
            symbol: Hisse sembolü
            alert_type: 'above', 'below', 'change_up', 'change_down'
            target: Hedef fiyat veya yüzde
            message: Özel mesaj
        """
        alert = Alert(
            symbol=symbol,
            alert_type=alert_type,
            target=target,
            message=message,
        )
        self.alerts.append(alert)
        return alert

    def add_breakout_alert(self, symbol: str, price: float, message: str = ""):
        """Fiyat belirli seviyenin üstüne çıkınca alarm."""
        return self.add_alert(symbol, 'above', price, message or f"{symbol} {price} üstüne çıktı!")

    def add_breakdown_alert(self, symbol: str, price: float, message: str = ""):
        """Fiyat belirli seviyenin altına düşünce alarm."""
        return self.add_alert(symbol, 'below', price, message or f"{symbol} {price} altına düştü!")

    def add_change_alert(self, symbol: str, percent: float, message: str = ""):
        """Günlük değişim eşiği alarmı."""
        if percent > 0:
            return self.add_alert(symbol, 'change_up', percent,
                                  message or f"{symbol} %{percent}+ yükseldi!")
        else:
            return self.add_alert(symbol, 'change_down', abs(percent),
                                  message or f"{symbol} %{abs(percent)}+ düştü!")

    def check_alerts(self) -> list[Alert]:
        """Tüm alarmları kontrol et."""
        newly_triggered = []

        for alert in self.alerts:
            if alert.triggered:
                continue

            quote = self.stream.get_quote(alert.symbol)
            if quote is None:
                continue

            price = quote.get('last', 0)
            change_pct = quote.get('change_percent', 0)

            triggered = False

            if alert.alert_type == 'above' and price >= alert.target:
                triggered = True
            elif alert.alert_type == 'below' and price <= alert.target:
                triggered = True
            elif alert.alert_type == 'change_up' and change_pct >= alert.target:
                triggered = True
            elif alert.alert_type == 'change_down' and change_pct <= -alert.target:
                triggered = True

            if triggered:
                alert.triggered = True
                alert.triggered_at = datetime.now()
                alert.triggered_price = price
                newly_triggered.append(alert)
                self.triggered_alerts.append(alert)

        return newly_triggered

    def connect(self):
        """Stream'e bağlan."""
        self.stream = bp.TradingViewStream()
        self.stream.connect()

        # Tüm alarm sembollerine abone ol
        symbols = set(a.symbol for a in self.alerts)
        for symbol in symbols:
            self.stream.subscribe(symbol)

    def disconnect(self):
        """Bağlantıyı kapat."""
        if self.stream:
            self.stream.disconnect()

    def print_status(self):
        """Alarm durumunu göster."""
        print("\n📋 AKTİF ALARMLAR:")
        print("-" * 70)

        active = [a for a in self.alerts if not a.triggered]
        if not active:
            print("   Aktif alarm yok.")
        else:
            for alert in active:
                quote = self.stream.get_quote(alert.symbol) if self.stream else None
                current = quote.get('last', 0) if quote else 0

                type_icon = {
                    'above': '↗️ ',
                    'below': '↘️ ',
                    'change_up': '📈',
                    'change_down': '📉',
                }.get(alert.alert_type, '⚡')

                print(f"   {type_icon} {alert.symbol:<8} Hedef: {alert.target:>10.2f} "
                      f"| Güncel: {current:>10.2f} | {alert.message}")

        print()
        print("🔔 TETİKLENEN ALARMLAR:")
        print("-" * 70)

        if not self.triggered_alerts:
            print("   Henüz tetiklenen alarm yok.")
        else:
            for alert in self.triggered_alerts[-10:]:  # Son 10
                time_str = alert.triggered_at.strftime("%H:%M:%S") if alert.triggered_at else "N/A"
                print(f"   🚨 [{time_str}] {alert.symbol}: {alert.message} "
                      f"(Fiyat: {alert.triggered_price:.2f})")


def run_alert_system(alerts: AlertSystem, check_interval: float = 2.0, duration: int = 120):
    """Alarm sistemini çalıştır."""

    print("🚀 Alarm sistemi başlatılıyor...")
    alerts.connect()
    print(f"✅ {len(alerts.alerts)} alarm aktif")
    print()

    time.sleep(3)  # İlk verilerin gelmesini bekle

    start_time = time.time()

    try:
        while True:
            elapsed = time.time() - start_time

            if duration > 0 and elapsed > duration:
                break

            # Alarmları kontrol et
            triggered = alerts.check_alerts()

            # Tetiklenen alarmları göster
            for alert in triggered:
                print()
                print("🚨" * 20)
                print(f"🔔 ALARM TETİKLENDİ!")
                print(f"   Sembol: {alert.symbol}")
                print(f"   Mesaj: {alert.message}")
                print(f"   Fiyat: {alert.triggered_price:.2f}")
                print(f"   Zaman: {alert.triggered_at.strftime('%H:%M:%S')}")
                print("🚨" * 20)
                print()

            # Durum göster
            print("\033[H\033[J", end="")  # Ekranı temizle
            print("=" * 70)
            print(f"⏰ FİYAT ALARM SİSTEMİ | {datetime.now().strftime('%H:%M:%S')}")
            print("=" * 70)

            alerts.print_status()

            print()
            print(f"⏱️  Çalışma süresi: {int(elapsed)}s")
            if duration > 0:
                print(f"⏳ Kalan süre: {duration - int(elapsed)}s")
            print("📌 Durdurmak için Ctrl+C")

            time.sleep(check_interval)

    except KeyboardInterrupt:
        print()
        print("🛑 Alarm sistemi durduruldu.")

    finally:
        alerts.disconnect()
        print("✅ Bağlantı kapatıldı.")

        # Özet
        print()
        print("📊 ÖZET:")
        print(f"   Toplam alarm: {len(alerts.alerts)}")
        print(f"   Tetiklenen: {len(alerts.triggered_alerts)}")


def main():
    print("=" * 70)
    print("borsapy - Fiyat Alarm Sistemi")
    print("=" * 70)
    print()

    # Alarm sistemi oluştur
    system = AlertSystem()

    # Örnek alarmlar ekle
    print("📝 Örnek alarmlar ekleniyor...")

    # Fiyat seviyeleri (örnek değerler - güncel fiyatlara göre ayarlayın)
    system.add_breakout_alert("THYAO", 310.0, "THYAO 310 direncini kırdı!")
    system.add_breakdown_alert("THYAO", 280.0, "THYAO 280 desteğini kaybetti!")

    system.add_breakout_alert("GARAN", 130.0, "GARAN 130 üstünde!")
    system.add_breakdown_alert("GARAN", 115.0, "GARAN 115 altında!")

    # Yüzde değişim alarmları
    system.add_change_alert("ASELS", 3.0, "ASELS %3+ yükseldi!")
    system.add_change_alert("ASELS", -3.0, "ASELS %3+ düştü!")

    system.add_change_alert("TUPRS", 2.5, "TUPRS %2.5+ yükseldi!")

    print(f"✅ {len(system.alerts)} alarm eklendi")
    print()

    # Sistemi çalıştır (2 dakika demo)
    run_alert_system(
        system,
        check_interval=2.0,
        duration=120,  # 2 dakika (0=sonsuz)
    )

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
