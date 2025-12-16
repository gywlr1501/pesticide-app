import streamlit as st
import pandas as pd
import os
import io
import re
from datetime import datetime

# --- 1. 기본 설정 (엔터프라이즈급 레이아웃) ---
st.set_page_config(page_title="롯데중앙연구소 잔류농약 판정 시스템", page_icon="🏢", layout="wide")

# 🎨 전문적인 UI/UX 스타일링 (Lotte Red 포인트 적용)
st.markdown("""
    <style>
    /* 전체 폰트 및 배경 설정 */
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* 헤더 스타일 - 롯데 레드 라인 */
    .header-container {
        padding: 20px;
        background-color: white;
        border-top: 5px solid #DA291C; /* 롯데 레드 */
        border-bottom: 1px solid #ddd;
        border-radius: 5px;
        margin-bottom: 20px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    
    /* 텍스트 스타일 */
    .sub-title {
        color: #666;
        font-size: 14px;
        margin-bottom: 5px;
    }
    .main-title {
        color: #333;
        font-size: 28px;
        font-weight: 700;
    }
    
    /* 입력창 스타일 */
    .stTextArea textarea {
        font-family: 'Consolas', monospace;
        background-color: #ffffff;
        border: 1px solid #ddd;
    }
    
    /* 카드 스타일 UI */
    .custom-card {
        background-color: white;
        padding: 20px;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 사이드바 (소속 명시) ---
with st.sidebar:
    st.markdown("### 🏢 LOTTE R&D Center")
    st.markdown("**Analysis Research팀**")
    st.markdown("---")
    st.info("""
    **시스템 정보**
    - **System**: 잔류농약 통합 판정
    - **Version**: v3.0 (Enterprise)
    - **기준**: 2025년 PLS 적용
    - **관리**: Analysis Research팀
    """)
    st.caption("Copyright © 2025 LOTTE R&D Center. All rights reserved.")

# --- 3. 메인 헤더 (커스텀 HTML) ---
st.markdown("""
    <div class="header-container">
        <div class="sub-title">롯데중앙연구소 Analysis Research팀</div>
        <div class="main-title">🥦 잔류농약 적합 판정 & 통합 관리 시스템</div>
    </div>
    """, unsafe_allow_html=True)

# --- 4. 데이터 로딩 ---
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

with st.spinner('사내 데이터베이스에 연결 중입니다...'):
    df = load_data()

if df is None:
    st.error("🚨 시스템 데이터 파일(data.csv)이 누락되었습니다. 관리자에게 문의하세요.")
    st.stop()

food_list = sorted(df['food_type'].unique().tolist())
pesticide_list = sorted(df['pesticide_name'].unique().tolist())

# --- 5. 유틸리티 함수 ---
def clean_amount(val):
    try: return float(re.sub(r'[^0-9.]', '', str(val)))
    except: return 0.0

def find_pest(df, name):
    exact = df[df['pesticide_name'] == name]
    if not exact.empty: return name
    partial = df[df['pesticide_name'].str.contains(name, case=False, regex=False)]
    return partial.iloc[0]['pesticide_name'] if not partial.empty else None

# --- 6. 이력 저장소 ---
if 'history_df' not in st.session_state:
    st.session_state['history_df'] = pd.DataFrame(columns=[
        '선택', '검사일자', '의뢰부서', '식품명', '농약명', 
        '검출량', '허용기준', '판정', '비고'
    ])

def add_to_history(dept, food, pest, amount, limit, note):
    if not dept: dept = "-"
    new_row = {
        '선택': False,
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

# --- 7. 대시보드 (상단 요약) ---
if not st.session_state['history_df'].empty:
    with st.container(border=True):
        st.markdown("#### 📊 실시간 모니터링 현황")
        hist = st.session_state['history_df']
        c1, c2, c3, c4 = st.columns(4)
        
        with c1: st.metric("금일 누적 부적합", f"{len(hist)}건", delta="Real-time")
        with c2: st.metric("최다 발생 부서", hist['의뢰부서'].mode()[0] if not hist.empty else "-")
        with c3: st.metric("주요 검출 농약", hist['농약명'].mode()[0] if not hist.empty else "-")
        with c4: st.metric("시스템 상태", "정상 가동", delta_color="normal")

st.write("") # 여백

# --- 8. 탭 메뉴 ---
tab1, tab2, tab3 = st.tabs(["🔍 정밀 검사", "📑 일괄 분석(Excel)", "📈 통합 관리 대장 (통계)"])

# ==========================================
# [탭 1] 정밀 검사
# ==========================================
with tab1:
    st.markdown("##### 🔬 개별 시료 정밀 분석")
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1: f_in = st.selectbox("식품명", food_list, index=None, key="s_f")
        with c2: p_in = st.selectbox("농약명 (검색 지원)", pesticide_list, index=None, key="s_p")
        with c3: a_in = st.number_input("검출량 (mg/kg)", 0.0, format="%.4f", key="s_a")
        
        st.divider()
        
        if st.button("분석 실행", type="primary", use_container_width=True):
            if f_in and p_in:
                match = df[(df['food_type'] == f_in) & (df['pesticide_name'] == p_in)]
                is_pls = match.empty
                limit = 0.01 if is_pls else float(match.iloc[0]['limit_mg_kg'])
                std_type = "PLS 일률기준" if is_pls else "식약처 고시"
                
                c_res1, c_res2 = st.columns(2)
                
                # 결과 카드 디자인
                with c_res1:
                    st.info(f"**적용 기준: {std_type}**\n\n허용 기준치: **{limit} mg/kg**")
                
                with c_res2:
                    if a_in > limit:
                        st.error(f"**판정: 부적합 🚨**\n\n초과량: +{a_in - limit:.4f} mg/kg")
                        # 저장 로직
                        with st.expander("💾 이력 대장 등록", expanded=True):
                            d_in = st.text_input("의뢰 부서", placeholder="예: 생명공학팀", key="s_d")
                            act = st.selectbox("조치", ["폐기", "반송", "재검사"], key="s_act")
                            if st.button("저장"):
                                add_to_history(d_in, f_in, p_in, a_in, limit, f"{act} (개별)")
                                st.toast("대장에 저장되었습니다.", icon="✅")
                                st.rerun()
                    else:
                        st.success(f"**판정: 적합 ✅**\n\n안전한 수준입니다.")
            else:
                st.warning("식품명과 농약명을 모두 선택해주세요.")

# ==========================================
# [탭 2] 일괄 분석
# ==========================================
with tab2:
    st.markdown("##### 📑 대량 데이터 일괄 처리")
    
    col_guide, col_action = st.columns([1, 2])
    
    with col_guide:
        with st.container(border=True):
            st.markdown("**📌 사용 가이드**")
            st.caption("엑셀 데이터를 복사하여 붙여넣으세요.")
            st.code("식품명  농약명  검출량", language=None)
            if st.button("테스트 데이터 입력"):
                st.session_state['paste_preset'] = "가지\tKasugamycin\t0.5T\n감자\tDiazinon\t0.01"
    
    with col_action:
        d_batch = st.text_input("의뢰 부서 (선택사항)", placeholder="미입력 시 '-'로 저장", key="b_d")
        txt_val = st.session_state.get('paste_preset', "")
        txt_in = st.text_area("데이터 입력", value=txt_val, height=150, placeholder="여기에 데이터를 붙여넣으세요.")
        
        if st.button("🚀 일괄 분석 시작", type="primary", use_container_width=True):
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
                    
                    # 결과 테이블
                    r_df = pd.DataFrame(res, columns=['식품','농약','검출량','기준','구분','판정'])
                    def color_row(val):
                        if "부적합" in val: return 'background-color: #ffe6e6; color: #d63031; font-weight: bold'
                        if "PLS" in val: return 'background-color: #fff9c4; color: #333'
                        return ''
                    
                    st.dataframe(r_df.style.applymap(color_row, subset=['판정', '구분']), use_container_width=True)
                    
                    if saved > 0: st.error(f"🚨 **{saved}건의 부적합** 항목이 관리 대장에 자동 등록되었습니다.")
                    else: st.success("🎉 모든 항목이 적합합니다.")
                    
                except Exception as e: st.error(f"데이터 처리 오류: {e}")

# ==========================================
# [탭 3] 통합 관리 대장 (월별 차트 추가!)
# ==========================================
with tab3:
    c_h, c_r = st.columns([4, 1])
    with c_h: st.markdown("##### 📋 부적합 이력 및 통계 분석")
    with c_r: 
        if st.button("🔄 데이터 새로고침"): st.rerun()

    if st.session_state['history_df'].empty:
        st.info("현재 등록된 부적합 이력이 없습니다.")
    else:
        # --- 1. 통계 대시보드 (차트 영역) ---
        with st.container(border=True):
            st.markdown("###### 📈 Analysis Dashboard")
            
            # 데이터 전처리 (날짜 변환)
            chart_df = st.session_state['history_df'].copy()
            chart_df['검사일자'] = pd.to_datetime(chart_df['검사일자'])
            chart_df['월'] = chart_df['검사일자'].dt.strftime('%Y-%m') # 월별 그룹핑

            tab_c1, tab_c2 = st.tabs(["📅 월별 추세", "📊 항목별 분포"])
            
            # [차트 1] 월별 발생 추이 (요청하신 기능!)
            with tab_c1:
                monthly_counts = chart_df['월'].value_counts().sort_index()
                st.bar_chart(monthly_counts, color="#DA291C") # 롯데 레드 컬러
                st.caption("※ 월별 부적합 발생 건수 추이")

            # [차트 2] 식품/농약별 분포
            with tab_c2:
                cc1, cc2 = st.columns(2)
                with cc1:
                    st.write("**식품별 빈도**")
                    st.bar_chart(chart_df['식품명'].value_counts())
                with cc2:
                    st.write("**농약별 빈도**")
                    st.bar_chart(chart_df['농약명'].value_counts())

        st.markdown("---")

        # --- 2. 관리 대장 (테이블) ---
        st.write("###### 📑 상세 이력 관리")
        
        # 체크박스 컬럼 맨 앞으로
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
        
        # 버튼 액션
        bt1, bt2, bt3 = st.columns([1, 1, 4])
        with bt1:
            if st.button("🗑️ 선택 삭제", type="primary"):
                rows_left = edited_df[edited_df['선택'] == False]
                rows_left['선택'] = False
                st.session_state['history_df'] = rows_left
                st.rerun()
        with bt2:
            if st.button("⚠️ 전체 초기화"):
                st.session_state['history_df'] = st.session_state['history_df'].iloc[0:0]
                st.rerun()
        with bt3:
            csv = edited_df.drop(columns=['선택']).to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 Excel 다운로드", csv, f"Lotte_R&D_Report_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
