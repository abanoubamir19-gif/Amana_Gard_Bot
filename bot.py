import requests
import time
from datetime import datetime
import random
import traceback

# 🛑 الإعدادات الأساسية
TELEGRAM_TOKEN = "8865376059:AAHuQB3cjCFMF03U0jQygqsENzQDKmMpQOk"
TELEGRAM_CHAT_ID = "-5584222771"
FIREBASE_URL = "https://amanagroup-a29a7-default-rtdb.firebaseio.com"

def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        print("Telegram Error:", e)

def get_json(url):
    try: return requests.get(url, timeout=10).json()
    except: return None

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
    print("🚀 بدء تشغيل المراقب الذكي لـ (مجوهرات الأمانة) يعمل الآن 24/7...")
    send_telegram_alert("🤖 المراقب الذكي بدأ العمل الآن. سيتم مراقبة الجرد وإرسال التنبيهات المهمة تلقائياً.")
    
    client_device_id = f"server_bot_{int(time.time())}"
    
    while True:
        try:
            # 1. سحب البيانات المباشرة
            dashboard_data = get_json(f"{FIREBASE_URL}/LiveDashboard.json") or {}
            if not isinstance(dashboard_data, dict): dashboard_data = {}
            
            global_memory = get_json(f"{FIREBASE_URL}/Global_Last_Cash.json") or {}
            if not isinstance(global_memory, dict): global_memory = {}
            
            closed_branches = get_json(f"{FIREBASE_URL}/Closed_Branches.json") or {}
            if not isinstance(closed_branches, dict): closed_branches = {}
            
            # 2. تصفير الكاش يومياً الساعة 5 الفجر
            now_dt = datetime.now()
            today_str = now_dt.strftime("%Y-%m-%d")
            if now_dt.hour == 5 and now_dt.minute <= 5:
                check_sent = get_json(f"{FIREBASE_URL}/System_Flags/Report_{today_str}.json")
                if not check_sent:
                    put_json(f"{FIREBASE_URL}/System_Flags/Report_{today_str}.json", {"sent": True})
                    delete_json(f"{FIREBASE_URL}/Global_Last_Cash.json")
                    delete_json(f"{FIREBASE_URL}/Closed_Branches.json")
                    put_json(f"{FIREBASE_URL}/System_Flags/Last_Alert_Level.json", 0)
                    global_memory.clear()
                    closed_branches.clear()
                    send_telegram_alert("🔄 تم تصفير الكاش وبدء يوم عمل جديد بنجاح (الساعة 5 فجراً).")
            
            total_cash_val = 0.0
            branch_cash_diffs = {}
            
            # 3. مراقبة الفروع (إغلاق الفروع فقط بدون إزعاج التأخيرات)
            for branch_name, info in dashboard_data.items():
                if not isinstance(info, dict): continue
                
                try: raw_c = float(str(info.get('Cash', '0')).replace(',', ''))
                except: raw_c = 0.0
                
                server_last_c = float(global_memory.get(branch_name, 0.0))
                actual_c = raw_c
                
                # إغلاق الفرع و الإشعارات
                if raw_c > 0:
                    if branch_name in closed_branches:
                        delete_json(f"{FIREBASE_URL}/Closed_Branches/{branch_name}.json")
                    if actual_c != server_last_c:
                        patch_json(f"{FIREBASE_URL}/Global_Last_Cash.json", {branch_name: actual_c})
                        branch_cash_diffs[branch_name] = actual_c - server_last_c
                elif raw_c == 0:
                    if branch_name in closed_branches:
                        actual_c = float(closed_branches[branch_name])
                    elif server_last_c > 0:
                        put_json(f"{FIREBASE_URL}/System_Flags/Close_Lock_{branch_name}.json", client_device_id)
                        time.sleep(0.5)
                        if get_json(f"{FIREBASE_URL}/System_Flags/Close_Lock_{branch_name}.json") == client_device_id:
                            patch_json(f"{FIREBASE_URL}/Closed_Branches.json", {branch_name: server_last_c})
                            send_telegram_alert(f"✅ تم التقفيل بنجاح\n🏢 الفرع: {branch_name}\n💰 اخر جرد: {server_last_c:,.2f} ج.م")
                        actual_c = server_last_c
                
                total_cash_val += actual_c

            # 4. مراقبة كسر حواجز الكاش (كل 100 ألف)
            fb_alert_level = get_json(f"{FIREBASE_URL}/System_Flags/Last_Alert_Level.json")
            if not isinstance(fb_alert_level, int): fb_alert_level = 0
            
            current_level = int(total_cash_val // 100000)
            if current_level != fb_alert_level and total_cash_val > 0:
                time.sleep(random.uniform(0.1, 1.0))
                if get_json(f"{FIREBASE_URL}/System_Flags/Last_Alert_Level.json") == fb_alert_level:
                    put_json(f"{FIREBASE_URL}/System_Flags/Alert_Lock.json", client_device_id)
                    time.sleep(0.5)
                    if get_json(f"{FIREBASE_URL}/System_Flags/Alert_Lock.json") == client_device_id:
                        put_json(f"{FIREBASE_URL}/System_Flags/Last_Alert_Level.json", current_level)
                        
                        boundary = max(current_level, fb_alert_level) * 100000
                        direction = "صعد وتخطى" if current_level > fb_alert_level else "نزل عن"
                        
                        trigger_branch = "غير معروف"
                        trigger_amount = 0
                        if branch_cash_diffs:
                            trigger_branch = max(branch_cash_diffs, key=branch_cash_diffs.get) if current_level > fb_alert_level else min(branch_cash_diffs, key=branch_cash_diffs.get)
                            trigger_amount = branch_cash_diffs[trigger_branch]
                            
                        msg = f"🚨 تنبيه جرد عاجل 🚨\nإجمالي الكاش {direction} حاجز الـ {boundary:,.0f} ج.م!\n\n💰 الإجمالي الكلي الحالي: {total_cash_val:,.2f} ج.م\n"
                        if trigger_amount != 0:
                            msg += f"الفرع المتسبب: 🏢 {trigger_branch} ({'أضاف' if trigger_amount > 0 else 'سحب'} {abs(trigger_amount):,.0f} ج.م)"
                        
                        send_telegram_alert(msg)
                        
        except Exception as e:
            print(f"Monitor Loop Error: {e}")
            traceback.print_exc()

        # انتظار 5 ثواني قبل فحص السيرفر مرة أخرى
        time.sleep(5)

if __name__ == "__main__":
    start_monitor()