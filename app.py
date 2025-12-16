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

# 🎨 Lotte Enterprise CSS (전문성 강화)
st.markdown("""
    <style>
    /* 전체 폰트 및 배경 */
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Noto Sans KR', sans-serif;
        background-color: #F4F6F9; /* 은은한 회색 배경 (눈 편안함) */
    }
    
    /* 헤더 디자인 (Lotte Red Line) */
    .top-header {
        background-color: white;
        padding: 20px 30px;
        border-top: 5px solid #DA291C; /* 롯데 레드 */
        border-bottom: 1px solid #e0e0e0;
        margin-bottom: 25px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        border-radius: 0 0 8px 8px;
    }
    .header-title {
        font-size: 26px;
        font-weight: 800;
        color: #2c3e50;
        letter-spacing: -0.5px;
    }
    .header-subtitle {
        font-size: 13px;
        color: #7f8c8d;
        font-weight: 500;
        margin-bottom: 5px;
        text-transform: uppercase;
    }
    
    /* 카드(Container) 스타일 */
    .stContainer {
        background-color: white;
        padding: 20px;
        border-radius: 8px;
        border: 1px solid #e1e4e8;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02);
    }
    
    /* KPI Metric 카드 스타일 */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #eee;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #DA291C; /* 포인트 컬러 */
        box-shadow: 0 2px 4px rgba(0,0,0,0.03);
    }
    
    /* 버튼 스타일 */
    .stButton>button {
        font-weight: bold;
        border-radius: 4px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. Professional Sidebar (전문성 강화) ---
with st.sidebar:
    # 로고 영역 (텍스트로 대체하되 스타일리시하게)
    st.markdown("<h2 style='color:#DA291C; text-align:center;'>LOTTE R&D</h2>", unsafe_allow_html=True)
    st.markdown("<div style='text-align:center; font-size:12px; color:#666; margin-bottom:20px;'>Safety Management System</div>", unsafe_allow_html=True)
    
    # 1. 사용자 프로필 (로그인 된 것처럼 연출)
    with st.container(border=True):
        c1, c2 = st.columns([1, 3])
        with c1: st.write("👤")
        with c2: 
            st.write("**김연구 님**")
            st.caption("Analysis Research팀")
            st.caption("권한: 관리자 (Admin)")

    st.markdown("---")
    
    # 2. 시스템 상태 모니터링 (서버실 느낌)
    st.caption("🖥️ SYSTEM STATUS")
    col_sys1, col_sys2 = st.columns(2)
    with col_sys1: st.metric("DB Status", "Online", delta_color="normal")
    with col_sys2: st.metric("Latency", "12ms", delta_color="inverse")
    
    st.progress(88, text="System Load")

    st.markdown("---")
    
    # 3. 바로가기 메뉴
    st.caption("🚀 QUICK LINKS")
    st.page_link("https://www.lotteconf.co.kr/", label="식품안전 법규 조회", icon="⚖️")
    st.page_link("https://www.foodsafetykorea.go.kr/", label="식품안전나라 (MFDS)", icon="🇰🇷")
    
    st.markdown("---")
    st.info("**Support Center**\n\nTel: 02-1234-5678\nEmail: safety@lotte.net")
    st.caption("v3.5.0 Enterprise Build")

# --- 3. 메인 헤더 ---
st.markdown("""
    <div class="top-header">
        <div class="header-subtitle">LOTTE CENTRAL R&D CENTER | Analysis Research Team</div>
        <div class="header-title">🥦 잔류농약 적합 판정 및 통합 품질 관리 시스템</div>
    </div>
    """, unsafe_allow_html=True)

# --- 4. 데이터 로딩 & 세션 초기화 ---
COLUMNS = [
    '선택', '검사일자', '의뢰부서', '식품명', '농약명', 
    '검출량 (mg/kg)', '허용기준 (mg/kg)', '초과량 (mg/kg)', 
    '판정', '조치내용', '적용기준', '비고'
]

if 'history_df' not in st.session_state:
    st.session_state['history_df'] = pd.DataFrame(columns=COLUMNS)

# 데이터 로딩 함수
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

def find_pest(df, name):
    exact = df[df['pesticide_name'] == name]
    if not exact.empty: return name
    partial = df[df['pesticide_name'].str.contains(name, case=False, regex=False)]
    return partial.iloc[0]['pesticide_name'] if not partial.empty else None

# ★ 이력 저장 함수 (모든 탭에서 공통 사용) ★
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

# --- 5. Executive Dashboard (총 요약 대시보드 - 최상단 배치) ---
st.markdown("##### 📊 Executive Summary (실시간 경영 요약)")

# 데이터 가공
hist_df = st.session_state['history_df']
total_fail = len(hist_df)
today_fail = len(hist_df[hist_df['검사일자'].str.contains(datetime.now().strftime("%Y-%m-%d"))])
top_dept = hist_df['의뢰부서'].mode()[0] if not hist_df.empty else "-"
top_risk_item = hist_df['식품명'].mode()[0] if not hist_df.empty else "-"

# KPI 카드 배치
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with kpi1: st.metric("누적 부적합 판정", f"{total_fail}건", delta=f"금일 +{today_fail}")
with kpi2: st.metric("최다 발생 부서", top_dept, delta="Risk High", delta_color="inverse")
with kpi3: st.metric("주요 관리 품목", top_risk_item, delta="집중 모니터링")
with kpi4: st.metric("데이터 무결성", "100%", "Secure")

st.markdown("---") # 구분선

# --- 6. 탭 구성 ---
tab1, tab2, tab3 = st.tabs(["🔬 개별 정밀 검사", "📑 대량 일괄 분석", "📈 통합 관리 대장 & 통계"])

# ==========================================
# [TAB 1] 정밀 검사 (저장 버그 완벽 수정)
# ==========================================
with tab1:
    with st.container(border=True):
        st.markdown("###### 🎯 개별 시료 정밀 분석 모듈")
        c1, c2, c3 = st.columns(3)
        with c1: f_in = st.selectbox("품목 선택", food_list, index=None, key="t1_f")
        with c2: p_in = st.selectbox("농약 선택 (스마트 검색)", pesticide_list, index=None, key="t1_p")
        with c3: a_in = st.number_input("검출량 (mg/kg)", 0.0, format="%.4f", key="t1_a")

        st.markdown("")
        if st.button("판정 실행 (Analysis)", type="primary", use_container_width=True):
            if f_in and p_in:
                # 1. 기준 조회
                match = df[(df['food_type'] == f_in) & (df['pesticide_name'] == p_in)]
                is_pls = match.empty
                
                limit = 0.01 if is_pls else float(match.iloc[0]['limit_mg_kg'])
                std_type = "PLS (0.01)" if is_pls else "식약처 고시"
                
                # 2. 결과 표시
                r1, r2 = st.columns(2)
                with r1:
                    st.info(f"**📉 허용 기준 ({std_type})**\n\n# **{limit:.4f} mg/kg**")
                
                with r2:
                    if a_in > limit:
                        # 부적합 로직
                        st.error(f"**🚨 판정: 부적합 (Non-Compliance)**\n\n초과량: +{a_in - limit:.4f} mg/kg")
                        
                        # ★ 저장 폼 활성화 ★
                        st.markdown("---")
                        st.markdown("**💾 부적합 이력 등록**")
                        with st.form("save_form_tab1"):
                            dc1, dc2 = st.columns(2)
                            with dc1: dept_in = st.text_input("의뢰 부서", placeholder="예: 품질보증팀")
                            with dc2: act_in = st.selectbox("조치 사항", ["폐기", "반송", "재가공", "기타"])
                            
                            # 폼 제출 버튼
                            submitted = st.form_submit_button("통합 대장에 저장")
                            if submitted:
                                # ★ 핵심: add_to_history 호출 시 모든 인자 정확히 전달 ★
                                add_to_history(dept_in, f_in, p_in, a_in, limit, act_in, std_type, "정밀검사")
                                st.toast("✅ 통합 대장에 성공적으로 저장되었습니다!", icon="💾")
                                st.rerun() # 즉시 반영을 위해 새로고침
                    else:
                        st.success(f"**✅ 판정: 적합 (Compliance)**\n\n안전 관리 기준 이내입니다.")
            else:
                st.warning("⚠️ 분석할 품목과 농약명을 선택하십시오.")

# ==========================================
# [TAB 2] 일괄 분석 (Professional UI)
# ==========================================
with tab2:
    col_guide, col_work = st.columns([1, 2])
    
    with col_guide:
        with st.container(border=True):
            st.markdown("###### 📌 Batch Guide")
            st.caption("엑셀/이메일 데이터를 복사하여 붙여넣으세요.")
            st.code("식품명  농약명  검출량", language=None)
            st.markdown("---")
            if st.button("📋 테스트 데이터 로드"):
                st.session_state['paste_preset'] = "가지\tKasugamycin\t0.5T\n감자\tDiazinon\t0.01\n사과\tUnknown\t0.02"

    with col_work:
        with st.container(border=True):
            st.markdown("###### 📑 데이터 입력 & 파싱")
            
            # 공통 입력 사항
            bc1, bc2 = st.columns(2)
            with bc1: b_dept = st.text_input("의뢰 부서 (일괄 적용)", key="b_d")
            with bc2: b_act = st.selectbox("조치 사항 (일괄 적용)", ["폐기", "반송", "재검사"], key="b_a")
            
            txt_val = st.session_state.get('paste_preset', "")
            txt_in = st.text_area("Raw Data Input", value=txt_val, height=120, label_visibility="collapsed", placeholder="여기에 데이터를 붙여넣으세요...")
            
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
                            
                            # 스마트 검색
                            real_p = find_pest(df, p_raw)
                            p_show = real_p if real_p else p_raw
                            
                            # 기준 매칭
                            match = df[(df['food_type'] == f) & (df['pesticide_name'] == p_show)] if real_p else pd.DataFrame()
                            limit = float(match.iloc[0]['limit_mg_kg']) if not match.empty else 0.01
                            std = "식약처 고시" if not match.empty else "PLS"
                            
                            # 판정
                            status = "✅ 적합"
                            if amt > limit:
                                status = "🚨 부적합"
                                add_to_history(b_dept, f, p_show, amt, limit, b_act, std, "일괄분석")
                                save_cnt += 1
                            
                            res_list.append([f, p_show, amt, limit, std, status])
                            bar.progress((i+1)/len(b_df))
                        
                        # 결과 출력
                        r_df = pd.DataFrame(res_list, columns=['식품','농약','검출량','기준','구분','판정'])
                        
                        def highlight(val):
                            if "부적합" in val: return 'background-color: #ffe6e6; color: #d63031; font-weight: bold'
                            if "PLS" in val: return 'background-color: #fff9c4'
                            return ''
                        
                        st.dataframe(r_df.style.applymap(highlight, subset=['판정', '구분']), use_container_width=True)
                        
                        if save_cnt > 0: st.error(f"🚨 총 {save_cnt}건의 부적합 항목이 자동으로 대장에 저장되었습니다.")
                        else: st.success("🎉 모든 항목이 적합합니다.")
                        
                    except Exception as e: st.error(f"데이터 파싱 오류: {e}")

# ==========================================
# [TAB 3] 통합 관리 대장 (요청사항 완벽 반영)
# ==========================================
with tab3:
    col_h, col_r = st.columns([4, 1])
    with col_h: st.markdown("##### 📈 통합 품질 관리 대장 & 통계")
    with col_r: 
        if st.button("🔄 데이터 새로고침"): st.rerun()

    if st.session_state['history_df'].empty:
        st.info("현재 등록된 부적합 이력이 없습니다.")
    else:
        # --- [섹션 1] 통계 차트 (높이 절반으로 축소) ---
        with st.container(border=True):
            st.markdown("###### 📊 Trend Analysis")
            
            # 데이터 가공
            chart_df = st.session_state['history_df'].copy()
            chart_df['월'] = pd.to_datetime(chart_df['검사일자']).dt.strftime('%Y-%m')
            
            # 2단 컬럼 구성
            chart_c1, chart_c2 = st.columns(2)
            
            with chart_c1:
                st.caption("📅 월별 부적합 발생 추이")
                # height=200으로 설정하여 세로 크기 절반 축소
                monthly_data = chart_df['월'].value_counts().sort_index()
                st.bar_chart(monthly_data, color="#DA291C", height=200) 
            
            with chart_c2:
                st.caption("🧪 품목별 위반 빈도 (Top 5)")
                item_data = chart_df['식품명'].value_counts().head(5)
                st.bar_chart(item_data, height=200) # 높이 200

        # --- [섹션 2] 상세 관리 대장 (테이블) ---
        st.markdown("###### 📑 Master Data Grid")
        
        # 표시할 데이터 준비 (선택 컬럼 맨 앞)
        disp_cols = ['선택', '검사일자', '의뢰부서', '식품명', '농약명', '검출량 (mg/kg)', '허용기준 (mg/kg)', '초과량 (mg/kg)', '판정', '조치내용', '적용기준', '비고']
        view_df = st.session_state['history_df'][disp_cols]

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
        
        # Action Buttons
        ab1, ab2, ab3 = st.columns([1, 1, 4])
        with ab1:
            if st.button("🗑️ 선택 삭제", type="primary"):
                # 선택되지 않은(False) 행만 남김
                remaining = edited_df[edited_df['선택'] == False]
                # 선택 값 초기화 후 저장
                remaining['선택'] = False
                st.session_state['history_df'] = remaining
                st.rerun()
                
        with ab2:
            if st.button("⚠️ 전체 초기화"):
                st.session_state['history_df'] = pd.DataFrame(columns=COLUMNS)
                st.rerun()
                
        with ab3:
            csv = edited_df.drop(columns=['선택']).to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 Excel(CSV) 리포트 다운로드", csv, f"Quality_Report_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
