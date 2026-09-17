import streamlit as st
import requests
import json
import base64
from datetime import datetime, timedelta
from PIL import Image
import io
import os

# Page configuration for mobile-friendly UI
st.set_page_config(
    page_title="متتبع السعرات بالكاميرا",
    page_icon="📸",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Custom CSS for Mobile & Arabic RTL layout (Clean, spacious, no sidebar)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
    
    * {
        font-family: 'Cairo', sans-serif !important;
    }
    
    .stApp {
        direction: rtl !important;
        text-align: right !important;
    }
    
    /* Hide sidebar and hamburger menu completely on mobile */
    [data-testid="stSidebar"], [data-testid="collapsedControl"] {
        display: none !important;
    }
    
    /* Spacious metric boxes for mobile */
    div[data-testid="stMetric"] {
        background: #f8f9fa;
        padding: 12px 14px;
        border-radius: 12px;
        border: 1px solid #e9ecef;
        text-align: center;
        margin-bottom: 8px;
    }
    
    div[data-testid="stMetricLabel"] {
        justify-content: center !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
    }
    
    div[data-testid="stMetricValue"] {
        font-size: 1.45rem !important;
        justify-content: center !important;
    }
    
    .meal-card {
        background: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 14px;
        margin-bottom: 10px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.03);
    }
    
    .log-day-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 14px;
        margin-bottom: 10px;
    }
    
    .macro-badge {
        display: inline-block;
        padding: 4px 9px;
        border-radius: 18px;
        font-size: 0.82rem;
        font-weight: 600;
        margin-left: 5px;
        margin-top: 4px;
    }
    .badge-cal { background: #ffe3e3; color: #c92a2a; }
    .badge-pro { background: #e7f5ff; color: #1864ab; }
    .badge-carb { background: #fff3bf; color: #e67700; }
    .badge-fat { background: #e6fcf5; color: #087f5b; }
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        justify-content: center;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 1rem !important;
        font-weight: 700 !important;
        padding: 8px 16px !important;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- Data Persistence (Local JSON Database) -----------------
DATA_FILE = "meals_history.json"

def load_all_history():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_all_history(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"خطأ أثناء حفظ البيانات: {e}")

# Helper: Get API Key
def get_api_key():
    if "GOOGLE_AI_API_KEY" in st.secrets:
        return st.secrets["GOOGLE_AI_API_KEY"]
    if "api_key" in st.session_state and st.session_state["api_key"]:
        return st.session_state["api_key"]
    return os.environ.get("GOOGLE_AI_API_KEY", "")

# Helper: Call Gemini Vision API
def analyze_food_image(image_bytes: bytes, api_key: str):
    base64_img = base64.b64encode(image_bytes).decode("utf-8")
    models = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.1-flash-lite"]
    
    prompt = """
    أنت خبير تغذية متخصص في حساب السعرات ومكونات الطعام.
    حلل هذه الصورة واكتشف نوع الوجبة أو الأطعمة الموجودة بدقة.
    قدّر وزنها التقريبي، ثم احسب بدقة:
    1. السعرات الحرارية (calories)
    2. البروتين بالجرام (protein)
    3. الكربوهيدرات بالجرام (carbs)
    4. الدهون بالجرام (fat)
    
    يجب أن تكون إجابتك بصيغة JSON صالحة حصراً بدون أي كود إضافي كالتالي:
    {
      "name": "اسم الوجبة بالعربي (مثال: صدر دجاج مشوي مع أرز وسلطة)",
      "calories": 450,
      "protein": 42,
      "carbs": 50,
      "fat": 10,
      "notes": "تفصيل سريع للمكونات المقدرة"
    }
    إذا لم تكن هناك وجبة طعام في الصورة، اكتب في name: "لم يتم التعرف على طعام" واجعل الأرقام 0.
    """
    
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": base64_img
                        }
                    }
                ]
            }
        ]
    }
    
    last_error = ""
    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            res = requests.post(url, headers={"Content-Type": "application/json"}, json=body, timeout=25)
            if res.status_code == 200:
                data = res.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                start = text.find("{")
                end = text.rfind("}") + 1
                if start != -1 and end != -1:
                    return json.loads(text[start:end])
            else:
                last_error = f"Model {model} returned {res.status_code}: {res.text}"
        except Exception as e:
            last_error = str(e)
            continue
            
    raise Exception(f"فشل التحليل عبر جميع النماذج: {last_error}")

# Load master database into session state
if "history" not in st.session_state:
    st.session_state.history = load_all_history()

# Default Macro Goals (2905 kcal, 182g Protein, 363g Carbs, 81g Fat)
DEFAULT_GOAL = {
    "calories": 2905,
    "protein": 182,
    "carbs": 363,
    "fat": 81
}

if "daily_goal" not in st.session_state:
    st.session_state.daily_goal = DEFAULT_GOAL.copy()

today_str = datetime.now().strftime("%Y-%m-%d")

# Initialize today's entry if missing
if today_str not in st.session_state.history:
    st.session_state.history[today_str] = {
        "date": today_str,
        "is_closed": False,
        "goal": st.session_state.daily_goal.copy(),
        "meals": []
    }
    save_all_history(st.session_state.history)

today_record = st.session_state.history[today_str]

# App Header
st.title("📸 متتبع السعرات بالكاميرا")
st.caption("صوّر وجبتك بكاميرا جوالك أو ارفع صورتها لحساب السعرات والماكروز مباشرة")

# Main Navigation Tabs
tab_today, tab_week, tab_month = st.tabs(["🔥 اليوم", "📅 سجل الأسبوع (7 أيام)", "🗓️ سجل الشهر (30 يوم)"])

# ----------------- TAB 1: TODAY (اليوم الحالي) -----------------
with tab_today:
    # Check if day is locked/closed
    if today_record.get("is_closed", False):
        st.info("🌙 **تم إقفال هذا اليوم بنجاح!** نوم العوافي وصحة وهنا.")
        if st.button("🔓 إعادة فتح اليوم لإضافة وجبة أخرى"):
            today_record["is_closed"] = False
            save_all_history(st.session_state.history)
            st.rerun()

    # Calculate today's totals
    today_meals = today_record.get("meals", [])
    total_cal = sum(m.get("calories", 0) for m in today_meals)
    total_pro = sum(m.get("protein", 0) for m in today_meals)
    total_carb = sum(m.get("carbs", 0) for m in today_meals)
    total_fat = sum(m.get("fat", 0) for m in today_meals)

    goal = today_record.get("goal", st.session_state.daily_goal)
    rem_cal = max(0, goal["calories"] - total_cal)

    # Metrics Grid (2x2)
    st.subheader(f"📊 ملخص اليوم ({today_str})")
    c1, c2 = st.columns(2)
    with c1:
        st.metric("المتبقي 🔥", f"{rem_cal} سعرة", delta=f"{total_cal}/{goal['calories']}")
    with c2:
        st.metric("البروتين 🥩", f"{total_pro}g", f"من {goal['protein']}g")

    c3, c4 = st.columns(2)
    with c3:
        st.metric("الكارب 🍞", f"{total_carb}g", f"من {goal['carbs']}g")
    with c4:
        st.metric("الدهون 🥑", f"{total_fat}g", f"من {goal['fat']}g")

    progress_pct = min(1.0, total_cal / max(1, goal["calories"]))
    st.progress(progress_pct, text=f"استهلكت {int(progress_pct * 100)}% من احتياجك اليومي ({total_cal} من {goal['calories']})")

    st.markdown("---")

    # Camera & Image Input
    if not today_record.get("is_closed", False):
        st.subheader("📸 إضافة وجبة جديدة")
        tab_cam, tab_up = st.tabs(["📷 التقاط بالكاميرا", "📁 رفع من الألبوم"])

        image_data = None
        with tab_cam:
            cam_pic = st.camera_input("التقط صورة لطبقك الآن")
            if cam_pic:
                image_data = cam_pic.getvalue()

        with tab_up:
            up_file = st.file_uploader("اختر صورة من ألبوم الصور", type=["jpg", "jpeg", "png", "webp"])
            if up_file:
                image_data = up_file.getvalue()

        if image_data:
            st.image(image_data, caption="الصورة المختارة", use_container_width=True)
            if st.button("🔍 فحص الوجبة وحساب السعرات", type="primary", use_container_width=True):
                with st.spinner("جارِ فحص الوجبة وتقدير السعرات والمكونات..."):
                    try:
                        result = analyze_food_image(image_data, get_api_key())
                        st.session_state["last_analysis"] = result
                    except Exception as e:
                        st.error(f"حدث خطأ أثناء التحليل: {e}")

        if "last_analysis" in st.session_state and st.session_state["last_analysis"]:
            res = st.session_state["last_analysis"]
            st.success(f"🍽️ **تم التعرف على:** {res.get('name', 'وجبة')}")

            rc1, rc2 = st.columns(2)
            rc1.metric("السعرات 🔥", f"{res.get('calories', 0)} kcal")
            rc2.metric("البروتين 🥩", f"{res.get('protein', 0)} g")
            rc3, rc4 = st.columns(2)
            rc3.metric("الكارب 🍞", f"{res.get('carbs', 0)} g")
            rc4.metric("الدهون 🥑", f"{res.get('fat', 0)} g")

            if "notes" in res and res["notes"]:
                st.info(f"📝 {res['notes']}")

            if st.button("➕ تسجيل الوجبة في اليوم", use_container_width=True):
                today_record["meals"].append({
                    "id": datetime.now().isoformat(),
                    "name": res.get("name", "وجبة"),
                    "calories": int(res.get("calories", 0)),
                    "protein": int(res.get("protein", 0)),
                    "carbs": int(res.get("carbs", 0)),
                    "fat": int(res.get("fat", 0)),
                    "time": datetime.now().strftime("%I:%M %p")
                })
                save_all_history(st.session_state.history)
                st.session_state["last_analysis"] = None
                st.rerun()

        st.markdown("---")

    # Meals Log for Today
    st.subheader(f"📋 وجبات مسجلة اليوم ({len(today_meals)})")

    if not today_meals:
        st.info("لم تسجل أي وجبة اليوم بعد.")
    else:
        for idx, meal in enumerate(reversed(today_meals)):
            st.markdown(f"""
            <div class="meal-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h4 style="margin: 0;">{meal['name']}</h4>
                    <span style="color: #888; font-size: 0.85rem;">⏰ {meal['time']}</span>
                </div>
                <div style="margin-top: 8px;">
                    <span class="macro-badge badge-cal">🔥 {meal['calories']} سعرة</span>
                    <span class="macro-badge badge-pro">🥩 {meal['protein']}g بروتين</span>
                    <span class="macro-badge badge-carb">🍞 {meal['carbs']}g كارب</span>
                    <span class="macro-badge badge-fat">🥑 {meal['fat']}g دهون</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Close Day / Lock Day Button
    st.markdown("---")
    if not today_record.get("is_closed", False):
        if st.button("🌙 إقفال اليوم وحفظ السجل النهائي", type="primary", use_container_width=True):
            today_record["is_closed"] = True
            save_all_history(st.session_state.history)
            st.success("تم إقفال يومك وحفظه في الأرشيف الأسبوعي والشهري بنجاح!")
            st.rerun()

# ----------------- TAB 2: WEEKLY LOG (سجل الأسبوع) -----------------
with tab_week:
    st.subheader("📅 سجل آخر 7 أيام")
    
    # Generate past 7 days
    past_7_days = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    
    week_cals = []
    week_pros = []
    week_carbs = []
    week_fats = []
    completed_days = 0

    for d in past_7_days:
        if d in st.session_state.history:
            d_meals = st.session_state.history[d].get("meals", [])
            c = sum(m.get("calories", 0) for m in d_meals)
            p = sum(m.get("protein", 0) for m in d_meals)
            cb = sum(m.get("carbs", 0) for m in d_meals)
            f = sum(m.get("fat", 0) for m in d_meals)
            if c > 0:
                completed_days += 1
                week_cals.append(c)
                week_pros.append(p)
                week_carbs.append(cb)
                week_fats.append(f)

    # Weekly Stats Cards
    avg_cal = int(sum(week_cals) / max(1, completed_days)) if completed_days > 0 else 0
    avg_pro = int(sum(week_pros) / max(1, completed_days)) if completed_days > 0 else 0
    avg_carb = int(sum(week_carbs) / max(1, completed_days)) if completed_days > 0 else 0
    avg_fat = int(sum(week_fats) / max(1, completed_days)) if completed_days > 0 else 0

    wc1, wc2 = st.columns(2)
    wc1.metric("معدل السعرات اليومي 🔥", f"{avg_cal} kcal")
    wc2.metric("معدل البروتين اليومي 🥩", f"{avg_pro} g")
    wc3, wc4 = st.columns(2)
    wc3.metric("معدل الكارب 🍞", f"{avg_carb} g")
    wc4.metric("معدل الدهون 🥑", f"{avg_fat} g")

    st.markdown(f"**أيام تم تسجيلها خلال الأسبوع:** {completed_days} من 7 أيام")
    st.markdown("---")

    # Day-by-day list
    for day in past_7_days:
        rec = st.session_state.history.get(day, {})
        d_meals = rec.get("meals", [])
        day_cal = sum(m.get("calories", 0) for m in d_meals)
        day_pro = sum(m.get("protein", 0) for m in d_meals)
        day_carb = sum(m.get("carbs", 0) for m in d_meals)
        day_fat = sum(m.get("fat", 0) for m in d_meals)
        is_closed = rec.get("is_closed", False)
        status_icon = "🔒 مقفل" if is_closed else ("🟢 مسجل" if day_cal > 0 else "⚪ لم يسجل")

        st.markdown(f"""
        <div class="log-day-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h4 style="margin: 0;">📅 {day} {"(اليوم)" if day == today_str else ""}</h4>
                <span style="font-size: 0.85rem; color: #555;">{status_icon}</span>
            </div>
            <div style="margin-top: 8px;">
                <span class="macro-badge badge-cal">🔥 {day_cal} سعرة</span>
                <span class="macro-badge badge-pro">🥩 {day_pro}g بروتين</span>
                <span class="macro-badge badge-carb">🍞 {day_carb}g كارب</span>
                <span class="macro-badge badge-fat">🥑 {day_fat}g دهون</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ----------------- TAB 3: MONTHLY LOG (سجل الشهر) -----------------
with tab_month:
    st.subheader("🗓️ سجل آخر 30 يوماً")
    
    past_30_days = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]
    
    month_cals = []
    month_pros = []
    m_logged_days = 0

    for d in past_30_days:
        if d in st.session_state.history:
            d_meals = st.session_state.history[d].get("meals", [])
            c = sum(m.get("calories", 0) for m in d_meals)
            p = sum(m.get("protein", 0) for m in d_meals)
            if c > 0:
                m_logged_days += 1
                month_cals.append(c)
                month_pros.append(p)

    m_avg_cal = int(sum(month_cals) / max(1, m_logged_days)) if m_logged_days > 0 else 0
    m_avg_pro = int(sum(month_pros) / max(1, m_logged_days)) if m_logged_days > 0 else 0
    total_month_cal = sum(month_cals)

    mc1, mc2 = st.columns(2)
    mc1.metric("معدل الشهر اليومي 🔥", f"{m_avg_cal} kcal")
    mc2.metric("معدل البروتين اليومي 🥩", f"{m_avg_pro} g")
    mc3, mc4 = st.columns(2)
    mc3.metric("مجموع سعرات الشهر", f"{total_month_cal:,} kcal")
    mc4.metric("الأيام الملتزم بها", f"{m_logged_days} / 30 يوم")

    st.markdown("---")
    st.markdown("#### 📋 تفاصيل الأيام للشهر:")

    for day in past_30_days:
        if day in st.session_state.history:
            rec = st.session_state.history[day]
            d_meals = rec.get("meals", [])
            if d_meals:
                day_cal = sum(m.get("calories", 0) for m in d_meals)
                day_pro = sum(m.get("protein", 0) for m in d_meals)
                day_carb = sum(m.get("carbs", 0) for m in d_meals)
                day_fat = sum(m.get("fat", 0) for m in d_meals)
                is_closed = rec.get("is_closed", False)

                st.markdown(f"""
                <div class="log-day-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h4 style="margin: 0;">🗓️ {day}</h4>
                        <span style="font-size: 0.85rem; color: #666;">{"🔒 مقفل" if is_closed else "نشط"}</span>
                    </div>
                    <div style="margin-top: 8px;">
                        <span class="macro-badge badge-cal">🔥 {day_cal} سعرة</span>
                        <span class="macro-badge badge-pro">🥩 {day_pro}g</span>
                        <span class="macro-badge badge-carb">🍞 {day_carb}g</span>
                        <span class="macro-badge badge-fat">🥑 {day_fat}g</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

# ----------------- Settings Expander at Bottom -----------------
st.markdown("---")
with st.expander("⚙️ تعديل الأهداف اليومية (الماكروز) والمفتاح"):
    st.markdown("أهدافك اليومية الحالية:")
    
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        new_cal = st.number_input("السعرات (kcal)", min_value=500, max_value=10000, value=st.session_state.daily_goal["calories"], step=50)
        new_pro = st.number_input("البروتين (g)", min_value=10, max_value=500, value=st.session_state.daily_goal["protein"], step=5)
    with col_g2:
        new_carb = st.number_input("الكارب (g)", min_value=10, max_value=800, value=st.session_state.daily_goal["carbs"], step=5)
        new_fat = st.number_input("الدهون (g)", min_value=5, max_value=300, value=st.session_state.daily_goal["fat"], step=5)
        
    if st.button("💾 حفظ الأهداف الجديدة", use_container_width=True):
        st.session_state.daily_goal = {
            "calories": int(new_cal),
            "protein": int(new_pro),
            "carbs": int(new_carb),
            "fat": int(new_fat)
        }
        today_record["goal"] = st.session_state.daily_goal.copy()
        save_all_history(st.session_state.history)
        st.success("تم حفظ أهدافك بنجاح!")
        st.rerun()

    st.markdown("---")
    st.subheader("🔑 مفتاح الخدمة")
    user_key = st.text_input("مفتاح الخدمة (اختياري)", value=get_api_key(), type="password")
    if user_key:
        st.session_state["api_key"] = user_key
