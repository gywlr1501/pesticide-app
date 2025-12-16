import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime

# --- 1. 기본 설정 ---
st.set_page_config(page_title="잔류농약 판정기", page_icon="🥦", layout="wide")
st.title("🥦 잔류농약 적합 판정 시스템 (Pro + 이력 수정기능)")

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
if 'history_df' not in st.session_state:
    st.session_state['history_df'] = pd.DataFrame(columns=[
        '검사일자', '의뢰부서', '식품명', '농약명', '검출량', '허용기준', '초과량', '판정', '조치내용', '비고'
    ])

# 이력 추가 함수
def add_to_history(dept, food, pest, amount, limit, action, note=""):
    new_data = {
        '검사일자': datetime.now().strftime("%Y-%m-%d %H:%M"),
        '의뢰부서': dept,
        '식품명': food,
        '농약명': pest,
        '검출량': amount,
        '허용기준': limit,
        '초과량': round(amount - limit, 4),
        '판정': '부적합',
        '조치내용': action,
        '비고': note
    }
    st.session_state['history_df'] = pd.concat(
        [st.session_state['history_df'], pd.DataFrame([new_data])], ignore_index=True
    )

# --- 4. 탭 메뉴 구성 ---
tab1, tab2, tab3 = st.tabs(["🔍 개별 판정", "📑 일괄 판정", "📋 부적합 이력 관리 (편집가능)"])

# ==========================================
# [탭 1] 개별 판정
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
                    
                    with st.container(border=True):
                        st.write("📝 **부적합 이력 등록**")
                        h_col1, h_col2 = st.columns(2)
                        with h_col1: dept_input = st.text_input("의뢰 부서", key="s_dept")
                        with h_col2: action_input = st.selectbox("조치 내용", ["폐기", "반송", "재검사", "기타"], key="s_act")
                        
                        if st.button("이력에 저장하기 💾", key="s_save"):
                            if dept_input:
                                add_to_history(dept_input, input_food, input_pesticide, input_amount, limit, action_input, "개별검사")
                                st.success("✅ 저장되었습니다!")
                            else:
                                st.warning("의뢰 부서를 입력해주세요.")
                else:
                    col_res2.metric("내 검출량", f"{input_amount} mg/kg", "적합")
                    st.success("✅ 안전합니다.")

# ==========================================
# [탭 2] 일괄 판정
# ==========================================
with tab2:
    st.header("엑셀 일괄 판정 & 자동 저장")
    st.info("부적합 발생 시 아래 입력된 정보로 **자동 저장**됩니다.")
    
    with st.expander("📝 검사 정보 입력 (필수)", expanded=True):
        bc1, bc2 = st.columns(2)
        with bc1: 
            batch_dept = st.text_input("의뢰 부서 (예: 품질팀)", value="품질관리팀", key="b_dept")
        with bc2: 
            batch_action = st.selectbox("부적합 시 조치 내용", ["폐기", "반송", "재검사", "기타"], key="b_act")

    example_text = "가지\t가스가마이신\t0.5\n감자\t다이아지논\t0.01"
    paste_data = st.text_area("데이터 붙여넣기", height=150, placeholder=example_text)

    if st.button("일괄 판정 및 자동 저장 🚀", type="primary"):
        if not batch_dept:
            st.warning("⚠️ '의뢰 부서'를 입력해주세요!")
        elif paste_data:
            try:
                batch_df = pd.read_csv(io.StringIO(paste_data), sep=None, names=['식품', '농약', '검출량'], engine='python')
                results = []
                saved_count = 0 
                
                progress_bar = st.progress(0)
                
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
                            add_to_history(batch_dept, f, p, amt, limit_val, batch_action, "일괄검사(자동)")
                            saved_count += 1
                        else:
                            status = "✅ 적합"
                    
                    results.append([f, p, amt, limit_val, status, note])
                    progress_bar.progress((i + 1) / len(batch_df))

                res_df = pd.DataFrame(results, columns=['식품', '농약', '검출량', '기준', '판정', '비고'])
                
                def color_row(row):
                    return ['background-color: #ffcccc'] * len(row) if "부적합" in row['판정'] else [''] * len(row)
                
                st.dataframe(res_df.style.apply(color_row, axis=1), use_container_width=True)
                
                if saved_count > 0:
                    st.error(f"🚨 **{saved_count}건의 부적합**이 이력 대장에 자동 저장되었습니다.")
                else:
                    st.success("🎉 모두 적합합니다!")
                
            except Exception as e:
                st.error(f"오류: {e}")

# ==========================================
# [탭 3] 부적합 이력 관리 (편집 기능 추가!)
# ==========================================
with tab3:
    st.header("📋 부적합 관리 대장")
    st.caption("💡 팁: 표 안의 내용을 더블 클릭하면 수정할 수 있습니다! (행 삭제도 가능)")

    if st.session_state['history_df'].empty:
        st.write("아직 등록된 이력이 없습니다.")
    else:
        # ★ 여기가 핵심! data_editor를 사용해 수정 가능하게 변경 ★
        # num_rows="dynamic"을 넣으면 행 추가/삭제도 가능해집니다.
        edited_df = st.data_editor(
            st.session_state['history_df'],
            use_container_width=True,
            num_rows="dynamic",
            key="history_editor"
        )
        
        # 수정된 내용이 있으면 세션에 다시 저장 (동기화)
        if not edited_df.equals(st.session_state['history_df']):
            st.session_state['history_df'] = edited_df
            st.rerun() # 화면 새로고침해서 반영

        st.divider()
        
        # 다운로드 버튼
        csv_data = st.session_state['history_df'].to_csv(index=False).encode('utf-8-sig')
        col_d1, col_d2 = st.columns([1, 4])
        
        with col_d1:
            st.download_button(
                label="📥 엑셀(CSV) 저장",
                data=csv_data,
                file_name=f"부적합관리대장_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv',
                type="primary"
            )
        
        with col_d2:
            if st.button("🗑️ 모든 기록 삭제"):
                st.session_state['history_df'] = st.session_state['history_df'].iloc[0:0]
                st.rerun()
