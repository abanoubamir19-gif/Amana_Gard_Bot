import requests
import time
from datetime import datetime, timezone, timedelta
import random
import traceback
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import os

# 🛑 الإعدادات الأساسية
TELEGRAM_TOKEN = "8865376059:AAHuQB3cjCFMF03U0jQygqsENzQDKmMpQOk"
TELEGRAM_CHAT_ID = "-5584222771"
FIREBASE_URL = "https://amanagroup-a29a7-default-rtdb.firebaseio.com"

# توقيت القاهرة (UTC+2) لضمان التصفير الساعة 5 الفجر بتوقيت مصر بالظبط
CAIRO_TZ = timezone(timedelta(hours=2))

def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        print("Telegram Error:", e)

def get_json(url):
    try:
        req_headers = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
        return requests.get(url, headers=req_headers, timeout=10).json()
    except:
        return None

def put_json(url, data):
    try: requests.put(url, json=data, timeout=10)
    except: pass

def patch_json(url, data):
    try: requests.patch(url, json=data, timeout=10)
    except: pass

def delete_json(url):
    try: requests.delete(url, timeout=10)
    except: pass

def start_monitor():
    print("🚀 بدء تشغيل المراقب الذكي يعمل الآن 24/7...")
    send_telegram_alert("🤖 تم تشغيل سيرفر المراقبة الذكي (مجوهرات الأمانة) بنجاح ويعمل الآن 24/7.")
    client_device_id = f"render_server_{int(time.time())}_{random.randint(1000, 9999)}"
    
    while True:
        try:
            dashboard_data = get_json(f"{FIREBASE_URL}/LiveDashboard.json") or {}
            if not isinstance(dashboard_data, dict): dashboard_data = {}
            
            global_memory = get_json(f"{FIREBASE_URL}/Global_Last_Cash.json") or {}
            if not isinstance(global_memory, dict): global_memory = {}
            
            closed_branches_db = get_json(f"{FIREBASE_URL}/Closed_Branches.json") or {}
            if not isinstance(closed_branches_db, dict): closed_branches_db = {}
            
            # 1. تصفير الكاش يومياً الساعة 5 الفجر بتوقيت مصر
            now_dt = datetime.now(CAIRO_TZ)
            today_str = now_dt.strftime("%Y-%m-%d")
            if now_dt.hour == 5 and now_dt.minute <= 5:
                check_sent = get_json(f"{FIREBASE_URL}/System_Flags/Report_{today_str}.json")
                if not check_sent:
                    put_json(f"{FIREBASE_URL}/System_Flags/Report_{today_str}.json", {"sent": True})
                    delete_json(f"{FIREBASE_URL}/Global_Last_Cash.json")
                    delete_json(f"{FIREBASE_URL}/Closed_Branches.json")
                    put_json(f"{FIREBASE_URL}/System_Flags/Last_Alert_Level.json", 0)
                    global_memory.clear()
                    closed_branches_db.clear()
                    send_telegram_alert("🔄 تم تصفير الكاش وبدء يوم عمل جديد بنجاح (الساعة 5 فجراً).")
            
            total_cash_val = 0.0
            branch_cash_diffs = {}
            
            # 2. التحديث التلقائي وتقفيل الفروع
            for branch_name, info in dashboard_data.items():
                if not isinstance(info, dict): continue
                try:
                    raw_c = float(str(info.get('Cash', '0')).replace(',', ''))
                except:
                    raw_c = 0.0
                
                server_last_c = float(global_memory.get(branch_name, 0.0))
                actual_c = raw_c
                
                if raw_c > 0:
                    if branch_name in closed_branches_db:
                        delete_json(f"{FIREBASE_URL}/Closed_Branches/{branch_name}.json")
                        closed_branches_db.pop(branch_name, None)
                    if actual_c != server_last_c:
                        patch_json(f"{FIREBASE_URL}/Global_Last_Cash.json", {branch_name: actual_c})
                        branch_cash_diffs[branch_name] = actual_c - server_last_c
                elif raw_c == 0:
                    if branch_name in closed_branches_db:
                        actual_c = float(closed_branches_db[branch_name])
                    elif server_last_c > 0:
                        put_json(f"{FIREBASE_URL}/System_Flags/Close_Lock_{branch_name}.json", client_device_id)
                        time.sleep(0.5)
                        lock_check = get_json(f"{FIREBASE_URL}/System_Flags/Close_Lock_{branch_name}.json")
                        if lock_check == client_device_id:
                            patch_json(f"{FIREBASE_URL}/Closed_Branches.json", {branch_name: server_last_c})
                            closed_branches_db[branch_name] = server_last_c
                            send_telegram_alert(f"✅ تم التقفيل بنجاح\n🏢 الفرع: {branch_name}\n💰 اخر جرد: {server_last_c:,.2f} ج.م")
                        actual_c = server_last_c
                    else:
                        actual_c = 0.0
                        
                total_cash_val += actual_c

            # 3. مراقبة حواجز الـ 100 ألف وإرسال تنبيهات التليجرام
            fb_alert_level = get_json(f"{FIREBASE_URL}/System_Flags/Last_Alert_Level.json")
            if not isinstance(fb_alert_level, int): fb_alert_level = 0
            
            current_level = int(total_cash_val // 100000)
            if current_level != fb_alert_level and total_cash_val > 0:
                time.sleep(random.uniform(0.1, 1.0))
                fb_check_again = get_json(f"{FIREBASE_URL}/System_Flags/Last_Alert_Level.json")
                if not isinstance(fb_check_again, int): fb_check_again = fb_alert_level
                
                if fb_check_again == fb_alert_level:
                    put_json(f"{FIREBASE_URL}/System_Flags/Alert_Lock.json", client_device_id)
                    time.sleep(0.5)
                    lock_check = get_json(f"{FIREBASE_URL}/System_Flags/Alert_Lock.json")
                    if lock_check == client_device_id:
                        put_json(f"{FIREBASE_URL}/System_Flags/Last_Alert_Level.json", current_level)
                        boundary = max(current_level, fb_alert_level) * 100000
                        direction = "صعد وتخطى" if current_level > fb_alert_level else "نزل عن"
                        
                        trigger_branch = "غير معروف"
                        trigger_amount = 0
                        if branch_cash_diffs:
                            if current_level > fb_alert_level:
                                trigger_branch = max(branch_cash_diffs, key=branch_cash_diffs.get)
                            else:
                                trigger_branch = min(branch_cash_diffs, key=branch_cash_diffs.get)
                            trigger_amount = branch_cash_diffs[trigger_branch]
                            
                        msg = f"🚨 تنبيه جرد عاجل 🚨\n"
                        msg += f"إجمالي الكاش {direction} حاجز الـ {boundary:,.0f} ج.م!\n\n"
                        msg += f"💰 الإجمالي الكلي الحالي: {total_cash_val:,.2f} ج.م\n"
                        if trigger_amount != 0:
                            change_dir = "أضاف" if trigger_amount > 0 else "سحب"
                            msg += f"الفرع: 🏢 {trigger_branch} ({change_dir} {abs(trigger_amount):,.0f} ج.م)"
                        send_telegram_alert(msg)
                        
        except Exception as e:
            traceback.print_exc()
            
        time.sleep(5)

# =========================================================================
# بوابة ويب خفيفة جداً ترد في جزء من الثانية عشان Render يفضل صاحي ومجاني
# =========================================================================
class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(b"OK - Amana Server is Alive")
        
    def log_message(self, format, *args):
        return

if __name__ == "__main__":
    # تشغيل المراقب في الخلفية 24/7
    bot_thread = threading.Thread(target=start_monitor, daemon=True)
    bot_thread.start()
    
    # فتح البورت عشان Render يشتغل كـ Web Service مجاني
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), KeepAliveHandler)
    server.serve_forever()