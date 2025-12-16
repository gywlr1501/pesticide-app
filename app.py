import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime

# --- 1. 기본 설정 (레이아웃) ---
st.set_page_config(page_title="잔류농약 판정기", page_icon="🥦", layout="wide")

# 스타일 커스텀 (CSS) - 선택 사항이지만 헤더를 더 예쁘게 만듭니다.
st.markdown("""
    <style>
    .stTextArea textarea {
        font-family: 'Consolas', 'Courier New', monospace; /* 데이터 입력창을 코딩창처럼 전문적으로 */
        font-size: 14px;
        background-color: #f8f9fa;
    }
    .big-font {
        font-size: 24px !important;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🥦 잔류농약 적합 판정 시스템 (Pro)")
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

with st.spinner('시스템 리소스를 불러오는 중입니다... ⏳'):
    df = load_data()

if df is None:
    st.error("🚨 시스템 파일('data.csv')이 누락되었습니다.")
    st.stop()

food_list = sorted(df['food_type'].unique().tolist())
pesticide_list = sorted(df['pesticide_name'].unique().tolist())

# --- 3. 이력 저장소 ---
if 'history_df' not in st.session_state:
    st.session_state['history_df'] = pd.DataFrame(columns=[
        '검사일자', '의뢰부서', '식품명', '농약명', 
        '검출량 (mg/kg)', '허용기준 (mg/kg)', '초과량 (mg/kg)', 
        '판정', '조치내용', '비고'
    ])

def add_to_history(dept, food, pest, amount, limit, action, note=""):
    new_data = {
        '검사일자': datetime.now().strftime("%Y-%m-%d %H:%M"),
        '의뢰부서': dept,
        '식품명': food,
        '농약명': pest,
        '검출량 (mg/kg)': amount,
        '허용기준 (mg/kg)': limit,
        '초과량 (mg/kg)': round(amount - limit, 4),
        '판정': '부적합',
        '조치내용': action,
        '비고': note
    }
    st.session_state['history_df'] = pd.concat(
        [st.session_state['history_df'], pd.DataFrame([new_data])], ignore_index=True
    )

# --- 4. 탭 메뉴 구성 ---
tab1, tab2, tab3 = st.tabs(["🔍 개별 판정", "📑 일괄 판정 (엑셀)", "📋 부적합 관리대장"])

# ==========================================
# [탭 1] 개별 판정
# ==========================================
with tab1:
    st.markdown("### 🎯 개별 정밀 검사")
    
    # 깔끔한 박스(Container) 안에 입력폼 넣기
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1: input_food = st.selectbox("식품 선택", food_list, index=None, key="s_food")
        with c2: input_pesticide = st.selectbox("농약 선택", pesticide_list, index=None, key="s_pest")
        with c3: input_amount = st.number_input("검출량 (mg/kg)", 0.0, format="%.4f", key="s_amt")

        st.markdown("") # 여백
        if st.button("판정 실행", type="primary", key="btn_s", use_container_width=True):
            if input_food and input_pesticide:
                match = df[(df['food_type'] == input_food) & (df['pesticide_name'] == input_pesticide)]
                if match.empty:
                    st.error("❌ 기준 정보가 존재하지 않습니다.")
                else:
                    limit = float(match.iloc[0]['limit_mg_kg'])
                    diff = input_amount - limit

                    st.markdown("---")
                    col_res1, col_res2 = st.columns(2)
                    col_res1.metric("허용 기준", f"{limit} mg/kg", help="식약처 허용 기준치")
                    
                    if diff > 0:
                        col_res2.metric("검출 결과", f"{input_amount} mg/kg", "부적합", delta_color="inverse")
                        st.error(f"🚨 **부적합 판정** (기준치 {diff:.4f} mg/kg 초과)")
                        
                        # 부적합 조치 카드
                        with st.container(border=True):
                            st.subheader("📝 부적합 조치 등록")
                            h_col1, h_col2 = st.columns(2)
                            with h_col1: dept_input = st.text_input("의뢰 부서", key="s_dept")
                            with h_col2: action_input = st.selectbox("조치 내용", ["폐기", "반송", "재검사", "기타"], key="s_act")
                            
                            if st.button("이력 대장에 저장", key="s_save"):
                                if dept_input:
                                    add_to_history(dept_input, input_food, input_pesticide, input_amount, limit, action_input, "개별검사")
                                    st.toast("✅ 이력 대장에 저장되었습니다!", icon="💾") # 토스트 메시지로 변경 (더 고급스러움)
                                else:
                                    st.warning("의뢰 부서를 입력해주세요.")
                    else:
                        col_res2.metric("검출 결과", f"{input_amount} mg/kg", "적합")
                        st.success("✅ **적합 판정** (안전합니다)")
            else:
                st.warning("식품명과 농약명을 모두 선택해주세요.")

# ==========================================
# [탭 2] 일괄 판정 (디자인 대폭 개선!)
# ==========================================
with tab2:
    st.markdown("### 📑 대량 데이터 일괄 분석")
    
    col_guide, col_input = st.columns([1, 2]) # 화면을 1:2 비율로 나눔
    
    # 왼쪽: 사용 가이드 (사이드바처럼 활용)
    with col_guide:
        with st.container(border=True):
            st.markdown("#### 💡 사용 가이드")
            st.info("""
            1. 엑셀에서 데이터를 복사하세요.
               **(식품명 / 농약명 / 검출량)**
            2. 오른쪽 칸에 붙여넣으세요.
            3. **[분석 시작]** 버튼을 누르세요.
            """)
            st.markdown("---")
            st.markdown("**📋 예시 데이터 형식**")
            st.code("""
가지    가스가마이신    0.5
감자    다이아지논      0.01
            """, language="text")
            
            # 예시 데이터 자동 입력 버튼
            if st.button("예시 데이터 채우기"):
                st.session_state['paste_preset'] = "가지\t가스가마이신\t0.5\n감자\t다이아지논\t0.01\n고구마\t디디티\t0.2"

    # 오른쪽: 입력 폼 (카드 형태)
    with col_input:
        with st.container(border=True):
            st.subheader("🛠️ 분석 설정")
            c_dept, c_act = st.columns(2)
            with c_dept:
                batch_dept = st.text_input("의뢰 부서", value="품질관리팀", key="b_dept", help="부적합 발생 시 이력에 저장될 부서명")
            with c_act:
                batch_action = st.selectbox("부적합 조치", ["폐기", "반송", "재검사", "기타"], key="b_act")
            
            st.markdown("👇 **데이터 붙여넣기 (Ctrl+V)**")
            
            # 텍스트 영역 (높이 조절 및 기본값 설정)
            default_text = st.session_state.get('paste_preset', "")
            paste_data = st.text_area(
                label="데이터 입력창", 
                value=default_text,
                height=200, 
                placeholder="여기에 엑셀 데이터를 붙여넣으세요...",
                label_visibility="collapsed" # 라벨 숨김 (깔끔하게)
            )

            if st.button("🚀 일괄 분석 및 자동 저장", type="primary", use_container_width=True):
                if not batch_dept:
                    st.warning("⚠️ '의뢰 부서'를 입력해주세요.")
                elif not paste_data:
                    st.warning("⚠️ 데이터를 입력해주세요.")
                else:
                    try:
                        batch_df = pd.read_csv(io.StringIO(paste_data), sep=None, names=['식품', '농약', '검출량'], engine='python')
                        results = []
                        saved_count = 0 
                        
                        progress_bar = st.progress(0)
                        status_text = st.empty() # 진행상황 텍스트
                        
                        total = len(batch_df)
                        for i, row in batch_df.iterrows():
                            status_text.text(f"분석 중... ({i+1}/{total})")
                            f = str(row['식품']).strip()
                            p = str(row['농약']).strip()
                            try: amt = float(row['검출량'])
                            except: amt = 0.0
                            
                            match = df[(df['food_type'] == f) & (df['pesticide_name'] == p)]
                            status, note, limit_val = "❓ 기준없음", "", 0.0
                            
                            if not match.empty:
                                limit_val = float(match.iloc[0]['limit_mg_kg'])
                                if amt > limit_val:
                                    status = "🚨 부적합"
                                    note = f"(+{amt - limit_val:.4f})"
                                    add_to_history(batch_dept, f, p, amt, limit_val, batch_action, "일괄검사(자동)")
                                    saved_count += 1
                                else:
                                    status = "✅ 적합"
                            
                            results.append([f, p, amt, limit_val, status, note])
                            progress_bar.progress((i + 1) / total)

                        status_text.empty() # 텍스트 지우기
                        
                        # 결과 표시
                        res_df = pd.DataFrame(results, columns=['식품', '농약', '검출량 (mg/kg)', '기준 (mg/kg)', '판정', '비고'])
                        
                        st.markdown("### 📊 분석 결과")
                        
                        def highlight_row(row):
                            if "부적합" in row['판정']:
                                return ['background-color: #ffe6e6; color: #cc0000; font-weight: bold'] * len(row)
                            return [''] * len(row)
                        
                        st.dataframe(
                            res_df.style.apply(highlight_row, axis=1).format({"검출량 (mg/kg)": "{:.4f}", "기준 (mg/kg)": "{:.4f}"}),
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        if saved_count > 0:
                            st.error(f"🚨 **부적합 {saved_count}건**이 발견되어 관리대장에 자동 저장되었습니다.")
                        else:
                            st.success("🎉 모든 데이터가 적합합니다!")
                            st.balloons()
                            
                    except Exception as e:
                        st.error(f"데이터 형식 오류: {e}")
                        st.info("💡 엑셀에서 복사할 때 제목 줄은 제외하고 데이터만 복사해주세요.")

# ==========================================
# [탭 3] 부적합 이력 관리
# ==========================================
with tab3:
    col_header, col_btn = st.columns([3, 1])
    with col_header:
        st.markdown("### 📋 부적합 관리 대장")
    with col_btn:
        if st.button("🔄 새로고침"):
            st.rerun()

    if st.session_state['history_df'].empty:
        st.info("현재 등록된 부적합 이력이 없습니다. (클린합니다! ✨)")
    else:
        # 데이터 에디터 (편집 기능)
        edited_df = st.data_editor(
            st.session_state['history_df'],
            use_container_width=True,
            num_rows="dynamic",
            key="history_editor",
            column_config={
                "판정": st.column_config.TextColumn(disabled=True), # 판정 결과는 수정 불가하게 막음
            }
        )
        
        if not edited_df.equals(st.session_state['history_df']):
            st.session_state['history_df'] = edited_df
            st.rerun()

        st.markdown("---")
        
        c_down, c_del = st.columns([1, 4])
        with c_down:
            csv_data = st.session_state['history_df'].to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 엑셀 저장",
                data=csv_data,
                file_name=f"부적합관리대장_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv',
                type="primary"
            )
        with c_del:
            if st.button("🗑️ 기록 전체 삭제"):
                st.session_state['history_df'] = st.session_state['history_df'].iloc[0:0]
                st.rerun()
