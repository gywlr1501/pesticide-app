import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime

# --- 1. 기본 설정 ---
st.set_page_config(page_title="잔류농약 판정기", page_icon="🥦", layout="wide")
st.title("🥦 잔류농약 적합 판정 시스템 (Pro + 이력관리)")

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

with st.spinner('데이터를 불러오는 중입니다... ⏳'):
    df = load_data()

if df is None:
    st.error("🚨 'data.csv' 파일을 찾을 수 없습니다!")
    st.stop()

food_list = sorted(df['food_type'].unique().tolist())
pesticide_list = sorted(df['pesticide_name'].unique().tolist())

# --- 3. 이력 저장소 (Session State) ---
# 웹사이트가 켜져 있는 동안 기록을 임시로 저장할 공간을 만듭니다.
if 'history_df' not in st.session_state:
    st.session_state['history_df'] = pd.DataFrame(columns=[
        '검사일자', '의뢰부서', '식품명', '농약명', '검출량', '허용기준', '초과량', '판정', '조치내용'
    ])

# 이력 추가 함수
def add_to_history(dept, food, pest, amount, limit, action):
    new_data = {
        '검사일자': datetime.now().strftime("%Y-%m-%d %H:%M"),
        '의뢰부서': dept,
        '식품명': food,
        '농약명': pest,
        '검출량': amount,
        '허용기준': limit,
        '초과량': round(amount - limit, 4),
        '판정': '부적합',
        '조치내용': action
    }
    st.session_state['history_df'] = pd.concat(
        [st.session_state['history_df'], pd.DataFrame([new_data])], ignore_index=True
    )

# --- 4. 탭 메뉴 구성 ---
tab1, tab2, tab3 = st.tabs(["🔍 개별 판정", "📑 일괄 판정(엑셀)", "📋 부적합 이력 관리"])

# ==========================================
# [탭 1] 개별 판정 + 이력 저장 기능
# ==========================================
with tab1:
    st.header("한 건씩 확인하기")
    c1, c2, c3 = st.columns(3)
    with c1: input_food = st.selectbox("식품 선택", food_list, index=None, key="s_food")
    with c2: input_pesticide = st.selectbox("농약 선택", pesticide_list, index=None, key="s_pest")
    with c3: input_amount = st.number_input("검출량 (mg/kg)", 0.0, format="%.4f", key="s_amt")

    if st.button("판정하기", type="primary", key="btn_s"):
        if input_food and input_pesticide:
            match = df[(df['food_type'] == input_food) & (df['pesticide_name'] == input_pesticide)]
            if match.empty:
                st.error("❌ 기준 정보가 없습니다.")
            else:
                limit = float(match.iloc[0]['limit_mg_kg'])
                diff = input_amount - limit

                st.divider()
                col_res1, col_res2 = st.columns(2)
                col_res1.metric("허용 기준", f"{limit} mg/kg")
                
                if diff > 0:
                    col_res2.metric("내 검출량", f"{input_amount} mg/kg", "부적합", delta_color="inverse")
                    st.error(f"🚨 **부적합!** (기준 {diff:.4f} 초과)")
                    
                    # === 부적합 시 이력 저장 폼 등장 ===
                    with st.container(border=True):
                        st.write("📝 **부적합 이력 등록**")
                        h_col1, h_col2 = st.columns(2)
                        with h_col1:
                            dept_input = st.text_input("의뢰 부서", placeholder="예: 구매팀, 생산1팀")
                        with h_col2:
                            action_input = st.selectbox("조치 내용", ["폐기", "반송", "재검사", "기타"])
                        
                        if st.button("이력에 저장하기 💾"):
                            if dept_input:
                                add_to_history(dept_input, input_food, input_pesticide, input_amount, limit, action_input)
                                st.success("✅ 부적합 대장에 저장되었습니다! (3번 탭에서 확인하세요)")
                            else:
                                st.warning("의뢰 부서를 입력해주세요.")
                else:
                    col_res2.metric("내 검출량", f"{input_amount} mg/kg", "적합")
                    st.success("✅ 안전합니다.")
                    st.balloons()

# ==========================================
# [탭 2] 일괄 판정
# ==========================================
with tab2:
    st.header("엑셀 붙여넣기 (식품명 / 농약명 / 검출량)")
    example_text = "가지\t가스가마이신\t0.5\n감자\t다이아지논\t0.01"
    paste_data = st.text_area("데이터 입력", height=150, placeholder=example_text)

    if st.button("일괄 판정 시작", type="primary"):
        if paste_data:
            try:
                batch_df = pd.read_csv(io.StringIO(paste_data), sep=None, names=['식품', '농약', '검출량'], engine='python')
                results = []
                
                # 검사 로직
                for i, row in batch_df.iterrows():
                    f = str(row['식품']).strip()
                    p = str(row['농약']).strip()
                    try: amt = float(row['검출량'])
                    except: amt = 0.0
                    
                    match = df[(df['food_type'] == f) & (df['pesticide_name'] == p)]
                    status, note, limit_val = "기준없음", "", 0.0
                    
                    if not match.empty:
                        limit_val = float(match.iloc[0]['limit_mg_kg'])
                        if amt > limit_val:
                            status = "🚨 부적합"
                            note = f"{amt - limit_val:.4f} 초과"
                        else:
                            status = "✅ 적합"
                    
                    results.append([f, p, amt, limit_val, status, note])

                res_df = pd.DataFrame(results, columns=['식품', '농약', '검출량', '기준', '판정', '비고'])
                
                # 결과 표시
                def color_row(row):
                    return ['background-color: #ffcccc'] * len(row) if "부적합" in row['판정'] else [''] * len(row)
                
                st.dataframe(res_df.style.apply(color_row, axis=1), use_container_width=True)
                
                # 부적합 건수 확인
                bad_items = res_df[res_df['판정'].str.contains("부적합")]
                if not bad_items.empty:
                    st.warning(f"🚨 부적합이 {len(bad_items)}건 있습니다. 이력 탭에 수동으로 등록해주세요.")
                
            except Exception as e:
                st.error("데이터 형식 오류")

# ==========================================
# [탭 3] 부적합 이력 관리 (NEW!)
# ==========================================
with tab3:
    st.header("📋 부적합 관리 대장")
    st.info("💡 웹사이트를 새로고침하면 기록이 사라지니, 꼭 **[CSV 다운로드]**를 눌러 파일로 저장하세요.")

    # 현재 기록된 데이터 보여주기
    history_data = st.session_state['history_df']
    
    if history_data.empty:
        st.write("아직 등록된 부적합 이력이 없습니다.")
    else:
        st.dataframe(history_data, use_container_width=True)
        
        # 다운로드 버튼
        csv_data = history_data.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 대장 엑셀(CSV)로 다운로드",
            data=csv_data,
            file_name=f"부적합관리대장_{datetime.now().strftime('%Y%m%d')}.csv",
            mime='text/csv'
        )
        
        # 기록 초기화 버튼
        if st.button("🗑️ 기록 모두 지우기"):
            st.session_state['history_df'] = st.session_state['history_df'].iloc[0:0]
            st.rerun()
