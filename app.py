import streamlit as st
import pandas as pd
import os
import io
import re
from datetime import datetime

# --- 1. 기본 설정 ---
st.set_page_config(page_title="롯데중앙연구소 잔류농약 판정 시스템", page_icon="🏢", layout="wide")

# 🎨 스타일링 (컴팩트 & 전문적)
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    .header-container {
        padding: 15px; /* 패딩 축소 */
        background-color: white;
        border-top: 4px solid #DA291C;
        border-bottom: 1px solid #ddd;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .main-title { color: #333; font-size: 24px; font-weight: 700; } /* 폰트 사이즈 축소 */
    .sub-title { color: #666; font-size: 12px; margin-bottom: 2px; }
    
    /* 카드 스타일 */
    .custom-card {
        background-color: white;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    /* 폰트 적용 */
    .stTextArea textarea { font-family: 'Consolas', monospace; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 사이드바 ---
with st.sidebar:
    st.markdown("### 🏢 LOTTE R&D")
    st.markdown("**Analysis Research팀**")
    st.markdown("---")
    st.caption("System v3.1 (Hotfix)")

# --- 3. 헤더 ---
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

with st.spinner('시스템 로딩 중...'):
    df = load_data()

if df is None:
    st.error("🚨 data.csv 파일 확인 필요")
    st.stop()

food_list = sorted(df['food_type'].unique().tolist())
pesticide_list = sorted(df['pesticide_name'].unique().tolist())

# --- 5. 유틸리티 ---
def clean_amount(val):
    try: return float(re.sub(r'[^0-9.]', '', str(val)))
    except: return 0.0

def find_pest(df, name):
    exact = df[df['pesticide_name'] == name]
    if not exact.empty: return name
    partial = df[df['pesticide_name'].str.contains(name, case=False, regex=False)]
    return partial.iloc[0]['pesticide_name'] if not partial.empty else None

# --- 6. 이력 저장소 (컬럼명 표준화 및 단위 포함) ---
# 형광펜 문제 해결: 컬럼 이름을 하나로 통일합니다.
COLUMNS = [
    '선택', '검사일자', '의뢰부서', '식품명', '농약명', 
    '검출량 (mg/kg)', '허용기준 (mg/kg)', '초과량 (mg/kg)', 
    '판정', '조치내용', '적용기준', '비고'
]

if 'history_df' not in st.session_state:
    st.session_state['history_df'] = pd.DataFrame(columns=COLUMNS)

# 예전 버전의 데이터가 세션에 남아있으면 충돌나므로 컬럼이 다르면 초기화 (안전장치)
if not st.session_state['history_df'].empty:
    if '검출량' in st.session_state['history_df'].columns: # 구버전 데이터 감지
        st.session_state['history_df'] = pd.DataFrame(columns=COLUMNS) # 초기화

def add_to_history(dept, food, pest, amount, limit, action, standard, note=""):
    if not dept: dept = "-"
    
    # 초과량 계산
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

# --- 7. 상단 미니 현황판 (사이즈 축소) ---
if not st.session_state['history_df'].empty:
    hist = st.session_state['history_df']
    # 컨테이너 없이 바로 컬럼 사용해서 공간 절약
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("🚨 금일 부적합", f"{len(hist)}건")
    with m2: st.metric("📂 최다 부서", hist['의뢰부서'].mode()[0] if not hist.empty else "-")
    with m3: st.metric("⚠️ 주요 농약", hist['농약명'].mode()[0] if not hist.empty else "-")
    with m4: st.metric("⚡ 시스템", "정상")
    st.markdown("---")

# --- 8. 탭 메뉴 ---
tab1, tab2, tab3 = st.tabs(["🔍 정밀 검사", "📑 일괄 분석", "📈 통합 관리 대장"])

# ==========================================
# [탭 1] 정밀 검사 (저장 기능 수정 완료)
# ==========================================
with tab1:
    with st.container(border=True):
        st.markdown("###### 🔬 개별 시료 정밀 분석")
        c1, c2, c3 = st.columns(3)
        with c1: f_in = st.selectbox("식품명", food_list, index=None, key="s_f")
        with c2: p_in = st.selectbox("농약명", pesticide_list, index=None, key="s_p")
        with c3: a_in = st.number_input("검출량 (mg/kg)", 0.0, format="%.4f", key="s_a")
        
        st.write("")
        if st.button("분석 실행", type="primary", use_container_width=True):
            if f_in and p_in:
                match = df[(df['food_type'] == f_in) & (df['pesticide_name'] == p_in)]
                is_pls = match.empty
                limit = 0.01 if is_pls else float(match.iloc[0]['limit_mg_kg'])
                std_type = "PLS 일률기준" if is_pls else "식약처 고시"
                
                c_res1, c_res2 = st.columns(2)
                with c_res1:
                    st.info(f"**적용 기준: {std_type}**\n\n허용 기준: **{limit} mg/kg**")
                
                with c_res2:
                    if a_in > limit:
                        st.error(f"**🚨 부적합** (+{a_in - limit:.4f} 초과)")
                        
                        # [수정됨] 저장 로직을 add_to_history의 새 양식에 맞춤
                        with st.container(border=True):
                            st.caption("📝 이력 대장 등록")
                            d_col, a_col = st.columns(2)
                            with d_col: d_in = st.text_input("의뢰 부서", key="s_d")
                            with a_col: act = st.selectbox("조치", ["폐기", "반송", "재검사"], key="s_act")
                            
                            if st.button("💾 저장하기", key="btn_save_tab1"):
                                # 모든 인자를 빠짐없이 전달!
                                add_to_history(d_in, f_in, p_in, a_in, limit, act, std_type, "개별분석")
                                st.toast("대장에 저장되었습니다!", icon="✅")
                                st.rerun() # 화면 갱신해서 3번 탭에 반영
                    else:
                        st.success("✅ 적합 (안전)")
            else:
                st.warning("항목을 선택해주세요.")

# ==========================================
# [탭 2] 일괄 분석 (컬럼 매칭 수정 완료)
# ==========================================
with tab2:
    col_g, col_a = st.columns([1, 2])
    with col_g:
        st.info("💡 엑셀 복사: 식품명 농약명 검출량")
        if st.button("예시 입력"):
            st.session_state['paste_preset'] = "가지\tKasugamycin\t0.5T\n감자\tDiazinon\t0.01"
    
    with col_a:
        with st.container(border=True):
            bc1, bc2 = st.columns(2)
            with bc1: d_batch = st.text_input("부서명 (선택)", key="b_d")
            with bc2: act_batch = st.selectbox("부적합 조치", ["폐기", "반송", "재검사"], key="b_act")
            
            txt_val = st.session_state.get('paste_preset', "")
            txt_in = st.text_area("데이터 입력", value=txt_val, height=100, label_visibility="collapsed", placeholder="데이터 붙여넣기")
            
            if st.button("🚀 일괄 분석", type="primary", use_container_width=True):
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
                            
                            status, note = "✅ 적합", ""
                            if amt > limit:
                                status = "🚨 부적합"
                                note = f"(+{amt-limit:.4f})"
                                # 일괄 저장 시에도 모든 컬럼 매핑
                                add_to_history(d_batch, f, p_show, amt, limit, act_batch, res_type, "일괄분석")
                                saved += 1
                            
                            res.append([f, p_show, amt, limit, res_type, status, note])
                            bar.progress((i+1)/len(b_df))
                        
                        r_df = pd.DataFrame(res, columns=['식품','농약','검출량','기준','구분','판정','비고'])
                        
                        # 스타일링
                        def color_row(val):
                            if "부적합" in val: return 'background-color: #ffe6e6; color: #d63031; font-weight: bold'
                            if "PLS" in val: return 'background-color: #fff9c4'
                            return ''
                        st.dataframe(r_df.style.applymap(color_row, subset=['판정', '구분']), use_container_width=True)
                        
                        if saved > 0: st.error(f"🚨 {saved}건 부적합 -> 대장 자동 저장 완료")
                        else: st.success("🎉 모두 적합")
                    except Exception as e: st.error(f"오류: {e}")

# ==========================================
# [탭 3] 통합 관리 대장 (사이즈 축소 & 데이터 표시 수정)
# ==========================================
with tab3:
    c_h, c_r = st.columns([4, 1])
    with c_h: st.markdown("##### 📋 부적합 이력 및 통계")
    with c_r: 
        if st.button("🔄 새로고침"): st.rerun()

    if st.session_state['history_df'].empty:
        st.info("등록된 이력이 없습니다.")
    else:
        # 1. 통계 차트 (사이즈 축소: 2단 컬럼으로 배치)
        with st.expander("📊 통계 대시보드 열기/닫기", expanded=True):
            chart_df = st.session_state['history_df'].copy()
            chart_df['월'] = pd.to_datetime(chart_df['검사일자']).dt.strftime('%Y-%m')
            
            # 차트 높이 제한을 위해 컬럼 분할 비율 조정
            tc1, tc2 = st.columns([1, 1]) 
            
            with tc1:
                st.caption("📅 월별 추세")
                st.bar_chart(chart_df['월'].value_counts().sort_index(), color="#DA291C", height=200) # 높이 200으로 축소
            
            with tc2:
                st.caption("🍆 품목별 빈도 (Top 5)")
                # 상위 5개만 짤라서 보여줌 (깔끔하게)
                top_foods = chart_df['식품명'].value_counts().head(5)
                st.bar_chart(top_foods, height=200)

        # 2. 관리 대장 테이블
        st.write("###### 📑 상세 목록")
        
        # 컬럼 순서 재정렬 (선택이 맨 앞)
        cols_ordered = ['선택', '검사일자', '의뢰부서', '식품명', '농약명', 
                        '검출량 (mg/kg)', '허용기준 (mg/kg)', '초과량 (mg/kg)', 
                        '판정', '조치내용', '적용기준', '비고']
        
        # 데이터가 있는 경우만 보여주기 (컬럼 매칭 확인용)
        display_df = st.session_state['history_df'][cols_ordered]

        edited_df = st.data_editor(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "선택": st.column_config.CheckboxColumn("선택", width="small"),
                "판정": st.column_config.TextColumn(disabled=True),
                "검출량 (mg/kg)": st.column_config.NumberColumn(format="%.4f"),
                "허용기준 (mg/kg)": st.column_config.NumberColumn(format="%.4f"),
                "초과량 (mg/kg)": st.column_config.NumberColumn(format="%.4f"),
            },
            key="history_editor"
        )
        
        # 버튼 그룹
        b1, b2, b3 = st.columns([1, 1, 3])
        with b1:
            if st.button("🗑️ 선택 삭제", type="primary"):
                remain = edited_df[edited_df['선택'] == False]
                remain['선택'] = False
                st.session_state['history_df'] = remain
                st.rerun()
        with b2:
            if st.button("⚠️ 전체 초기화"):
                st.session_state['history_df'] = st.session_state['history_df'].iloc[0:0]
                st.rerun()
        with b3:
            csv = edited_df.drop(columns=['선택']).to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 Excel 다운로드", csv, f"Report_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
