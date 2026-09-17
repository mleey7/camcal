import streamlit as st
import requests
import json
import base64
from datetime import datetime
from PIL import Image
import io

# Page configuration for mobile-friendly UI
st.set_page_config(
    page_title="متتبع السعرات بالكاميرا",
    page_icon="📸",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Custom CSS for Arabic & Mobile Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
        direction: rtl;
        text-align: right;
    }
    
    .stMetric {
        background: #f8f9fa;
        padding: 12px;
        border-radius: 12px;
        border: 1px solid #e9ecef;
        text-align: center;
    }
    
    .meal-card {
        background: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    
    .macro-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-left: 6px;
    }
    .badge-cal { background: #ffe3e3; color: #c92a2a; }
    .badge-pro { background: #e7f5ff; color: #1864ab; }
    .badge-carb { background: #fff3bf; color: #e67700; }
    .badge-fat { background: #e6fcf5; color: #087f5b; }
</style>
""", unsafe_allow_html=True)

import os

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
    أنت خبير تغذية وذكاء اصطناعي متخصص في حساب السعرات.
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
                # Extract JSON block
                start = text.find("{")
                end = text.rfind("}") + 1
                if start != -1 and end != -1:
                    json_str = text[start:end]
                    return json.loads(json_str)
            else:
                last_error = f"Model {model} returned {res.status_code}: {res.text}"
        except Exception as e:
            last_error = str(e)
            continue
            
    raise Exception(f"فشل التحليل عبر جميع النماذج: {last_error}")

# Session State Initialization
if "meals" not in st.session_state:
    st.session_state.meals = []
if "daily_goal" not in st.session_state:
    st.session_state.daily_goal = {
        "calories": 2905,
        "protein": 182,
        "carbs": 363,
        "fat": 81
    }

# App Header
st.title("📸 متتبع السعرات بالكاميرا")
st.caption("صوّر وجبتك بكاميرا جوالك أو ارفع صورتها لحساب السعرات والماكروز مباشرة")

# Sidebar for Settings & Macro Goals
with st.sidebar:
    st.header("🎯 أهدافك اليومية (الماكروز)")
    st.markdown("الأهداف الحالية المعتمدة:")
    
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        new_cal = st.number_input("السعرات (kcal)", min_value=500, max_value=10000, value=st.session_state.daily_goal["calories"], step=50)
        new_pro = st.number_input("البروتين (g)", min_value=10, max_value=500, value=st.session_state.daily_goal["protein"], step=5)
    with col_g2:
        new_carb = st.number_input("الكارب (g)", min_value=10, max_value=800, value=st.session_state.daily_goal["carbs"], step=5)
        new_fat = st.number_input("الدهون (g)", min_value=5, max_value=300, value=st.session_state.daily_goal["fat"], step=5)
        
    if st.button("💾 حفظ أي تعديل جديد", use_container_width=True):
        st.session_state.daily_goal = {
            "calories": int(new_cal),
            "protein": int(new_pro),
            "carbs": int(new_carb),
            "fat": int(new_fat)
        }
        st.success("تم تحديث أهدافك بنجاح!")
        st.rerun()

    st.markdown("---")
    st.subheader("🔑 مفتاح الخدمة")
    user_key = st.text_input("مفتاح الخدمة (اختياري)", value=get_api_key(), type="password")
    if user_key:
        st.session_state["api_key"] = user_key

# Calculate current totals
total_cal = sum(m["calories"] for m in st.session_state.meals)
total_pro = sum(m["protein"] for m in st.session_state.meals)
total_carb = sum(m["carbs"] for m in st.session_state.meals)
total_fat = sum(m["fat"] for m in st.session_state.meals)

goal = st.session_state.daily_goal
rem_cal = max(0, goal["calories"] - total_cal)

# Progress Indicators
st.subheader("📊 ملخص اليوم")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("المتبقي", f"{rem_cal} سعرة", delta=f"{total_cal}/{goal['calories']}")
with col2:
    st.metric("البروتين", f"{total_pro}g", f"من {goal['protein']}g")
with col3:
    st.metric("الكارب", f"{total_carb}g", f"من {goal['carbs']}g")
with col4:
    st.metric("الدهون", f"{total_fat}g", f"من {goal['fat']}g")

progress_pct = min(1.0, total_cal / max(1, goal["calories"]))
st.progress(progress_pct, text=f"استهلكت {int(progress_pct * 100)}% من احتياجك اليومي")

st.markdown("---")

# Meal Input Section
st.subheader("📸 تحليل وجبة جديدة")
tab_camera, tab_upload = st.tabs(["📷 التقاط بالكاميرا (مباشر من الجوال)", "📁 رفع صورة من الألبوم"])

image_data = None
with tab_camera:
    camera_pic = st.camera_input("التقط صورة لطبقك الآن")
    if camera_pic:
        image_data = camera_pic.getvalue()

with tab_upload:
    uploaded_file = st.file_uploader("اختر صورة من ألبوم الصور", type=["jpg", "jpeg", "png", "webp"])
    if uploaded_file:
        image_data = uploaded_file.getvalue()

if image_data:
    st.image(image_data, caption="الصورة المختارة", use_container_width=True)
    if st.button("🔍 تحليل الوجبة وحساب السعرات", type="primary", use_container_width=True):
        with st.spinner("جارِ فحص الوجبة وتقدير السعرات والمكونات..."):
            try:
                result = analyze_food_image(image_data, get_api_key())
                st.session_state["last_analysis"] = result
            except Exception as e:
                st.error(f"حدث خطأ أثناء التحليل: {e}")

if "last_analysis" in st.session_state and st.session_state["last_analysis"]:
    res = st.session_state["last_analysis"]
    st.success(f"🍽️ **تم التعرف على:** {res.get('name', 'وجبة')}")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("السعرات 🔥", f"{res.get('calories', 0)} kcal")
    c2.metric("البروتين 🥩", f"{res.get('protein', 0)} g")
    c3.metric("الكارب 🍞", f"{res.get('carbs', 0)} g")
    c4.metric("الدهون 🥑", f"{res.get('fat', 0)} g")
    
    if "notes" in res and res["notes"]:
        st.info(f"📝 {res['notes']}")
        
    if st.button("➕ إضافة الوجبة إلى سجل اليوم", use_container_width=True):
        st.session_state.meals.append({
            "id": datetime.now().isoformat(),
            "name": res.get("name", "وجبة"),
            "calories": res.get("calories", 0),
            "protein": res.get("protein", 0),
            "carbs": res.get("carbs", 0),
            "fat": res.get("fat", 0),
            "time": datetime.now().strftime("%I:%M %p")
        })
        st.session_state["last_analysis"] = None
        st.rerun()

st.markdown("---")

# Meals Log Section
st.subheader(f"📋 سجل وجبات اليوم ({len(st.session_state.meals)})")

if not st.session_state.meals:
    st.info("لم تسجل أي وجبة اليوم بعد. ابدأ بتصوير وجبتك أعلاه!")
else:
    for idx, meal in enumerate(reversed(st.session_state.meals)):
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
        
    if st.button("🗑️ مسح سجل اليوم"):
        st.session_state.meals = []
        st.rerun()
