import streamlit as st
import pandas as pd
import os
import io
import re
from datetime import datetime

# --- 1. 기본 설정 ---
st.set_page_config(page_title="잔류농약 판정 시스템(PLS추가)", page_icon="🥦", layout="wide")

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
                    col_res2.metric("검출 결과", f"{input_amount} mg/kg", "부적합", delta_color="inverse")
                    if is_pls:
                        st.error(f"🚨 **부적합!** (미등록 농약 -> PLS 0.01 적용)")
                    else:
                        st.error(f"🚨 **부적합!** (기준 {diff:.4f} 초과)")
                    
                    with st.container(border=True):
                        st.subheader("📝 부적합 조치")
                        h1, h2 = st.columns(2)
                        with h1: dept = st.text_input("의뢰 부서 (선택)", placeholder="입력 안 해도 됨", key="s_dept")
                        with h2: act = st.selectbox("조치", ["폐기", "반송", "재검사"], key="s_act")
                        
                        if st.button("저장", key="s_save"):
                            # 부서 입력 체크 로직 삭제 -> 바로 저장
                            add_to_history(dept, input_food, input_pesticide, input_amount, limit, act, std_type)
                            st.toast("저장되었습니다!", icon="💾")
                else:
                    col_res2.metric("검출 결과", f"{input_amount} mg/kg", "적합")
                    st.success("✅ **적합** (안전합니다)")
            else:
                st.warning("항목을 선택해주세요.")

# ==========================================
# [탭 2] 일괄 판정 (부서 입력 선택사항으로 변경)
# ==========================================
with tab2:
    st.markdown("### 📑 스마트 일괄 분석")
    col_guide, col_input = st.columns([1, 2])
    
    with col_guide:
        with st.container(border=True):
            st.info("""
            **💡 팁**
            - **의뢰 부서**는 비워두셔도 됩니다.
            - 엑셀 데이터를 그대로 복사해 오세요.
            """)
            st.markdown("**📋 예시 (클릭해서 채우기)**")
            st.code("""
가지    Kasugamycin    0.5T
감자    Diazinon       0.01
            """, language="text")
            if st.button("예시 채우기"):
                st.session_state['paste_preset'] = "가지\tKasugamycin\t0.5T\n감자\tDiazinon\t0.01"

    with col_input:
        with st.container(border=True):
            c_dept, c_act = st.columns(2)
            # value=""로 비워둠
            with c_dept: b_dept = st.text_input("의뢰 부서 (선택사항)", placeholder="비워두면 '-'로 저장됨", key="b_dept")
            with c_act: b_act = st.selectbox("부적합 조치", ["폐기", "반송", "재검사"], key="b_act")
            
            def_txt = st.session_state.get('paste_preset', "")
            paste_data = st.text_area("데이터 입력", value=def_txt, height=200, placeholder="식품 농약 검출량")

            if st.button("🚀 분석 시작", type="primary", use_container_width=True):
                # b_dept 체크 로직 삭제 -> paste_data만 있으면 실행
                if not paste_data:
                    st.warning("데이터를 입력해주세요.")
                else:
                    try:
                        batch_df = pd.read_csv(io.StringIO(paste_data), sep=None, names=['식품', '농약', '검출량'], engine='python')
                        results = []
                        saved_count = 0 
                        
                        progress_bar = st.progress(0)
                        
                        for i, row in batch_df.iterrows():
                            f_raw = str(row['식품']).strip()
                            p_raw = str(row['농약']).strip()
                            amt = clean_amount_value(row['검출량'])

                            real_pest_name = find_pesticide_match(df, p_raw)
                            if real_pest_name:
                                p_display = real_pest_name
                                match = df[(df['food_type'] == f_raw) & (df['pesticide_name'] == real_pest_name)]
                            else:
                                p_display = p_raw
                                match = pd.DataFrame()

                            if not match.empty:
                                limit_val = float(match.iloc[0]['limit_mg_kg'])
                                std_type = "고시"
                            else:
                                limit_val = 0.01
                                std_type = "PLS"
                            
                            if amt > limit_val:
                                status = "🚨 부적합"
                                note = f"(+{amt - limit_val:.4f})"
                                add_to_history(b_dept, f_raw, p_display, amt, limit_val, b_act, std_type)
                                saved_count += 1
                            else:
                                status = "✅ 적합"
                                note = ""
                            
                            results.append([f_raw, p_display, amt, limit_val, std_type, status, note])
                            progress_bar.progress((i + 1) / len(batch_df))

                        res_df = pd.DataFrame(results, columns=['식품', '농약(검색결과)', '검출량', '기준', '구분', '판정', '비고'])
                        
                        def highlight(row):
                            if "부적합" in row['판정']: return ['background-color: #ffe6e6; color: #cc0000; font-weight: bold'] * len(row)
                            if row['구분'] == "PLS": return ['background-color: #fffff0'] * len(row)
                            return [''] * len(row)
                        
                        st.dataframe(res_df.style.apply(highlight, axis=1).format({"검출량": "{:.4f}", "기준": "{:.4f}"}), use_container_width=True)
                        
                        if saved_count > 0:
                            st.error(f"🚨 **{saved_count}건 부적합** 발견 (이력 대장 자동 저장됨)")
                        else:
                            st.success("🎉 모두 적합합니다!")
                            
                    except Exception as e:
                        st.error(f"분석 중 오류 발생: {e}")

# ==========================================
# [탭 3] 부적합 관리대장
# ==========================================
with tab3:
    c_h, c_r = st.columns([3, 1])
    with c_h: st.markdown("### 📋 부적합 관리 대장")
    with c_r: 
        if st.button("🔄 새로고침"): st.rerun()

    if st.session_state['history_df'].empty:
        st.info("이력이 없습니다.")
    else:
        edited_df = st.data_editor(
            st.session_state['history_df'],
            use_container_width=True, num_rows="dynamic", key="history_editor",
            column_config={"판정": st.column_config.TextColumn(disabled=True)}
        )
        if not edited_df.equals(st.session_state['history_df']):
            st.session_state['history_df'] = edited_df
            st.rerun()
        
        st.divider()
        csv_data = st.session_state['history_df'].to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 엑셀 저장", csv_data, f"부적합대장_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", type="primary")
