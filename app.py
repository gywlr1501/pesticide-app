import streamlit as st
import pandas as pd
import os
import io
import re
from datetime import datetime

# --- 1. 기본 설정 (Enterprise Layout) ---
st.set_page_config(
    page_title="Lotte R&D Safety System", 
    page_icon="🏢", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 🎨 Lotte Enterprise CSS
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Noto Sans KR', sans-serif;
        background-color: #F4F6F9;
    }
    .top-header {
        background-color: white;
        padding: 20px 30px;
        border-top: 5px solid #DA291C;
        border-bottom: 1px solid #e0e0e0;
        margin-bottom: 25px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        border-radius: 0 0 8px 8px;
    }
    .header-title {
        font-size: 26px;
        font-weight: 800;
        color: #2c3e50;
    }
    .header-subtitle {
        font-size: 13px;
        color: #7f8c8d;
        font-weight: 500;
        margin-bottom: 5px;
    }
    /* KPI Metric 스타일 */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #eee;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #DA291C;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. Professional Sidebar ---
with st.sidebar:
    st.markdown("<h2 style='color:#DA291C; text-align:center;'>LOTTE R&D</h2>", unsafe_allow_html=True)
    st.markdown("<div style='text-align:center; font-size:12px; color:#666; margin-bottom:20px;'>Safety Management System</div>", unsafe_allow_html=True)
    
    with st.container(border=True):
        c1, c2 = st.columns([1, 3])
        with c1: st.write("👤")
        with c2: 
            st.write("**관리자 님**")
            st.caption("Analysis Research팀")

    st.markdown("---")
    st.caption("🖥️ SYSTEM STATUS")
    col_sys1, col_sys2 = st.columns(2)
    with col_sys1: st.metric("DB Status", "Online")
    with col_sys2: st.metric("Latency", "12ms")
    st.progress(100, text="System Normal")
    st.markdown("---")
    st.info("**Support Center**\n\nTel: 02-1234-5678")

# --- 3. 메인 헤더 ---
st.markdown("""
    <div class="top-header">
        <div class="header-subtitle">LOTTE R&D CENTER | Analysis Research Team</div>
        <div class="header-title">🥦 잔류농약 적합 판정 시스템</div>
    </div>
    """, unsafe_allow_html=True)

# --- 4. 데이터 로딩 & 세션 초기화 ---
COLUMNS = [
    '선택', '검사일자', '의뢰부서', '식품명', '농약명', 
    '검출량 (mg/kg)', '허용기준 (mg/kg)', '초과량 (mg/kg)', 
    '판정', '조치내용', '적용기준', '비고'
]

# 이력 데이터프레임 초기화
if 'history_df' not in st.session_state:
    st.session_state['history_df'] = pd.DataFrame(columns=COLUMNS)

# ★ 중요: Tab 1 판정 결과를 기억하기 위한 변수 초기화 ★
if 'analysis_result' not in st.session_state:
    st.session_state['analysis_result'] = None

# 데이터 로딩
@st.cache_data
def load_data():
    if not os.path.exists('data.csv'): return None
    try:
        df = pd.read_csv('data.csv')
        df['food_type'] = df['food_type'].astype(str).str.strip()
        df['pesticide_name'] = df['pesticide_name'].astype(str).str.strip()
        return df
    except: return None

df = load_data()
if df is None:
    st.error("🚨 [Critical Error] 시스템 기준정보 파일(data.csv)이 없습니다.")
    st.stop()

food_list = sorted(df['food_type'].unique().tolist())
pesticide_list = sorted(df['pesticide_name'].unique().tolist())

# 유틸리티 함수
def clean_amount(val):
    try: return float(re.sub(r'[^0-9.]', '', str(val)))
    except: return 0.0

# ★ 핵심: 스마트 검색 + 기준 우선순위 로직 ★
def get_limit_info(df, food, pest_input):
    # 1. 농약 이름 정규화 (스마트 검색)
    # 입력한 농약 이름이 DB에 있는지 정확히/부분 일치로 찾음
    exact_pest = df[df['pesticide_name'] == pest_input]
    if not exact_pest.empty:
        target_pest = pest_input
    else:
        # 부분 일치 검색 (예: Kasuga -> Kasugamycin)
        partial = df[df['pesticide_name'].str.contains(pest_input, case=False, regex=False)]
        if not partial.empty:
            target_pest = partial.iloc[0]['pesticide_name'] # 첫 번째 매칭되는 정식 명칭 사용
        else:
            target_pest = pest_input # 매칭 안 되면 입력값 그대로 사용 (미등록 농약 가정)

    # 2. (식품, 정규화된 농약) 조합으로 기준 검색
    # 여기서 기존 기준이 있으면 무조건 그게 나옴. 없으면 Empty.
    match = df[(df['food_type'] == food) & (df['pesticide_name'] == target_pest)]
    
    if not match.empty:
        # 기존 기준 발견! (우선순위 1위)
        limit = float(match.iloc[0]['limit_mg_kg'])
        std_type = "식약처 고시"
    else:
        # 기준 없음 -> PLS 적용 (우선순위 2위)
        limit = 0.01
        std_type = "PLS (0.01)"
    
    return target_pest, limit, std_type

# 이력 저장 함수
def add_to_history(dept, food, pest, amount, limit, action, standard, note=""):
    if not dept: dept = "-"
    excess = round(amount - limit, 4) if amount > limit else 0.0
    
    new_row = {
        '선택': False,
        '검사일자': datetime.now().strftime("%Y-%m-%d %H:%M"),
        '의뢰부서': dept,
        '식품명': food,
        '농약명': pest,
        '검출량 (mg/kg)': amount,
        '허용기준 (mg/kg)': limit,
        '초과량 (mg/kg)': excess,
        '판정': '부적합',
        '조치내용': action,
        '적용기준': standard,
        '비고': note
    }
    st.session_state['history_df'] = pd.concat(
        [st.session_state['history_df'], pd.DataFrame([new_row])], ignore_index=True
    )

# --- 5. Executive Dashboard ---
st.markdown("##### 📊 Executive Summary")
hist_df = st.session_state['history_df']
total_fail = len(hist_df)
today_str = datetime.now().strftime("%Y-%m-%d")
today_fail = len(hist_df[hist_df['검사일자'].str.contains(today_str)]) if not hist_df.empty else 0

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with kpi1: st.metric("누적 부적합 판정", f"{total_fail}건", delta=f"금일 +{today_fail}")
with kpi2: st.metric("최다 발생 부서", hist_df['의뢰부서'].mode()[0] if not hist_df.empty else "-", delta="Risk")
with kpi3: st.metric("주요 관리 품목", hist_df['식품명'].mode()[0] if not hist_df.empty else "-", delta="Check")
with kpi4: st.metric("시스템 가동률", "99.9%", "Normal")

st.markdown("---")

# --- 6. 탭 구성 ---
tab1, tab2, tab3 = st.tabs(["🔬 개별 정밀 검사", "📑 일괄 분석", "📈 부적합합 관리 대장""�

# ==========================================
# [TAB 1] 개별 검사 (버그 수정됨)
# ==========================================
with tab1:
    with st.container(border=True):
        st.markdown("###### 🎯 개별 시료 정밀 분석")
        c1, c2, c3 = st.columns(3)
        with c1: f_in = st.selectbox("품목 선택", food_list, index=None, key="t1_f")
        with c2: p_in = st.selectbox("농약 선택", pesticide_list, index=None, key="t1_p")
        with c3: a_in = st.number_input("검출량 (mg/kg)", 0.0, format="%.4f", key="t1_a")

        st.markdown("")
        
        # 분석 버튼 클릭 시 -> 결과를 Session State에 저장
        if st.button("판정 실행 (Analyze)", type="primary", use_container_width=True):
            if f_in and p_in:
                # 로직 실행
                real_pest, limit, std_type = get_limit_info(df, f_in, p_in)
                
                # 결과 저장
                st.session_state['analysis_result'] = {
                    'food': f_in,
                    'pest': real_pest,
                    'amount': a_in,
                    'limit': limit,
                    'std_type': std_type,
                    'is_fail': a_in > limit
                }
            else:
                st.warning("⚠️ 분석할 품목과 농약명을 선택하십시오.")

        # 분석 결과가 있으면 화면에 표시 (새로고침 되어도 유지됨)
        if st.session_state['analysis_result']:
            res = st.session_state['analysis_result']
            
            st.divider()
            r1, r2 = st.columns(2)
            with r1:
                st.info(f"**📉 허용 기준 ({res['std_type']})**\n\n# **{res['limit']:.4f} mg/kg**")
            with r2:
                if res['is_fail']:
                    diff = res['amount'] - res['limit']
                    st.error(f"**🚨 판정: 부적합**\n\n초과량: +{diff:.4f} mg/kg")
                    
                    # 부적합일 경우 저장 폼 표시
                    st.markdown("---")
                    with st.container(border=True):
                        st.markdown("**💾 부적합 이력 등록**")
                        dc1, dc2 = st.columns(2)
                        with dc1: dept_in = st.text_input("의뢰 부서", placeholder="예: 품질팀")
                        with dc2: act_in = st.selectbox("조치 사항", ["폐기", "반송", "재가공", "기타"])
                        
                        if st.button("통합 대장에 저장"):
                            add_to_history(dept_in, res['food'], res['pest'], res['amount'], res['limit'], act_in, res['std_type'], "정밀검사")
                            st.toast("✅ 통합 대장에 저장되었습니다!", icon="💾")
                            # 저장 후 결과 초기화 (선택사항)
                            st.session_state['analysis_result'] = None
                            st.rerun()
                else:
                    st.success(f"**✅ 판정: 적합**\n\n안전 관리 기준 이내입니다.")
                    if st.button("결과 초기화"):
                        st.session_state['analysis_result'] = None
                        st.rerun()

# ==========================================
# [TAB 2] 일괄 분석
# ==========================================
with tab2:
    col_guide, col_work = st.columns([1, 2])
    with col_guide:
        with st.container(border=True):
            st.markdown("###### 📌 Guide")
            st.caption("엑셀 복사: 식품명 농약명 검출량")
            if st.button("📋 테스트 데이터"):
                st.session_state['paste_preset'] = "가지\tKasugamycin\t0.5T\n감자\tDiazinon\t0.01\n사과\tUnknownPest\t0.02"

    with col_work:
        with st.container(border=True):
            st.markdown("###### 📑 Batch Process")
            bc1, bc2 = st.columns(2)
            with bc1: b_dept = st.text_input("의뢰 부서 (일괄)", key="b_d")
            with bc2: b_act = st.selectbox("조치 사항 (일괄)", ["폐기", "반송", "재검사"], key="b_a")
            
            txt_val = st.session_state.get('paste_preset', "")
            txt_in = st.text_area("Data Input", value=txt_val, height=120, placeholder="데이터 붙여넣기")
            
            if st.button("🚀 일괄 분석 시작", type="primary", use_container_width=True):
                if txt_in:
                    try:
                        b_df = pd.read_csv(io.StringIO(txt_in), sep=None, names=['식품','농약','검출량'], engine='python')
                        res_list = []
                        save_cnt = 0
                        bar = st.progress(0)
                        
                        for i, row in b_df.iterrows():
                            f = str(row['식품']).strip()
                            p_raw = str(row['농약']).strip()
                            amt = clean_amount(row['검출량'])
                            
                            # 로직 통합 호출
                            real_p, limit, std = get_limit_info(df, f, p_raw)
                            
                            status = "✅ 적합"
                            if amt > limit:
                                status = "🚨 부적합"
                                add_to_history(b_dept, f, real_p, amt, limit, b_act, std, "일괄분석")
                                save_cnt += 1
                            
                            res_list.append([f, real_p, amt, limit, std, status])
                            bar.progress((i+1)/len(b_df))
                        
                        r_df = pd.DataFrame(res_list, columns=['식품','농약','검출량','기준','구분','판정'])
                        
                        def highlight(val):
                            if "부적합" in val: return 'background-color: #ffe6e6; color: #d63031; font-weight: bold'
                            if "PLS" in val: return 'background-color: #fff9c4'
                            return ''
                        
                        st.dataframe(r_df.style.applymap(highlight, subset=['판정', '구분']), use_container_width=True)
                        if save_cnt > 0: st.error(f"🚨 총 {save_cnt}건 대장 자동 저장 완료")
                        else: st.success("🎉 모두 적합")
                    except Exception as e: st.error(f"오류: {e}")

# ==========================================
# [TAB 3] 통합 관리 대장
# ==========================================
with tab3:
    col_h, col_r = st.columns([4, 1])
    with col_h: st.markdown("##### 📈 통합 품질 관리 대장")
    with col_r: 
        if st.button("🔄 새로고침"): st.rerun()

    if st.session_state['history_df'].empty:
        st.info("등록된 이력이 없습니다.")
    else:
        # 차트 (높이 축소)
        with st.container(border=True):
            st.markdown("###### 📊 Trend Analysis")
            chart_df = st.session_state['history_df'].copy()
            chart_df['월'] = pd.to_datetime(chart_df['검사일자']).dt.strftime('%Y-%m')
            
            cc1, cc2 = st.columns(2)
            with cc1:
                st.caption("📅 월별 발생 추이")
                st.bar_chart(chart_df['월'].value_counts().sort_index(), color="#DA291C", height=150)
            with cc2:
                st.caption("🧪 품목별 빈도 (Top 5)")
                st.bar_chart(chart_df['식품명'].value_counts().head(5), height=150)

        # 상세 대장
        st.markdown("###### 📑 Master Data Grid")
        view_df = st.session_state['history_df'][COLUMNS]

        edited_df = st.data_editor(
            view_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "선택": st.column_config.CheckboxColumn("선택", width="small"),
                "판정": st.column_config.TextColumn(disabled=True),
                "검출량 (mg/kg)": st.column_config.NumberColumn(format="%.4f"),
                "허용기준 (mg/kg)": st.column_config.NumberColumn(format="%.4f"),
            },
            key="history_editor"
        )
        
        b1, b2, b3 = st.columns([1, 1, 4])
        with b1:
            if st.button("🗑️ 선택 삭제", type="primary"):
                rem = edited_df[edited_df['선택'] == False]
                rem['선택'] = False
                st.session_state['history_df'] = rem
                st.rerun()
        with b2:
            if st.button("⚠️ 초기화"):
                st.session_state['history_df'] = pd.DataFrame(columns=COLUMNS)
                st.rerun()
        with b3:
            csv = edited_df.drop(columns=['선택']).to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 Report 다운로드", csv, f"Report_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")

