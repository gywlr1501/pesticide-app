import streamlit as st
import pandas as pd
import os
import io
import re
import sqlite3 # 영구 저장을 위한 DB 라이브러리
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
    </style>
    """, unsafe_allow_html=True)

# --- 2. Database Handling (SQLite 영구 저장) ---
DB_FILE = "history.db"

def init_db():
    """DB 테이블이 없으면 생성"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            검사일자 TEXT,
            의뢰부서 TEXT,
            식품명 TEXT,
            농약명 TEXT,
            검출량 REAL,
            허용기준 REAL,
            초과량 REAL,
            판정 TEXT,
            조치내용 TEXT,
            적용기준 TEXT,
            비고 TEXT
        )
    ''')
    conn.commit()
    conn.close()

def load_history_db():
    """DB에서 데이터 불러오기"""
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql("SELECT * FROM history ORDER BY id DESC", conn)
        return df
    except:
        return pd.DataFrame()
    finally:
        conn.close()

def save_to_db(dept, food, pest, amount, limit, action, standard, note=""):
    """DB에 데이터 한 줄 저장"""
    if not dept: dept = "-"
    excess = round(amount - limit, 4) if amount > limit else 0.0
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO history (검사일자, 의뢰부서, 식품명, 농약명, 검출량, 허용기준, 초과량, 판정, 조치내용, 적용기준, 비고)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (date_str, dept, food, pest, amount, limit, excess, "부적합", action, standard, note))
    conn.commit()
    conn.close()

def delete_ids_from_db(ids):
    """선택한 ID 삭제"""
    if not ids: return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    placeholders = ', '.join('?' * len(ids))
    c.execute(f"DELETE FROM history WHERE id IN ({placeholders})", ids)
    conn.commit()
    conn.close()

def clear_all_db():
    """전체 초기화"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM history")
    conn.commit()
    conn.close()

# 앱 시작 시 DB 초기화 확인
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
        <div class="header-title">🥦 잔류농약 적합 판정 및 통합 품질 관리 시스템</div>
    </div>
    """, unsafe_allow_html=True)

# --- 5. Data Loading & Logic Fix ---
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

# ★ [수정됨] PLS 로직 강화: DB 매칭 우선순위 엄격 적용 ★
def get_limit_info(df, food, pest_input):
    # 1. 농약 이름 매칭 (정확 -> 포함 순)
    exact_pest = df[df['pesticide_name'] == pest_input]
    target_pest = pest_input 
    
    if not exact_pest.empty:
        target_pest = pest_input # 정확히 일치하는 이름 있음
    else:
        # 부분 일치 검색 (대소문자 무시)
        partial = df[df['pesticide_name'].str.contains(pest_input, case=False, regex=False)]
        if not partial.empty: 
            target_pest = partial.iloc[0]['pesticide_name'] # DB에 있는 정식 명칭으로 교체

    # 2. (식품 + 농약) 조합으로 기준 검색
    match = df[(df['food_type'] == food) & (df['pesticide_name'] == target_pest)]
    
    # 3. 판정 로직
    if not match.empty:
        # ★ DB에 값이 있으면 무조건 그 값을 리턴 (PLS 아님) ★
        return target_pest, float(match.iloc[0]['limit_mg_kg']), "식약처 고시"
    else:
        # ★ DB에 값이 '없을 때만' 0.01 리턴 ★
        return target_pest, 0.01, "PLS (0.01)"

def clean_amount(val):
    try: return float(re.sub(r'[^0-9.]', '', str(val)))
    except: return 0.0

# --- 6. Dashboard (DB 연동) ---
hist = load_history_db() # 이제 DB에서 불러옴
today = datetime.now().strftime("%Y-%m-%d")
today_cnt = len(hist[hist['검사일자'].str.contains(today)]) if not hist.empty else 0

st.markdown("##### 📊 Executive Summary")
k1, k2, k3, k4 = st.columns(4)
with k1: st.metric("누적 부적합", f"{len(hist)}건", delta=f"금일 +{today_cnt}")
with k2: st.metric("Risk 부서", hist['의뢰부서'].mode()[0] if not hist.empty else "-", "High")
with k3: st.metric("주요 품목", hist['식품명'].mode()[0] if not hist.empty else "-", "Check")
with k4: st.metric("DB 시스템", "Persistent", "Safe")
st.markdown("---")

# --- 7. Tabs ---
t1, t2, t3, t4, t5 = st.tabs(["🔬 정밀 검사", "🌭 가공식품(건조)", "🥗 복합원재료", "📑 일괄 분석", "📈 통합 대장"])

# [Tab 1: 정밀]
with t1:
    with st.container(border=True):
        c1,c2,c3 = st.columns(3)
        with c1: f=st.selectbox("품목", food_list, key="t1f", index=None)
        with c2: p=st.selectbox("농약", pesticide_list, key="t1p", index=None)
        with c3: a=st.number_input("검출량", 0.0, format="%.4f", key="t1a")
        
        if st.button("분석", key="b1", type="primary"):
            if f and p:
                rp, l, s = get_limit_info(df, f, p)
                st.session_state['ar'] = {'f':f, 'p':rp, 'a':a, 'l':l, 's':s, 'bad':a>l}
            else: st.warning("선택 필요")
        
        if st.session_state.get('ar'):
            r = st.session_state['ar']
            st.divider()
            c1, c2 = st.columns(2)
            with c1: st.info(f"**기준 ({r['s']})**: {r['l']:.4f}")
            with c2:
                if r['bad']:
                    st.error(f"**부적합** (+{r['a']-r['l']:.4f})")
                    with st.container(border=True):
                        d = st.text_input("부서", key="t1d")
                        act = st.selectbox("조치", ["폐기","반송"], key="t1act")
                        if st.button("저장", key="t1sv"):
                            save_to_db(d, r['f'], r['p'], r['a'], r['l'], act, r['s'], "정밀")
                            st.toast("DB 저장 완료!"); st.session_state['ar']=None; st.rerun()
                else: st.success("적합")

# [Tab 2: 건조]
with t2:
    ci, cc = st.columns([1,2])
    with ci: st.info("**수분 환산 공식**")
    with cc:
        with st.container(border=True):
            c1, c2 = st.columns(2)
            with c1: rf = st.selectbox("원물", food_list, key="t2f", index=None)
            with c2: tp = st.selectbox("농약", pesticide_list, key="t2p", index=None)
            
            dm_raw, dm_dry = 0.0, 0.0
            if rf in MOISTURE_DB: dm_raw, dm_dry = MOISTURE_DB[rf]['raw'], MOISTURE_DB[rf]['dried']
            
            c1,c2,c3 = st.columns([2,2,1])
            with c1: mr = st.number_input("원물 수분", value=dm_raw, key="tmr")
            with c2: md = st.number_input("건조 수분", value=dm_dry, key="tmd")
            fac = (100-md)/(100-mr) if (100-mr)!=0 else 1.0
            with c3: st.metric("배수", f"{fac:.2f}배")
            
            amt = st.number_input("검출량", 0.0, format="%.4f", key="t2a")
            if st.button("환산 판정", type="primary"):
                if rf and tp:
                    rp, l, s = get_limit_info(df, rf, tp)
                    cl = l * fac
                    st.divider()
                    c1, c2 = st.columns(2)
                    with c1: st.info(f"원물({l}) x {fac:.2f} = **{cl:.4f}**")
                    with c2:
                        if amt > cl:
                            st.error(f"**부적합** (+{amt-cl:.4f})")
                            with st.container(border=True):
                                d = st.text_input("부서", key="t2d")
                                act = st.selectbox("조치", ["폐기"], key="t2ac")
                                if st.button("저장", key="t2s"):
                                    save_to_db(d, f"{rf}(건조)", rp, amt, cl, act, "환산", f"원물{l}x{fac:.2f}")
                                    st.toast("DB 저장!"); st.rerun()
                        else: st.success("적합")

# [Tab 3: 복합]
with t3:
    if 'recipe_df' not in st.session_state:
        st.session_state['recipe_df'] = pd.DataFrame([{"원료명": "양상추", "배합비율(%)": 50.0}, {"원료명": "오이", "배합비율(%)": 30.0}])
    
    col_l, col_r = st.columns([1, 2])
    with col_l: st.info("**가중평균 기준**\n배합비율 반영")
    with col_r:
        with st.container(border=True):
            c1, c2 = st.columns(2)
            with c1: prod_name = st.text_input("제품명", key="t3_name")
            with c2: target_pest = st.selectbox("농약", pesticide_list, key="t3_pest")
            
            edited_recipe = st.data_editor(st.session_state['recipe_df'], num_rows="dynamic", use_container_width=True, 
                                           column_config={"원료명": st.column_config.SelectboxColumn(options=food_list)})
            
            comp_amt = st.number_input("완제품 검출량", 0.0, format="%.4f", key="t3_amt")
            
            if st.button("판정", type="primary"):
                if prod_name and target_pest:
                    final_limit = 0.0
                    for idx, row in edited_recipe.iterrows():
                        rp, l, s = get_limit_info(df, row['원료명'], target_pest)
                        final_limit += l * (row['배합비율(%)'] / 100.0)
                    
                    st.divider()
                    c1,c2 = st.columns(2)
                    with c1: st.info(f"계산된 기준: **{final_limit:.4f}**")
                    with c2:
                        if comp_amt > final_limit:
                            st.error(f"**부적합** (+{comp_amt - final_limit:.4f})")
                            with st.container(border=True):
                                d = st.text_input("부서", key="t3d")
                                act = st.selectbox("조치", ["폐기"], key="t3ac")
                                if st.button("저장", key="t3s"):
                                    save_to_db(d, prod_name, target_pest, comp_amt, final_limit, act, "가중평균", f"기준 {final_limit:.4f}")
                                    st.toast("DB 저장!"); st.rerun()
                        else: st.success("적합")

# [Tab 4: 일괄]
with t4:
    ci, cw = st.columns([1,2])
    with ci: 
        st.info("엑셀 복붙")
        if st.button("테스트"): st.session_state['pp'] = "가지\tKasugamycin\t0.5T\n감자\tDiazinon\t0.01"
    with cw:
        with st.container(border=True):
            c1,c2=st.columns(2)
            with c1: d=st.text_input("부서", key="t4d")
            with c2: a=st.selectbox("조치", ["폐기"], key="t4a")
            tx = st.text_area("Data", st.session_state.get('pp',""), height=100)
            if st.button("실행", type="primary"):
                try:
                    bdf = pd.read_csv(io.StringIO(tx), sep=None, names=['식품','농약','검출량'], engine='python')
                    rs, sv = [], 0
                    bar = st.progress(0)
                    for i,r in bdf.iterrows():
                        f,p,v = str(r['식품']).strip(), str(r['농약']).strip(), clean_amount(r['검출량'])
                        rp,l,s = get_limit_info(df,f,p)
                        stt = "적합"
                        if v>l: stt="부적합"; save_to_db(d,f,rp,v,l,a,s,"일괄"); sv+=1
                        rs.append([f,rp,v,l,s,stt]); bar.progress((i+1)/len(bdf))
                    st.dataframe(pd.DataFrame(rs, columns=['식품','농약','검출량','기준','구분','판정']).style.applymap(lambda v: 'background-color:#ffe6e6' if '부적합' in v else '', subset=['판정']), use_container_width=True)
                    if sv: st.error(f"{sv}건 저장")
                    else: st.success("완료")
                except: st.error("오류")

# [Tab 5: 대장 (DB 연동 + 안전 삭제)]
with t5:
    c1, c2 = st.columns([4,1])
    with c1: st.markdown("##### 📈 통합 대장 (Persistent DB)")
    with c2: 
        if st.button("새로고침"): st.rerun()
    
    # DB에서 최신 데이터 로드
    hist_db = load_history_db()

    if not hist_db.empty:
        with st.container(border=True):
            dfc = hist_db.copy(); dfc['M'] = pd.to_datetime(dfc['검사일자']).dt.strftime('%Y-%m')
            c1,c2=st.columns(2)
            with c1: st.bar_chart(dfc['M'].value_counts().sort_index(), color="#DA291C", height=150)
            with c2: st.bar_chart(dfc['식품명'].value_counts().head(5), height=150)
        
        # 선택 삭제를 위한 Editor
        hist_db['선택'] = False # 선택용 컬럼 추가
        cols = ['선택', 'id'] + [c for c in hist_db.columns if c not in ['선택', 'id']]
        
        edf = st.data_editor(
            hist_db[cols], 
            use_container_width=True, 
            hide_index=True, 
            column_config={"선택":st.column_config.CheckboxColumn(width="small"), "id": st.column_config.NumberColumn(width="small", disabled=True)},
            key="he_db"
        )
        
        b1,b2,b3 = st.columns([1,1,4])
        with b1:
            if st.button("선택 삭제"):
                to_delete = edf[edf['선택']==True]['id'].tolist()
                delete_ids_from_db(to_delete)
                st.rerun()
        
        # ★ [추가됨] 안전한 전체 초기화 ★
        with b2:
            if st.button("⚠️ 전체 초기화"):
                # 플래그만 세움
                st.session_state['confirm_reset'] = True
        
        with b3:
            st.download_button("다운로드", edf.drop(columns=['선택']).to_csv(index=False).encode('utf-8-sig'), "Report.csv")

        # 초기화 확인 창 (조건부 렌더링)
        if st.session_state.get('confirm_reset'):
            st.error("⚠️ 경고: 모든 데이터가 영구적으로 삭제됩니다.")
            col_y, col_n = st.columns(2)
            with col_y:
                if st.button("네, 전부 삭제합니다", type="primary"):
                    clear_all_db()
                    st.session_state['confirm_reset'] = False
                    st.rerun()
            with col_n:
                if st.button("취소"):
                    st.session_state['confirm_reset'] = False
                    st.rerun()

    else: st.info("데이터 없음")
