import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import os

# 1. 페이지 설정 (탭 이름과 아이콘)
st.set_page_config(
    page_title="잔류농약 판정기",
    page_icon="🥦"
)

# 2. 제목 출력
st.title("🥦 잔류농약 적합 판정 시스템")

# 3. 데이터베이스 파일 확인 (진단 기능)
db_file = 'pesticide_db.sqlite'
if not os.path.exists(db_file):
    st.error("🚨 데이터베이스 파일이 없습니다!")
    st.warning("GitHub에 'pesticide_db.sqlite' 파일을 올리셨나요? 파일 철자를 확인해주세요.")
    st.stop()

# 4. 데이터베이스 연결
@st.cache_resource
def get_connection():
    return create_engine(f'sqlite:///{db_file}')

try:
    engine = get_connection()
except Exception as e:
    st.error(f"데이터베이스 연결 오류: {e}")
    st.stop()

# 5. 목록 가져오기 (로딩 표시 추가)
@st.cache_data
def get_lists():
    conn = engine.connect()
    df_food = pd.read_sql("SELECT DISTINCT food_type FROM pesticide_limits ORDER BY food_type", conn)
    df_pesticide = pd.read_sql("SELECT DISTINCT pesticide_name FROM pesticide_limits ORDER BY pesticide_name", conn)
    conn.close()
    return df_food['food_type'].tolist(), df_pesticide['pesticide_name'].tolist()

# 로딩 중일 때 스피너 돌리기
with st.spinner('데이터를 불러오고 있습니다... 잠시만 기다려주세요! ⏳'):
    try:
        food_options, pesticide_options = get_lists()
    except Exception as e:
        st.error(f"데이터 목록을 가져오지 못했습니다: {e}")
        st.stop()

# 6. 화면 구성
st.divider()
col1, col2 = st.columns(2)

with col1:
    input_food = st.selectbox("1. 식품 선택", food_options, index=None, placeholder="식품을 선택하세요")

with col2:
    input_pesticide = st.selectbox("2. 농약 선택", pesticide_options, index=None, placeholder="농약을 선택하세요")

input_amount = st.number_input("3. 검출량 (mg/kg)", min_value=0.0, format="%.4f", step=0.001)

# 7. 판정 로직
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
