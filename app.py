import streamlit as st
import pandas as pd
import os
import io

# --- 1. 기본 설정 ---
st.set_page_config(page_title="잔류농약 판정기", page_icon="🥦", layout="wide") # 넓은 화면 사용
st.title("🥦 잔류농약 적합 판정 시스템 (Pro)")

# --- 2. 데이터 로딩 ---
@st.cache_data
def load_data():
    csv_file = 'data.csv'
    if not os.path.exists(csv_file):
        return None
    try:
        df = pd.read_csv(csv_file)
        # 공백 제거 및 문자열 변환
        df['food_type'] = df['food_type'].astype(str).str.strip()
        df['pesticide_name'] = df['pesticide_name'].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"데이터 파일 읽기 실패: {e}")
        return None

with st.spinner('데이터를 불러오는 중입니다... ⏳'):
    df = load_data()

if df is None:
    st.error("🚨 'data.csv' 파일을 찾을 수 없습니다! GitHub에 파일을 올려주세요.")
    st.stop()

# 목록 준비
food_list = sorted(df['food_type'].unique().tolist())
pesticide_list = sorted(df['pesticide_name'].unique().tolist())

# --- 3. 탭(Tab) 메뉴 만들기 ---
tab1, tab2 = st.tabs(["🔍 개별 검색 (하나씩)", "📑 일괄 검색 (여러 개 복붙)"])

# ==========================================
# [탭 1] 기존 기능: 하나씩 검색
# ==========================================
with tab1:
    st.header("한 건씩 정확하게 확인하기")
    c1, c2, c3 = st.columns([1, 1, 1]) # 3단 배치

    with c1:
        input_food = st.selectbox("식품 선택", food_list, index=None, placeholder="식품명", key="single_food")
    with c2:
        input_pesticide = st.selectbox("농약 선택", pesticide_list, index=None, placeholder="농약명", key="single_pest")
    with c3:
        input_amount = st.number_input("검출량 (mg/kg)", min_value=0.0, format="%.4f", step=0.001, key="single_amount")

    if st.button("판정하기", type="primary", key="btn_single"):
        if not input_food or not input_pesticide:
            st.warning("식품과 농약을 모두 선택해주세요.")
        else:
            match = df[(df['food_type'] == input_food) & (df['pesticide_name'] == input_pesticide)]
            
            if match.empty:
                st.error("❌ 기준 정보 없음")
                st.write(f"'{input_food}' - '{input_pesticide}' 조합은 기준서에 없습니다.")
            else:
                limit = float(match.iloc[0]['limit_mg_kg'])
                
                # 결과 카드 디자인
                st.divider()
                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("식품 / 농약", f"{input_food}")
                rc2.metric("허용 기준", f"{limit} mg/kg")
                
                # 초과 여부 색상 표시
                diff = input_amount - limit
                if diff > 0:
                    rc3.metric("내 검출량", f"{input_amount} mg/kg", f"+{diff:.4f} 초과 (부적합)", delta_color="inverse")
                    st.error(f"🚨 **[부적합]** 기준치보다 **{diff:.4f} mg/kg** 초과되었습니다!")
                else:
                    rc3.metric("내 검출량", f"{input_amount} mg/kg", "안전 (적합)")
                    st.success("✅ **[적합]** 안전한 수준입니다.")

# ==========================================
# [탭 2] 신규 기능: 여러 개 한꺼번에 (복붙)
# ==========================================
with tab2:
    st.header("엑셀에서 복사해서 붙여넣으세요")
    
    st.info("""
    **💡 사용 방법**
    1. 엑셀에서 **[식품명, 농약명, 검출량]** 순서로 셀을 드래그해서 복사(Ctrl+C)하세요.
    2. 아래 칸에 붙여넣기(Ctrl+V) 하세요.
    3. **Ctrl + Enter**를 누르면 자동으로 표가 만들어집니다.
    """)

    # 예시 데이터 보여주기
    example_text = "가지\t가스가마이신\t0.5\n감자\t다이아지논\t0.01\n고구마\t디디티\t0.2"
    
    # 텍스트 입력창
    paste_data = st.text_area("여기에 붙여넣기 (식품 농약 검출량)", height=200, placeholder=example_text)

    if st.button("일괄 판정 시작 🚀", type="primary", key="btn_batch"):
        if not paste_data:
            st.warning("데이터를 붙여넣어 주세요!")
        else:
            # 1. 붙여넣은 텍스트를 데이터프레임으로 변환
            try:
                # 탭(\t)이나 콤마(,)나 공백으로 구분된 데이터를 읽음
                batch_df = pd.read_csv(io.StringIO(paste_data), sep=None, names=['식품명', '농약명', '검출량'], engine='python')
                
                results = []
                
                # 2. 한 줄씩 검사 시작
                progress_bar = st.progress(0)
                total_rows = len(batch_df)

                for i, row in batch_df.iterrows():
                    f_name = str(row['식품명']).strip()
                    p_name = str(row['농약명']).strip()
                    try:
                        amount = float(row['검출량'])
                    except:
                        amount = 0.0 # 숫자가 아니면 0 처리

                    # 기준 찾기
                    match = df[(df['food_type'] == f_name) & (df['pesticide_name'] == p_name)]
                    
                    if match.empty:
                        status = "❓ 기준 없음"
                        limit_val = 0.0
                        diff = 0.0
                        note = "데이터베이스에 없음"
                    else:
                        limit_val = float(match.iloc[0]['limit_mg_kg'])
                        if amount > limit_val:
                            status = "🚨 부적합"
                            note = f"{amount - limit_val:.4f} 초과"
                        else:
                            status = "✅ 적합"
                            note = "안전"
                    
                    results.append({
                        "식품명": f_name,
                        "농약명": p_name,
                        "검출량": amount,
                        "허용기준": limit_val,
                        "판정결과": status,
                        "비고": note
                    })
                    progress_bar.progress((i + 1) / total_rows)

                # 3. 결과 보여주기
                res_df = pd.DataFrame(results)
                
                # 부적합 건수 세기
                fail_count = len(res_df[res_df['판정결과'].str.contains("부적합")])
                
                st.write("---")
                if fail_count > 0:
                    st.error(f"총 {len(res_df)}건 중 **{fail_count}건이 부적합**입니다! 빨간색을 확인하세요.")
                else:
                    st.success(f"축하합니다! 총 {len(res_df)}건 모두 **적합(안전)**합니다.")
                    st.balloons()

                # 4. 예쁜 표로 보여주기 (부적합은 빨간색 강조)
                def highlight_fail(row):
                    if "부적합" in row['판정결과']:
                        return ['background-color: #ffcccc'] * len(row) # 연한 빨강 배경
                    elif "적합" in row['판정결과']:
                        return ['background-color: #e6fffa'] * len(row) # 연한 초록 배경
                    else:
                        return [''] * len(row)

                st.dataframe(
                    res_df.style.apply(highlight_fail, axis=1), 
                    use_container_width=True,
                    hide_index=True
                )

            except Exception as e:
                st.error("데이터 형식이 이상해요! '식품명 농약명 검출량' 순서가 맞는지 확인해주세요.")
                st.write(f"에러 내용: {e}")
