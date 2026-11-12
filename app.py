import json
import urllib.request

def get_crypto_signal():
    print("=" * 40)
    print("🚀 جاري الاتصال المباشر وفحص سوق Binance...")
    print("=" * 40)
    
    url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=20"
    
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            
        # استخراج الأسعار (سعر الإغلاق لكل شمعة هو العنصر رقم 4)
        closes = [float(candle[4]) for candle in data]
        current_price = closes[-1]
        prev_price = closes[-2]
        
        # حساب التغير البسيط
        change = ((current_price - prev_price) / prev_price) * 100
        
        print(f"\n📊 زوج العملة: BTC/USDT")
        print(f"💵 السعر الحالي: ${current_price:,.2f}")
        print(f"📈 التغير الحالي: {change:.2f}%")
        print("-" * 40)
        
        if change >= 0:
            print("📌 التوصية: LONG 🟢 (اتجاه صاعد)")
            print(f"🛑 وقف الخسارة: ${current_price * 0.985:,.2f}")
            print(f"🎯 الهدف المقترح: ${current_price * 1.015:,.2f}")
        else:
            print("📌 التوصية: SHORT 🔴 (اتجاه هابط)")
            print(f"🛑 وقف الخسارة: ${current_price * 1.015:,.2f}")
            print(f"🎯 الهدف المقترح: ${current_price * 0.985:,.2f}")
            
        print("=" * 40)

    except Exception as e:
        print(f"❌ حدث خطأ في الاتصال بالشبكة: {e}")

if __name__ == "__main__":
    get_crypto_signal()
