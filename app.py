import streamlit as st
import pandas as pd
import os

# --- 1. 기본 설정 ---
st.set_page_config(page_title="잔류농약 판정기", page_icon="🥦")
st.title("🥦 잔류농약 적합 판정 시스템 (CSV 버전)")

# --- 2. 데이터 로딩 (가장 단순한 방법!) ---
@st.cache_data
def load_data():
    csv_file = 'data.csv'
    
    # 파일이 있는지 확인
    if not os.path.exists(csv_file):
        return None
    
    # CSV 파일을 그냥 엑셀 읽듯이 읽어옵니다.
    try:
        df = pd.read_csv(csv_file)
        # 혹시 모를 공백 제거 (안전장치)
        df['food_type'] = df['food_type'].astype(str).str.strip()
        df['pesticide_name'] = df['pesticide_name'].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"데이터 파일 읽기 실패: {e}")
        return None

# 데이터 불러오기
with st.spinner('데이터를 불러오는 중입니다... ⏳'):
    df = load_data()

# 파일이 없을 때 경고
if df is None:
    st.error("🚨 'data.csv' 파일을 찾을 수 없습니다!")
    st.warning("GitHub 저장소에 'data.csv' 파일이 잘 올라가 있는지 확인해주세요.")
    st.stop()

# --- 3. 목록 만들기 ---
# DB 쿼리 대신 파이썬으로 목록을 뽑습니다.
food_list = sorted(df['food_type'].unique().tolist())
pesticide_list = sorted(df['pesticide_name'].unique().tolist())

# --- 4. 화면 구성 ---
st.divider()
st.write("검사할 식품과 농약을 선택하세요.")

col1, col2 = st.columns(2)

with col1:
    input_food = st.selectbox("1. 식품 선택", food_list, index=None, placeholder="식품을 선택하세요")

with col2:
    input_pesticide = st.selectbox("2. 농약 선택", pesticide_list, index=None, placeholder="농약을 선택하세요")

input_amount = st.number_input("3. 검출량 (mg/kg)", min_value=0.0, format="%.4f", step=0.001)

# --- 5. 판정 로직 (Pandas 필터링) ---
if st.button("판정하기 🔍", type="primary"):
    if not input_food or not input_pesticide:
        st.warning("식품명과 농약명을 모두 선택해주세요!")
    else:
        # ★ 여기가 핵심! SQL 대신 파이썬으로 콕 집어서 찾기
        # "식품명이 이거고, 농약명이 이거인 행을 찾아라"
        match = df[
            (df['food_type'] == input_food) & 
            (df['pesticide_name'] == input_pesticide)
        ]

        if match.empty:
            st.error("❌ 기준 데이터를 찾을 수 없습니다.")
            st.write(f"선택하신 **{input_food}** / **{input_pesticide}** 조합은 목록에 없어요.")
        else:
            # 기준값 가져오기
            limit = float(match.iloc[0]['limit_mg_kg'])
            
            st.subheader("📊 판정 결과")
            c1, c2 = st.columns(2)
            c1.metric("허용 기준", f"{limit} mg/kg")
            c2.metric("내 검출량", f"{input_amount} mg/kg")

            if input_amount > limit:
                st.error(f"🚨 **부적합** (초과량: {input_amount - limit:.4f} mg/kg)")
            else:
                st.success("✅ **적합** (안전합니다)")
                st.balloons()
