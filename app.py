import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime

# --- 1. 기본 설정 ---
st.set_page_config(page_title="잔류농약 판정기 (PLS 적용)", page_icon="🥦", layout="wide")

# 스타일 커스텀
st.markdown("""
    <style>
    .stTextArea textarea {
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 14px;
        background-color: #f8f9fa;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🥦 잔류농약 판정 시스템 (Pro + PLS 제도 적용)")
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

with st.spinner('PLS 기준 데이터를 로딩 중입니다... ⏳'):
    df = load_data()

if df is None:
    st.error("🚨 'data.csv' 파일이 없습니다.")
    st.stop()

# 목록은 검색을 위해 존재 (PLS 적용 시 목록에 없어도 입력 가능해야 함 -> selectbox의 allow_output_mutation 개념이 없으므로, 
# 사용자가 목록에 없는 걸 넣으려면 텍스트 입력이 필요할 수 있으나, 일단 편의상 콤보박스 유지하되 설명 추가)
food_list = sorted(df['food_type'].unique().tolist())
pesticide_list = sorted(df['pesticide_name'].unique().tolist())

# --- 3. 이력 저장소 ---
if 'history_df' not in st.session_state:
    st.session_state['history_df'] = pd.DataFrame(columns=[
        '검사일자', '의뢰부서', '식품명', '농약명', 
        '검출량 (mg/kg)', '허용기준 (mg/kg)', '초과량 (mg/kg)', 
        '판정', '적용기준', '조치내용' # '적용기준' 컬럼 추가 (고시 vs PLS)
    ])

def add_to_history(dept, food, pest, amount, limit, action, standard_type):
    new_data = {
        '검사일자': datetime.now().strftime("%Y-%m-%d %H:%M"),
        '의뢰부서': dept,
        '식품명': food,
        '농약명': pest,
        '검출량 (mg/kg)': amount,
        '허용기준 (mg/kg)': limit,
        '초과량 (mg/kg)': round(amount - limit, 4),
        '판정': '부적합',
        '적용기준': standard_type, # PLS 인지 고시 기준인지 기록
        '조치내용': action
    }
    st.session_state['history_df'] = pd.concat(
        [st.session_state['history_df'], pd.DataFrame([new_data])], ignore_index=True
    )

# --- 4. 탭 메뉴 ---
tab1, tab2, tab3 = st.tabs(["🔍 개별 판정 (PLS)", "📑 일괄 판정 (PLS)", "📋 부적합 관리대장"])

# ==========================================
# [탭 1] 개별 판정
# ==========================================
with tab1:
    st.markdown("### 🎯 PLS 적용 정밀 검사")
    st.caption("목록에 없는 조합은 **일률기준 (0.01 mg/kg)**이 자동 적용됩니다.")
    
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        # PLS는 목록에 없는 것도 입력 가능해야 하므로 selectbox지만 
        # 사용자가 타이핑해서 검색한다고 가정 (실제로는 목록에 있는것만 선택됨. 
        # 목록 외 입력을 허용하려면 st.text_input과 병행해야 하지만, 편의상 DB내 검색 위주로 하되 로직만 구현)
        with c1: input_food = st.selectbox("식품 선택", food_list, index=None, key="s_food")
        with c2: input_pesticide = st.selectbox("농약 선택", pesticide_list, index=None, key="s_pest")
        with c3: input_amount = st.number_input("검출량 (mg/kg)", 0.0, format="%.4f", key="s_amt")

        st.markdown("")
        if st.button("판정 실행", type="primary", key="btn_s", use_container_width=True):
            if input_food and input_pesticide:
                # 1. DB에서 기준 찾기
                match = df[(df['food_type'] == input_food) & (df['pesticide_name'] == input_pesticide)]
                
                # 2. 기준 설정 로직 (PLS 적용)
                if match.empty:
                    limit = 0.01
                    standard_type = "PLS 일률기준"
                    limit_desc = "0.01 mg/kg (PLS)"
                    is_pls = True
                else:
                    limit = float(match.iloc[0]['limit_mg_kg'])
                    standard_type = "식약처 고시"
                    limit_desc = f"{limit} mg/kg"
                    is_pls = False

                diff = input_amount - limit

                st.markdown("---")
                col_res1, col_res2 = st.columns(2)
                
                col_res1.metric("허용 기준", limit_desc, standard_type)
                
                if diff > 0:
                    col_res2.metric("검출 결과", f"{input_amount} mg/kg", "부적합", delta_color="inverse")
                    
                    if is_pls:
                        st.error(f"🚨 **부적합!** (해당 작물에 등록되지 않은 농약입니다. PLS 기준 0.01 mg/kg 적용)")
                    else:
                        st.error(f"🚨 **부적합!** (기준치 {diff:.4f} mg/kg 초과)")
                    
                    # 조치 등록
                    with st.container(border=True):
                        st.subheader("📝 부적합 조치 등록")
                        h_col1, h_col2 = st.columns(2)
                        with h_col1: dept_input = st.text_input("의뢰 부서", key="s_dept")
                        with h_col2: action_input = st.selectbox("조치 내용", ["폐기", "반송", "재검사", "기타"], key="s_act")
                        
                        if st.button("이력 대장에 저장", key="s_save"):
                            if dept_input:
                                add_to_history(dept_input, input_food, input_pesticide, input_amount, limit, action_input, standard_type)
                                st.toast("✅ 저장되었습니다!", icon="💾")
                            else:
                                st.warning("의뢰 부서를 입력해주세요.")
                else:
                    col_res2.metric("검출 결과", f"{input_amount} mg/kg", "적합")
                    if is_pls:
                        st.success("✅ **적합** (등록되지 않은 농약이나, PLS 기준 0.01 이내로 검출됨)")
                    else:
                        st.success("✅ **적합** (안전합니다)")
            else:
                st.warning("식품명과 농약명을 선택해주세요.")

# ==========================================
# [탭 2] 일괄 판정
# ==========================================
with tab2:
    st.markdown("### 📑 PLS 자동 적용 일괄 분석")
    
    col_guide, col_input = st.columns([1, 2])
    
    with col_guide:
        with st.container(border=True):
            st.markdown("#### 💡 PLS 판정 안내")
            st.info("""
            **목록에 없는 조합**이 입력되면
            자동으로 **0.01 mg/kg** 기준을
            적용하여 판정합니다.
            """)
            st.markdown("---")
            st.markdown("**📋 예시 데이터 (복사용)**")
            st.code("""
가지    가스가마이신    0.5
바나나  미등록농약      0.02
사과    다이아지논      0.005
            """, language="text")
            if st.button("예시 데이터 채우기"):
                st.session_state['paste_preset'] = "가지\t가스가마이신\t0.5\n바나나\t미등록농약\t0.02\n사과\t다이아지논\t0.005"

    with col_input:
        with st.container(border=True):
            st.subheader("🛠️ 분석 설정")
            c_dept, c_act = st.columns(2)
            with c_dept: batch_dept = st.text_input("의뢰 부서", value="품질관리팀", key="b_dept")
            with c_act: batch_action = st.selectbox("부적합 조치", ["폐기", "반송", "재검사", "기타"], key="b_act")
            
            default_text = st.session_state.get('paste_preset', "")
            paste_data = st.text_area("데이터 입력창", value=default_text, height=200, label_visibility="collapsed", placeholder="식품 농약 검출량 붙여넣기")

            if st.button("🚀 일괄 분석 시작", type="primary", use_container_width=True):
                if not batch_dept:
                    st.warning("⚠️ 의뢰 부서를 입력해주세요.")
                elif not paste_data:
                    st.warning("⚠️ 데이터를 입력해주세요.")
                else:
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
                            
                            # 1. DB 매칭 확인
                            match = df[(df['food_type'] == f) & (df['pesticide_name'] == p)]
                            
                            # 2. PLS 로직 적용
                            if not match.empty:
                                limit_val = float(match.iloc[0]['limit_mg_kg'])
                                standard_type = "고시"
                            else:
                                limit_val = 0.01 # PLS 일률기준
                                standard_type = "PLS"
                            
                            # 3. 판정
                            if amt > limit_val:
                                status = "🚨 부적합"
                                note = f"(+{amt - limit_val:.4f})"
                                add_to_history(batch_dept, f, p, amt, limit_val, batch_action, standard_type)
                                saved_count += 1
                            else:
                                status = "✅ 적합"
                                note = ""
                            
                            results.append([f, p, amt, limit_val, standard_type, status, note])
                            progress_bar.progress((i + 1) / len(batch_df))

                        res_df = pd.DataFrame(results, columns=['식품', '농약', '검출량', '기준', '구분', '판정', '비고'])
                        
                        st.markdown("### 📊 분석 결과")
                        
                        def highlight_row(row):
                            if "부적합" in row['판정']:
                                return ['background-color: #ffe6e6; color: #cc0000; font-weight: bold'] * len(row)
                            elif row['구분'] == "PLS": # PLS 적용된 건은 노란색 힌트 배경
                                return ['background-color: #fffff0'] * len(row)
                            return [''] * len(row)
                        
                        st.dataframe(
                            res_df.style.apply(highlight_row, axis=1).format({"검출량": "{:.4f}", "기준": "{:.4f}"}),
                            use_container_width=True, hide_index=True
                        )
                        
                        if saved_count > 0:
                            st.error(f"🚨 **부적합 {saved_count}건** 자동 저장됨")
                        else:
                            st.success("🎉 모두 적합합니다!")
                            
                    except Exception as e:
                        st.error(f"오류: {e}")

# ==========================================
# [탭 3] 부적합 관리대장
# ==========================================
with tab3:
    col_h, col_r = st.columns([3, 1])
    with col_h: st.markdown("### 📋 부적합 관리 대장")
    with col_r: 
        if st.button("🔄 새로고침"): st.rerun()

    if st.session_state['history_df'].empty:
        st.info("이력이 없습니다.")
    else:
        edited_df = st.data_editor(
            st.session_state['history_df'],
            use_container_width=True,
            num_rows="dynamic",
            key="history_editor",
            column_config={
                "판정": st.column_config.TextColumn(disabled=True),
                "적용기준": st.column_config.TextColumn(disabled=True), # PLS 여부도 수정 불가
            }
        )
        if not edited_df.equals(st.session_state['history_df']):
            st.session_state['history_df'] = edited_df
            st.rerun()

        st.markdown("---")
        csv_data = st.session_state['history_df'].to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 엑셀 저장", csv_data, f"부적합대장_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", type="primary")
