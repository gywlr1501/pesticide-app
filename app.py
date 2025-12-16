import streamlit as st
import pandas as pd
import os
import io
import re
from datetime import datetime

# --- 1. 기본 설정 ---
st.set_page_config(page_title="잔류농약 판정기 (PLS Pro)", page_icon="🥦", layout="wide")

st.markdown("""
    <style>
    .stTextArea textarea {
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 14px;
        background-color: #f8f9fa;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🥦 잔류농약 판정 시스템 (Pro + 스마트 검색)")
st.markdown("---")

# --- 2. 데이터 로딩 ---
@st.cache_data
def load_data():
    csv_file = 'data.csv'
    if not os.path.exists(csv_file):
        return None
    try:
        df = pd.read_csv(csv_file)
        df['food_type'] = df['food_type'].astype(str).str.strip()
        df['pesticide_name'] = df['pesticide_name'].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"데이터 파일 읽기 실패: {e}")
        return None

with st.spinner('시스템 가동 중... ⏳'):
    df = load_data()

if df is None:
    st.error("🚨 'data.csv' 파일이 없습니다.")
    st.stop()

food_list = sorted(df['food_type'].unique().tolist())
pesticide_list = sorted(df['pesticide_name'].unique().tolist())

# --- 3. 핵심 기능 함수들 ---
def clean_amount_value(value):
    try:
        if isinstance(value, (int, float)): return float(value)
        val_str = str(value).strip()
        cleaned = re.sub(r'[^0-9.]', '', val_str)
        if not cleaned: return 0.0
        return float(cleaned)
    except:
        return 0.0

def find_pesticide_match(df, input_pest_name):
    exact_match = df[df['pesticide_name'] == input_pest_name]
    if not exact_match.empty: return input_pest_name
    
    partial_match = df[df['pesticide_name'].str.contains(input_pest_name, case=False, regex=False)]
    if not partial_match.empty:
        return partial_match.iloc[0]['pesticide_name']
    return None

# --- 4. 이력 저장소 ---
if 'history_df' not in st.session_state:
    st.session_state['history_df'] = pd.DataFrame(columns=[
        '검사일자', '의뢰부서', '식품명', '농약명', 
        '검출량 (mg/kg)', '허용기준 (mg/kg)', '초과량 (mg/kg)', 
        '판정', '적용기준', '조치내용'
    ])

def add_to_history(dept, food, pest, amount, limit, action, standard_type):
    # 부서 입력이 없으면 "-"로 저장
    if not dept or dept.strip() == "":
        dept = "-"
        
    new_data = {
        '검사일자': datetime.now().strftime("%Y-%m-%d %H:%M"),
        '의뢰부서': dept,
        '식품명': food,
        '농약명': pest,
        '검출량 (mg/kg)': amount,
        '허용기준 (mg/kg)': limit,
        '초과량 (mg/kg)': round(amount - limit, 4),
        '판정': '부적합',
        '적용기준': standard_type,
        '조치내용': action
    }
    st.session_state['history_df'] = pd.concat(
        [st.session_state['history_df'], pd.DataFrame([new_data])], ignore_index=True
    )

# --- 5. 탭 메뉴 ---
tab1, tab2, tab3 = st.tabs(["🔍 개별 판정", "📑 일괄 판정 (스마트)", "📋 부적합 관리대장"])

# ==========================================
# [탭 1] 개별 판정
# ==========================================
with tab1:
    st.markdown("### 🎯 정밀 검사")
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1: input_food = st.selectbox("식품 선택", food_list, index=None, key="s_food")
        with c2: input_pesticide = st.selectbox("농약 선택 (한/영 검색)", pesticide_list, index=None, key="s_pest")
        with c3: input_amount = st.number_input("검출량 (mg/kg)", 0.0, format="%.4f", key="s_amt")

        st.markdown("")
        if st.button("판정 실행", type="primary", key="btn_s", use_container_width=True):
            if input_food and input_pesticide:
                match = df[(df['food_type'] == input_food) & (df['pesticide_name'] == input_pesticide)]
                
                if match.empty:
                    limit = 0.01
                    std_type = "PLS 일률기준"
                    desc = "0.01 mg/kg (PLS)"
                    is_pls = True
                else:
                    limit = float(match.iloc[0]['limit_mg_kg'])
                    std_type = "식약처 고시"
                    desc = f"{limit} mg/kg"
                    is_pls = False

                diff = input_amount - limit

                st.markdown("---")
                col_res1, col_res2 = st.columns(2)
                col_res1.metric("허용 기준", desc, std_type)
                
                if diff > 0:
                    col_
