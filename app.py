import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import os

# --- 1. 기본 설정 ---
st.set_page_config(page_title="잔류농약 판정기", page_icon="🥦")
st.title("🥦 잔류농약 적합 판정 시스템 (CSV 버전)")

# --- 2. 데이터 로딩 (CSV 방식) ---
# 보안 문제로 DB 파일 대신 CSV(글자 파일)를 읽어서 즉석에서 DB를 만듭니다.
@st.cache_resource
def get_engine_from_csv():
    csv_file = 'data.csv'
    
    if not os.path.exists(csv_file):
        st.error("🚨 'data.csv' 파일이 없습니다!")
        st.warning("GitHub에서 'Create new file'을 눌러 data.csv를 만들고 내용을 붙여넣으세요.")
        st.stop()
    
    # CSV 파일을 읽어서 메모리(RAM) 속에 임시 DB를 만듭니다.
    try:
        df = pd.read_csv(csv_file)
        
        # 기계적인 처리를 위해 메모리 DB 생성
        engine = create_engine('sqlite:///:memory:')
        df.to_sql('pesticide_limits', engine, index=False)
        return engine
    except Exception as e:
        st.error(f"데이터 로딩 중 오류 발생: {e}")
        st.stop()

# 엔진 가동!
with st.spinner('데이터를 해독하고 있습니다... ⏳'):
    engine = get_engine_from_csv()

# --- 3. 목록 가져오기 ---
@st.cache_data
def get_lists():
    conn = engine.connect()
    # DISTINCT를 이용해 중복 제거
    df_food = pd.read_sql("SELECT DISTINCT food_type FROM pesticide_limits ORDER BY food_type", conn)
    df_pesticide = pd.read_sql("SELECT DISTINCT pesticide_name FROM pesticide_limits ORDER BY pesticide_name", conn)
    conn.close()
    return df_food['food_type'].tolist(), df_pesticide['pesticide_name'].tolist()

food_options, pesticide_options = get_lists()

# --- 4. 화면 구성 (이전과 동일) ---
st.divider()
col1, col2 = st.columns(2)

with col1:
    input_food = st.selectbox("1. 식품 선택", food_options, index=None, placeholder="식품을 선택하세요")

with col2:
    input_pesticide = st.selectbox("2. 농약 선택", pesticide_options, index=None, placeholder="농약을 선택하세요")

input_amount = st.number_input("3. 검출량 (mg/kg)", min_value=0.0, format="%.4f", step=0.001)

# --- 5. 판정 로직 ---
if st.button("판정하기 🔍", type="primary"):
    if not input_food or not input_pesticide:
        st.warning("식품명과 농약명을 모두 선택해주세요!")
    else:
        query = text("SELECT limit_mg_kg FROM pesticide_limits WHERE food_type = :food AND pesticide_name = :pesticide")
        
        with engine.connect() as conn:
            result = pd.read_sql(query, conn, params={'food': input_food, 'pesticide': input_pesticide})

        if result.empty:
            st.error("❌ 기준 데이터를 찾을 수 없습니다.")
        else:
            limit = float(result.iloc[0]['limit_mg_kg'])
            
            st.subheader("📊 판정 결과")
            c1, c2 = st.columns(2)
            c1.metric("허용 기준", f"{limit} mg/kg")
            c2.metric("내 검출량", f"{input_amount} mg/kg")

            if input_amount > limit:
                st.error(f"🚨 **부적합** (초과량: {input_amount - limit:.4f} mg/kg)")
            else:
                st.success("✅ **적합** (안전합니다)")
                st.balloons()
