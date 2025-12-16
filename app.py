import streamlit as st
import pandas as pd
import os
import io
import re
from datetime import datetime

# --- 1. 기본 설정 ---
st.set_page_config(page_title="잔류농약 통합 관리 시스템", page_icon="🥦", layout="wide")

# 전문적인 스타일 (카드 UI, 폰트, 그래프 스타일)
st.markdown("""
    <style>
    .stTextArea textarea { font-family: 'Consolas', monospace; background-color: #f8f9fa; }
    .metric-card { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

# 사이드바 (전문적인 느낌 추가)
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2917/2917995.png", width=50) # 브로콜리 아이콘 등
    st.title("PLS 통합 관리")
    st.info("""
    **시스템 정보**
    - 버전: v2.5 (Pro)
    - 담당자: 롯데중앙연구소 Analysis Research팀
    - 적용기준: 2024 PLS
    """)
    st.markdown("---")
    st.caption("Copyright © 2025 Safety First")

st.title("🥦 잔류농약 적합 판정 & 통합 관리 시스템")
st.markdown("---")

# --- 2. 데이터 로딩 ---
@st.cache_data
def load_data():
    csv_file = 'data.csv'
    if not os.path.exists(csv_file): return None
    try:
        df = pd.read_csv(csv_file)
        df['food_type'] = df['food_type'].astype(str).str.strip()
        df['pesticide_name'] = df['pesticide_name'].astype(str).str.strip()
        return df
    except: return None

with st.spinner('데이터베이스 연결 중...'):
    df = load_data()

if df is None:
    st.error("🚨 데이터 파일을 찾을 수 없습니다.")
    st.stop()

food_list = sorted(df['food_type'].unique().tolist())
pesticide_list = sorted(df['pesticide_name'].unique().tolist())

# --- 3. 함수들 ---
def clean_amount(val):
    try: return float(re.sub(r'[^0-9.]', '', str(val)))
    except: return 0.0

def find_pest(df, name):
    exact = df[df['pesticide_name'] == name]
    if not exact.empty: return name
    partial = df[df['pesticide_name'].str.contains(name, case=False, regex=False)]
    return partial.iloc[0]['pesticide_name'] if not partial.empty else None

# --- 4. 이력 저장소 ---
if 'history_df' not in st.session_state:
    st.session_state['history_df'] = pd.DataFrame(columns=[
        '선택', '검사일자', '의뢰부서', '식품명', '농약명', 
        '검출량', '허용기준', '판정', '비고'
    ])

def add_to_history(dept, food, pest, amount, limit, note):
    if not dept: dept = "-"
    new_row = {
        '선택': False, # 삭제용 체크박스 초기값
        '검사일자': datetime.now().strftime("%Y-%m-%d %H:%M"),
        '의뢰부서': dept,
        '식품명': food,
        '농약명': pest,
        '검출량': amount,
        '허용기준': limit,
        '판정': '부적합',
        '비고': note
    }
    st.session_state['history_df'] = pd.concat(
        [st.session_state['history_df'], pd.DataFrame([new_row])], ignore_index=True
    )

# --- 5. 대시보드 (전문성 UP! 📈) ---
# 저장된 이력이 있으면 상단에 요약 통계를 보여줍니다.
if not st.session_state['history_df'].empty:
    hist = st.session_state['history_df']
    total_scan = len(hist) # 전체 검사 건수 (여기서는 부적합 건수만 쌓이지만, 예시로 활용)
    # 실제로는 전체 검사 카운트도 따로 세면 좋지만, 현재 구조상 부적합 건수 위주로 보여줌
    
    st.markdown("### 📊 실시간 현황 대시보드")
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("🚨 누적 부적합", f"{total_scan}건", delta="오늘 기준")
    with m2: st.metric("📅 오늘 날짜", datetime.now().strftime("%m-%d"))
    
    # 가장 많이 걸린 농약 1위
    top_pest = hist['농약명'].mode()
    top_pest_name = top_pest[0] if not top_pest.empty else "-"
    with m3: st.metric("⚠️ 최다 검출 농약", top_pest_name)
    
    # 가장 많이 걸린 식품 1위
    top_food = hist['식품명'].mode()
    top_food_name = top_food[0] if not top_food.empty else "-"
    with m4: st.metric("🍆 최다 검출 식품", top_food_name)
    st.markdown("---")

# --- 6. 탭 메뉴 ---
tab1, tab2, tab3 = st.tabs(["🔍 정밀 검사", "📑 일괄 분석", "📋 통합 관리 대장"])

# [탭 1] 정밀 검사
with tab1:
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1: f_in = st.selectbox("식품", food_list, index=None, key="s_f")
        with c2: p_in = st.selectbox("농약 (검색)", pesticide_list, index=None, key="s_p")
        with c3: a_in = st.number_input("검출량 (mg/kg)", 0.0, format="%.4f", key="s_a")
        
        st.write("")
        if st.button("판정 실행", type="primary", use_container_width=True):
            if f_in and p_in:
                match = df[(df['food_type'] == f_in) & (df['pesticide_name'] == p_in)]
                is_pls = match.empty
                limit = 0.01 if is_pls else float(match.iloc[0]['limit_mg_kg'])
                
                c_res1, c_res2 = st.columns(2)
                c_res1.metric("허용 기준", f"{limit} mg/kg", "PLS 적용" if is_pls else "식약처 고시")
                
                if a_in > limit:
                    c_res2.metric("결과", f"{a_in} mg/kg", "부적합", delta_color="inverse")
                    st.error(f"🚨 **부적합** (기준치 {limit} 초과)")
                    
                    with st.expander("📝 이력 저장 (클릭)", expanded=True):
                        d_in = st.text_input("부서명", placeholder="입력 안하면 '-'", key="s_d")
                        act_in = st.selectbox("조치", ["폐기", "반송", "기타"], key="s_act")
                        if st.button("저장하기", key="s_sv"):
                            add_to_history(d_in, f_in, p_in, a_in, limit, f"{act_in} / 개별")
                            st.toast("저장 완료!", icon="✅")
                            st.rerun()
                else:
                    c_res2.metric("결과", f"{a_in} mg/kg", "적합")
                    st.success("✅ 안전합니다.")

# [탭 2] 일괄 분석
with tab2:
    col_g, col_i = st.columns([1, 2])
    with col_g:
        st.info("💡 엑셀에서 [식품 / 농약 / 검출량]을 복사해서 붙여넣으세요.")
        if st.button("예시 데이터 입력"):
            st.session_state['paste_preset'] = "가지\tKasugamycin\t0.5T\n감자\tDiazinon\t0.01"
            
    with col_i:
        d_batch = st.text_input("부서명 (선택)", key="b_d")
        txt_val = st.session_state.get('paste_preset', "")
        txt_in = st.text_area("데이터 입력", value=txt_val, height=150)
        
        if st.button("🚀 분석 시작", type="primary", use_container_width=True):
            if txt_in:
                try:
                    b_df = pd.read_csv(io.StringIO(txt_in), sep=None, names=['식품','농약','검출량'], engine='python')
                    res, saved = [], 0
                    
                    bar = st.progress(0)
                    for i, row in b_df.iterrows():
                        f = str(row['식품']).strip()
                        p_raw = str(row['농약']).strip()
                        amt = clean_amount(row['검출량'])
                        
                        real_p = find_pest(df, p_raw)
                        p_show = real_p if real_p else p_raw
                        match = df[(df['food_type'] == f) & (df['pesticide_name'] == p_show)] if real_p else pd.DataFrame()
                        
                        limit = float(match.iloc[0]['limit_mg_kg']) if not match.empty else 0.01
                        res_type = "고시" if not match.empty else "PLS"
                        
                        status = "✅ 적합"
                        if amt > limit:
                            status = "🚨 부적합"
                            add_to_history(d_batch, f, p_show, amt, limit, f"일괄 / {res_type}")
                            saved += 1
                        
                        res.append([f, p_show, amt, limit, res_type, status])
                        bar.progress((i+1)/len(b_df))
                        
                    r_df = pd.DataFrame(res, columns=['식품','농약','검출량','기준','구분','판정'])
                    
                    def color_row(val):
                        if "부적합" in val: return 'background-color: #ffcccc; color: red; font-weight: bold'
                        if "PLS" in val: return 'background-color: #fffff0'
                        return ''
                    
                    st.dataframe(r_df.style.applymap(color_row, subset=['판정', '구분']), use_container_width=True)
                    
                    if saved > 0: st.error(f"🚨 **{saved}건**이 부적합하여 대장에 자동 저장되었습니다.")
                    else: st.balloons()
                    
                except Exception as e: st.error(f"오류: {e}")

# [탭 3] 통합 관리 대장 (삭제 버튼 & 차트 추가!)
with tab3:
    c_head, c_refresh = st.columns([4, 1])
    with c_head: st.markdown("### 📋 부적합 관리 대장")
    with c_refresh: 
        if st.button("🔄 새로고침"): st.rerun()

    if st.session_state['history_df'].empty:
        st.info("데이터가 깨끗합니다! (부적합 이력 없음)")
    else:
        # 1. 차트 보여주기 (전문성 UP!)
        with st.expander("📈 통계 차트 보기 (Click)", expanded=False):
            chart_col1, chart_col2 = st.columns(2)
            with chart_col1:
                st.caption("식품별 부적합 빈도")
                st.bar_chart(st.session_state['history_df']['식품명'].value_counts())
            with chart_col2:
                st.caption("농약별 부적합 빈도")
                st.bar_chart(st.session_state['history_df']['농약명'].value_counts())

        # 2. 데이터 에디터 (체크박스 기능 활성화)
        st.write("삭제할 항목의 **[선택]** 박스를 체크하고 아래 삭제 버튼을 누르세요.")
        
        # history_df의 컬럼 순서 조정 ('선택'이 맨 앞으로)
        cols = ['선택'] + [c for c in st.session_state['history_df'].columns if c != '선택']
        
        edited_df = st.data_editor(
            st.session_state['history_df'][cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "선택": st.column_config.CheckboxColumn("선택", width="small"),
                "판정": st.column_config.TextColumn(disabled=True),
            },
            key="history_editor"
        )

        # 3. 액션 버튼들 (삭제 & 다운로드)
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 3])
        
        with col_btn1:
            # ★ 요청하신 삭제 버튼 구현 ★
            if st.button("🗑️ 선택 항목 삭제", type="primary"):
                # 선택된 행(True)만 빼고 남기기
                rows_to_keep = edited_df[edited_df['선택'] == False]
                # '선택' 컬럼은 저장할 필요 없으니 False로 초기화해서 저장
                rows_to_keep['선택'] = False 
                st.session_state['history_df'] = rows_to_keep
                st.rerun()
        
        with col_btn2:
            if st.button("🔥 전체 초기화"):
                st.session_state['history_df'] = st.session_state['history_df'].iloc[0:0]
                st.rerun()
                
        with col_btn3:
            csv = edited_df.drop(columns=['선택']).to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 엑셀 다운로드", csv, f"Report_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
