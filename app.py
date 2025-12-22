import streamlit as st
import pandas as pd
import os
import io
import re
import sqlite3
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
    html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; background-color: #F4F6F9; }
    .top-header {
        background-color: white; padding: 20px 30px; border-top: 5px solid #DA291C;
        border-bottom: 1px solid #e0e0e0; margin-bottom: 25px; border-radius: 0 0 8px 8px;
    }
    .header-title { font-size: 26px; font-weight: 800; color: #2c3e50; }
    .header-subtitle { font-size: 13px; color: #7f8c8d; font-weight: 500; margin-bottom: 5px; }
    div[data-testid="stMetric"] { background-color: white; border-left: 4px solid #DA291C; border-radius: 8px; padding: 15px; border: 1px solid #eee; }
    
    /* 설명 박스 스타일 */
    .info-box {
        background-color: #e3f2fd;
        border-left: 5px solid #2196f3;
        padding: 15px;
        border-radius: 5px;
        font-size: 14px;
        color: #0d47a1;
        margin-bottom: 15px;
    }
    .calc-box {
        background-color: #f9f9f9;
        border: 1px solid #ddd;
        padding: 15px;
        border-radius: 5px;
        font-family: 'Consolas', monospace;
        font-size: 13px;
        color: #333;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. Database Handling ---
DB_FILE = "history.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, 검사일자 TEXT, 의뢰부서 TEXT, 식품명 TEXT, 농약명 TEXT, 검출량 REAL, 허용기준 REAL, 초과량 REAL, 판정 TEXT, 조치내용 TEXT, 적용기준 TEXT, 비고 TEXT)''')
    conn.commit(); conn.close()

def save_to_db(dept, food, pest, amount, limit, action, standard, note=""):
    if not dept: dept = "-"
    excess = round(amount - limit, 4) if amount > limit else 0.0
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("INSERT INTO history (검사일자, 의뢰부서, 식품명, 농약명, 검출량, 허용기준, 초과량, 판정, 조치내용, 적용기준, 비고) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (datetime.now().strftime("%Y-%m-%d %H:%M"), dept, food, pest, amount, limit, excess, "부적합", action, standard, note))
    conn.commit(); conn.close()

def load_history_db():
    conn = sqlite3.connect(DB_FILE)
    try: return pd.read_sql("SELECT * FROM history ORDER BY id DESC", conn)
    except: return pd.DataFrame()
    finally: conn.close()

def delete_ids_from_db(ids):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute(f"DELETE FROM history WHERE id IN ({','.join(['?']*len(ids))})", ids)
    conn.commit(); conn.close()

def clear_all_db():
    conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("DELETE FROM history"); conn.commit(); conn.close()

init_db()

# --- 3. Sidebar ---
with st.sidebar:
    st.markdown("<h2 style='color:#DA291C; text-align:center;'>LOTTE R&D</h2>", unsafe_allow_html=True)
    st.markdown("<div style='text-align:center; font-size:12px; color:#666; margin-bottom:20px;'>Safety Management System</div>", unsafe_allow_html=True)
    with st.container(border=True):
        c1, c2 = st.columns([1, 3])
        with c1: st.write("👤")
        with c2: st.write("**관리자 님**"); st.caption("Analysis Research팀")
    st.markdown("---")
    st.caption("DB Status: Connected 🟢")

# --- 4. Header ---
st.markdown("""
    <div class="top-header">
        <div class="header-subtitle">LOTTE R&D CENTER | Analysis Research Team</div>
        <div class="header-title">🥦 잔류농약 판정 및 부적합 관리 시스템</div>
    </div>
    """, unsafe_allow_html=True)

# --- 5. Logic & Data (오류 수정됨) ---
# 숫자만 추출하는 강력한 함수
def clean_amount(val):
    try: 
        # 문자열로 변환 후 0-9와 .(점)만 남기고 다 삭제
        clean_str = re.sub(r'[^0-9.]', '', str(val))
        if not clean_str: return 0.0 # 빈 값이면 0.0 반환
        return float(clean_str)
    except: return 0.0

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
if df is None: st.error("🚨 data.csv 없음"); st.stop()

food_list = sorted(df['food_type'].unique().tolist())
pesticide_list = sorted(df['pesticide_name'].unique().tolist())
MOISTURE_DB = {"고추": {"raw": 83.0, "dried": 14.0}, "마늘": {"raw": 65.0, "dried": 10.0}, "양파": {"raw": 90.0, "dried": 12.0}}

# ★ [핵심 수정] 기준값 가져올 때 에러 방지 처리 추가 ★
def get_limit_info(df, food, pest_input):
    exact_pest = df[df['pesticide_name'] == pest_input]
    target_pest = pest_input if not exact_pest.empty else pest_input
    if exact_pest.empty:
        partial = df[df['pesticide_name'].str.contains(pest_input, case=False, regex=False)]
        if not partial.empty: target_pest = partial.iloc[0]['pesticide_name']
    
    match = df[(df['food_type'] == food) & (df['pesticide_name'] == target_pest)]
    
    if not match.empty: 
        # ★ 여기서 에러가 났었습니다. clean_amount로 감싸서 해결! ★
        raw_val = match.iloc[0]['limit_mg_kg']
        limit_val = clean_amount(raw_val)
        return target_pest, limit_val, "식약처 고시"
    else: 
        return target_pest, 0.01, "PLS (0.01)"

# --- 6. Dashboard ---
hist = load_history_db()
today_cnt = len(hist[hist['검사일자'].str.contains(datetime.now().strftime("%Y-%m-%d"))]) if not hist.empty else 0
st.markdown("##### 📊 Executive Summary")
k1, k2, k3, k4 = st.columns(4)
with k1: st.metric("누적 부적합", f"{len(hist)}건", delta=f"금일 +{today_cnt}")
with k2: st.metric("Risk 부서", hist['의뢰부서'].mode()[0] if not hist.empty else "-", "High")
with k3: st.metric("주요 품목", hist['식품명'].mode()[0] if not hist.empty else "-", "Check")
with k4: st.metric("시스템 상태", "Stable", "v4.1 Fixed")
st.markdown("---")

# --- 7. Tabs ---
t1, t2, t3, t4, t5 = st.tabs(["🔬 정밀 검사", "🌭 가공식품(건조)", "🥗 복합원재료", "📑 일괄 분석", "📈 통합 대장"])

# [Tab 1: 정밀 검사]
with t1:
    col_info, col_main = st.columns([1, 2])
    with col_info:
        st.markdown("""
        <div class="info-box">
        <b>📘 기준 적용 원칙</b><br><br>
        <b>1. 식품공전 기준 우선 적용</b><br>
        식품의 기준 및 규격에 고시된 잔류허용기준이 있는 경우 해당 기준을 최우선으로 적용합니다.<br><br>
        <b>2. PLS (Positive List System)</b><br>
        기준이 설정되지 않은 농약의 경우, 일률기준인 <b>0.01 mg/kg</b>을 적용하여 불검출 수준으로 관리합니다.
        </div>
        """, unsafe_allow_html=True)
    
    with col_main:
        with st.container(border=True):
            st.markdown("###### 🎯 개별 시료 정밀 분석")
            c1,c2,c3 = st.columns(3)
            with c1: f=st.selectbox("품목", food_list, key="t1f", index=None)
            with c2: p=st.selectbox("농약", pesticide_list, key="t1p", index=None)
            with c3: a=st.number_input("검출량", 0.0, format="%.4f", key="t1a")
            
            if st.button("분석 실행", key="b1", type="primary"):
                if f and p:
                    rp, l, s = get_limit_info(df, f, p)
                    st.session_state['ar'] = {'f':f, 'p':rp, 'a':a, 'l':l, 's':s, 'bad':a>l}
                else: st.warning("선택 필요")
            
            if st.session_state.get('ar'):
                r = st.session_state['ar']
                st.divider()
                st.markdown("###### 🧾 분석 결과 상세")
                rc1, rc2 = st.columns(2)
                with rc1:
                    st.markdown(f"""
                    <div class="calc-box">
                    <b>[기준 조회 결과]</b><br>
                    • 품목: {r['f']}<br>
                    • 농약: {r['p']}<br>
                    • 적용 법규: <b>{r['s']}</b><br>
                    -------------------------<br>
                    <b>📉 허용 기준: {r['l']:.4f} mg/kg</b>
                    </div>
                    """, unsafe_allow_html=True)
                with rc2:
                    if r['bad']:
                        st.error(f"**🚨 판정: 부적합**\n\n초과량: +{r['a']-r['l']:.4f} mg/kg")
                        with st.container(border=True):
                            d = st.text_input("부서", key="t1d")
                            act = st.selectbox("조치", ["폐기","반송"], key="t1act")
                            if st.button("저장", key="t1sv"):
                                save_to_db(d, r['f'], r['p'], r['a'], r['l'], act, r['s'], "정밀")
                                st.toast("DB 저장 완료!"); st.session_state['ar']=None; st.rerun()
                    else: st.success("**✅ 판정: 적합**\n\n안전 관리 기준 이내입니다.")

# [Tab 2: 건조 식품]
with t2:
    col_info, col_main = st.columns([1, 2])
    with col_info:
        st.markdown("""
        <div class="info-box">
        <b>📘 수분 보정 기준 (식약처)</b><br><br>
        건조 등으로 수분 함량이 변화된 경우, 원료의 기준에 수분 감소비율(농축배수)을 곱하여 환산합니다.<br><br>
        <b>[계산 공식]</b><br>
        $$ \\text{계수} = \\frac{100 - \\text{건조수분}}{100 - \\text{원물수분}} $$ <br>
        $$ \\text{환산기준} = \\text{원물기준} \\times \\text{계수} $$
        </div>
        """, unsafe_allow_html=True)

    with col_main:
        with st.container(border=True):
            st.markdown("###### 🌭 건조/가공식품 환산 분석")
            c1, c2 = st.columns(2)
            with c1: rf = st.selectbox("원물", food_list, key="t2f", index=None)
            with c2: tp = st.selectbox("농약", pesticide_list, key="t2p", index=None)
            
            dm_raw, dm_dry = 0.0, 0.0
            if rf in MOISTURE_DB: dm_raw, dm_dry = MOISTURE_DB[rf]['raw'], MOISTURE_DB[rf]['dried']
            
            c1,c2,c3 = st.columns([2,2,1])
            with c1: mr = st.number_input("원물 수분(%)", value=dm_raw, key="tmr")
            with c2: md = st.number_input("건조 수분(%)", value=dm_dry, key="tmd")
            fac = (100-md)/(100-mr) if (100-mr)!=0 else 1.0
            with c3: st.metric("농축 배수", f"{fac:.2f}배")
            
            amt = st.number_input("검출량 (mg/kg)", 0.0, format="%.4f", key="t2a")
            if st.button("환산 판정", type="primary"):
                if rf and tp:
                    rp, l, s = get_limit_info(df, rf, tp)
                    cl = l * fac
                    
                    st.divider()
                    st.markdown("###### 🧾 산출 근거 (Calculation Evidence)")
                    
                    cc1, cc2 = st.columns(2)
                    with cc1:
                         st.markdown(f"""
                        <div class="calc-box">
                        <b>1. 원물 기준 ({s})</b><br>
                        {l} mg/kg<br><br>
                        <b>2. 농축 배수 산출</b><br>
                        (100-{md}) / (100-{mr}) = <b>{fac:.2f}배</b><br><br>
                        <b>3. 최종 환산 기준</b><br>
                        {l} × {fac:.2f} = <b>{cl:.4f} mg/kg</b>
                        </div>
                        """, unsafe_allow_html=True)
                    with cc2:
                        if amt > cl:
                            st.error(f"**🚨 부적합** (+{amt-cl:.4f})")
                            with st.container(border=True):
                                d = st.text_input("부서", key="t2d")
                                act = st.selectbox("조치", ["폐기"], key="t2ac")
                                if st.button("저장", key="t2s"):
                                    save_to_db(d, f"{rf}(건조)", rp, amt, cl, act, "환산", f"원물{l}x{fac:.2f}")
                                    st.toast("저장 완료!"); st.rerun()
                        else: st.success("**✅ 적합**")

# [Tab 3: 복합원재료]
with t3:
    if 'recipe_df' not in st.session_state:
        st.session_state['recipe_df'] = pd.DataFrame([{"원료명": "양상추", "배합비율(%)": 50.0}, {"원료명": "오이", "배합비율(%)": 30.0}])
    
    col_info, col_main = st.columns([1, 2])
    with col_info:
        st.markdown("""
        <div class="info-box">
        <b>📘 가중평균 기준 적용 (식품공전)</b><br><br>
        복합원재료(가공식품)의 경우, 제품에 포함된 각 원재료의 잔류허용기준에 배합비율을 곱하여 합산한 기준을 적용합니다.<br><br>
        <b>[계산 공식]</b><br>
        $$ \\sum (\\text{원료기준} \\times \\text{배합비율}) $$
        </div>
        """, unsafe_allow_html=True)
    
    with col_main:
        with st.container(border=True):
            st.markdown("###### 🥗 가중평균 기준 배합비율 반영")
            c1, c2 = st.columns(2)
            with c1: prod_name = st.text_input("제품명", key="t3_name")
            with c2: target_pest = st.selectbox("농약", pesticide_list, key="t3_pest")
            
            edited_recipe = st.data_editor(st.session_state['recipe_df'], num_rows="dynamic", use_container_width=True, 
                                           column_config={"원료명": st.column_config.SelectboxColumn(options=food_list)})
            
            comp_amt = st.number_input("완제품 검출량", 0.0, format="%.4f", key="t3_amt")
            
            if st.button("복합 기준 산출 및 판정", type="primary"):
                if prod_name and target_pest:
                    final_limit = 0.0
                    calc_log = ""
                    for idx, row in edited_recipe.iterrows():
                        r_f = row['원료명']
                        r_r = row['배합비율(%)'] / 100.0
                        rp, l, s = get_limit_info(df, r_f, target_pest)
                        contrib = l * r_r
                        final_limit += contrib
                        calc_log += f"• {r_f}: 기준 {l} × 비율 {row['배합비율(%)']}% = {contrib:.4f}\n"
                    
                    st.divider()
                    st.markdown("###### 🧾 산출 근거 (Calculation Logic)")
                    
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        st.markdown(f"""
                        <div class="calc-box">
                        <b>[원료별 기여도 계산]</b><br>
                        {calc_log.replace(chr(10), '<br>')}
                        --------------------------------<br>
                        <b>📏 최종 합산 기준: {final_limit:.4f} mg/kg</b>
                        </div>
                        """, unsafe_allow_html=True)
                    with cc2:
                        if comp_amt > final_limit:
                            st.error(f"**🚨 부적합** (+{comp_amt - final_limit:.4f})")
                            with st.container(border=True):
                                d = st.text_input("부서", key="t3d")
                                act = st.selectbox("조치", ["폐기"], key="t3ac")
                                if st.button("저장", key="t3s"):
                                    save_to_db(d, prod_name, target_pest, comp_amt, final_limit, act, "가중평균", f"기준 {final_limit:.4f}")
                                    st.toast("저장 완료!"); st.rerun()
                        else: st.success("**✅ 적합**")

# [Tab 4: 일괄 분석]
with t4:
    col_info, col_main = st.columns([1, 2])
    with col_info:
        st.markdown("""
        <div class="info-box">
        <b>📘 대량 데이터 자동 처리</b><br><br>
        엑셀 등의 데이터를 일괄로 복사하여 붙여넣으면, 각 행마다 <b>[Tab 1]</b>과 동일한 로직(식약처 고시 우선, 없으면 PLS)을 적용하여 자동으로 판정합니다.
        </div>
        """, unsafe_allow_html=True)
        if st.button("📋 테스트 데이터 로드"): st.session_state['pp'] = "가지\tKasugamycin\t0.5T\n감자\tDiazinon\t0.01"

    with col_main:
        with st.container(border=True):
            st.markdown("###### 📑 Batch Process")
            c1,c2=st.columns(2)
            with c1: d=st.text_input("부서", key="t4d")
            with c2: a=st.selectbox("조치", ["폐기"], key="t4a")
            tx = st.text_area("Data", st.session_state.get('pp',""), height=100)
            if st.button("일괄 실행", type="primary"):
                try:
                    bdf = pd.read_csv(io.StringIO(tx), sep=None, names=['식품','농약','검출량'], engine='python')
                    rs, sv = [], 0
                    bar = st.progress(0)
                    for i,r in bdf.iterrows():
                        f,p,v = str(r['식품']).strip(), str(r['농약']).strip(), clean_amount(r['검출량'])
                        rp,l,s = get_limit_info(df,f,p)
                        stt = "✅ 적합"
                        if v>l: stt="🚨 부적합"; save_to_db(d,f,rp,v,l,a,s,"일괄"); sv+=1
                        rs.append([f,rp,v,l,s,stt]); bar.progress((i+1)/len(bdf))
                    st.dataframe(pd.DataFrame(rs, columns=['식품','농약','검출량','기준','구분','판정']).style.applymap(lambda v: 'background-color:#ffe6e6' if '부적합' in v else '', subset=['판정']), use_container_width=True)
                    if sv: st.error(f"{sv}건 저장 완료")
                    else: st.success("완료")
                except: st.error("데이터 형식을 확인하세요.")

# [Tab 5: 통합 대장]
with t5:
    c1, c2 = st.columns([4,1])
    with c1: st.markdown("##### 📈 통합 대장 (Persistent DB)")
    with c2: 
        if st.button("새로고침"): st.rerun()
    
    if not hist.empty:
        with st.container(border=True):
            dfc = hist.copy(); dfc['M'] = pd.to_datetime(dfc['검사일자']).dt.strftime('%Y-%m')
            c1,c2=st.columns(2)
            with c1: st.bar_chart(dfc['M'].value_counts().sort_index(), color="#DA291C", height=150)
            with c2: st.bar_chart(dfc['식품명'].value_counts().head(5), height=150)
        
        hist['선택'] = False
        edf = st.data_editor(hist[['선택','id','검사일자','의뢰부서','식품명','농약명','검출량','허용기준','판정','적용기준','비고']], use_container_width=True, hide_index=True, column_config={"선택":st.column_config.CheckboxColumn(width="small"), "id":st.column_config.NumberColumn(width="small", disabled=True)}, key="he_db")
        
        b1,b2,b3 = st.columns([1,1,4])
        with b1:
            if st.button("선택 삭제"):
                ids = edf[edf['선택']==True]['id'].tolist()
                delete_ids_from_db(ids); st.rerun()
        with b2:
            if st.button("⚠️ 전체 초기화"): st.session_state['confirm']=True
        with b3:
            st.download_button("다운로드", edf.drop(columns=['선택']).to_csv(index=False).encode('utf-8-sig'), "Report.csv")

        if st.session_state.get('confirm'):
            st.warning("정말 삭제하시겠습니까?")
            if st.button("Yes"): clear_all_db(); st.session_state['confirm']=False; st.rerun()
            if st.button("No"): st.session_state['confirm']=False; st.rerun()
    else: st.info("데이터 없음")

