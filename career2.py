import streamlit as st
import pandas as pd
import os
import pdfplumber
import re
from datetime import datetime
from io import BytesIO

# 공종 및 공사종류 옵션을 미리 정의 (parse_pdf 기본 인자로 사용됨)
job_options = ["건축", "토목", "전기", "기계", "설비", "조경", "안전", "정보통신"]
project_type_options = ["공동주택", "공용청사", "공장", "교육연구시설", "문화및집회시설", "산업시설", "업무시설", "운수시설", "기타"]

# 페이지 설정
st.set_page_config(layout="wide", page_title="HAEAHN PCM Career Management System")

# 사이드바/메인 배경색 커스터마이징
st.markdown(
    """
    <style>
    /* 사이드바 배경색 */
    section[data-testid="stSidebar"], div[data-testid="stSidebar"] {
        background-color: #f7f4f3 !important;
    }

    /* 메인 결과 영역 배경색 */
    div[data-testid="stAppViewContainer"],
    div[data-testid="stMain"],
    div[data-testid="stMainContent"],
    main .block-container {
        background-color: #d9dde6 !important;
    }

    /* 내부 카드/컨테이너가 배경색을 덮지 않도록 투명 처리 */
    .stApp, .block-container, .css-18e3th9 {
        background-color: transparent !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# 1. 데이터 로드 함수
def load_data(folder_path):
    file_path = os.path.join(folder_path, "기술인_경력데이터베이스.xlsx")
    if os.path.exists(file_path):
        return pd.read_excel(file_path)
    else:
        return None

# 사이드바: 검색 조건 및 설정
with st.sidebar:
    st.header("⚙️ 시스템 설정")
    folder_path = st.text_input("경력증명서 폴더 경로", value=r"C:\Career certificate")

    # --- 버튼들을 폴더 경로 바로 다음으로 이동함 ---
    st.divider()
    if st.button("엑셀 변환 (.pdf → 엑셀)"):
        if not os.path.isdir(folder_path):
            st.error("유효한 폴더 경로를 입력하세요.")
        else:
            with st.spinner("폴더 내 PDF를 분석하여 엑셀로 저장 중..."):
                def parse_pdf(fp, job_kw=job_options, proj_kw=project_type_options):
                    rec = {
                        "이름": "",
                        "출생연도": "",
                        "나이": None,
                        "기술자등급": "",
                        "보유 자격증": "",
                        "공종": "",
                        "공사종류": "",
                        "대표 경력": "",
                        "파일명": os.path.basename(fp)
                    }
                    try:
                        with pdfplumber.open(fp) as pdf:
                            text_head = ""
                            for p in pdf.pages[:4]:
                                text_head += (p.extract_text() or "") + "\n"

                            # 이름 추출: '성명' 또는 '이름' 라벨 우선, 없으면 본문에서 2~4글자 한글 단어 탐색
                            name = None
                            name_match = re.search(r"(?:성명|성\s?명|이름)\s*[:\s]\s*([가-힣]{2,4})", text_head)
                            if not name_match:
                                name_match = re.search(r"^([가-힣]{2,4})\s*(?:님|/|\\(|$)", text_head, flags=re.M)
                            if name_match:
                                name = name_match.group(1).strip()
                            
                            # 생년월일: 첫페이지의 00.00.00 형식의 앞 2자리로 계산 (1900 + 앞2자리)
                            m = re.search(r"(?:생년월일|출생연도)\s*[:\s]*([0-9]{2})[.\-][0-9]{2}[.\-][0-9]{2}", text_head)
                            if m:
                                y2 = int(m.group(1))
                                birth_year = 1900 + y2
                                rec["출생연도"] = str(birth_year)
                                rec["나이"] = datetime.now().year - birth_year

                            # 기존 등급/자격증/공종/공사종류/대표경력 추출 로직 계속...
                            gm = re.search(r"(특급|고급|중급|초급)(?:\s*기술자)?", text_head)
                            if gm:
                                rec["기술자등급"] = gm.group(1)

                            licenses = re.findall(r"([가-힣]+(?:기사|산업기사|기술사|건축사))", text_head)
                            licenses = [L for L in licenses if all(x not in L for x in ["종합","사무소","씨엠"])]
                            rec["보유 자격증"] = ", ".join(dict.fromkeys(licenses))

                            for j in job_kw:
                                if j in text_head:
                                    rec["공종"] = j
                                    break
                            for pt in proj_kw:
                                if pt in text_head:
                                    rec["공사종류"] = pt
                                    break

                            found_proj = ""
                            for page in pdf.pages:
                                tables = page.extract_tables()
                                for table in tables:
                                    header_str = str(table[:3])
                                    if "사업명" in header_str or "공사명" in header_str:
                                        for row in table:
                                            if row and any(cell for cell in row):
                                                cell0 = row[0] or ""
                                                if isinstance(cell0, str) and len(cell0.strip())>2 and "사업명" not in cell0:
                                                    found_proj = cell0.strip()
                                                    break
                                        if found_proj:
                                            break
                                if found_proj:
                                    break

                                txt = page.extract_text() or ""
                                for line in txt.splitlines():
                                    if "공사" in line and len(line) > 6:
                                        found_proj = line.strip()
                                        break
                                if found_proj:
                                    break

                            rec["대표 경력"] = found_proj
                    except Exception:
                        pass
                    # 이름이 추출되었으면 사용, 없으면 파일명(확장자 제거) 사용
                    if name:
                        rec["이름"] = name
                    else:
                        rec["이름"] = os.path.splitext(os.path.basename(fp))[0]
                    return rec

                def convert_pdfs_to_excel(folder):
                    pdfs = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".pdf")]
                    records = []
                    for p in pdfs:
                        records.append(parse_pdf(p))
                    df_out = pd.DataFrame(records)
                    out_path = os.path.join(folder, "기술인_경력데이터베이스.xlsx")
                    df_out.to_excel(out_path, index=False)
                    return out_path, df_out

                try:
                    out_path, out_df = convert_pdfs_to_excel(folder_path)
                    st.success(f"엑셀 변환 완료: {out_path} ({len(out_df)}건)")
                    st.session_state["db_path"] = out_path
                    st.session_state["db_df"] = out_df
                except Exception as ex:
                    st.error(f"변환 중 오류: {ex}")

    db_path = st.session_state.get("db_path", os.path.join(folder_path, "기술인_경력데이터베이스.xlsx"))
    if os.path.exists(db_path):
        with open(db_path, "rb") as f:
            file_bytes = f.read()
        st.download_button(
            label="엑셀 다운로드 (.xlsx)",
            data=file_bytes,
            file_name="기술인_경력데이터베이스.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    st.divider()
    st.header("🔍 필수 검색 조건")
    # 공종: 드롭다운 대신 체크박스 형태로 표시하여 복수 선택 가능하도록 변경
    job_options = ["건축", "토목", "전기", "기계", "설비", "조경", "안전", "정보통신"]
    st.write("공종 (복수 선택 가능)")
    cols = st.columns(4)
    req_job = []
    for i, job in enumerate(job_options):
        if cols[i % 4].checkbox(job, key=f"req_job_{job}"):
            req_job.append(job)
    
    # 새로 추가: 공사종류 (복수 선택 가능)
    project_type_options = ["공동주택", "공용청사", "공장", "교육연구시설", "문화및집회시설", "산업시설", "업무시설", "운수시설", "기타"]
    req_project_types = st.multiselect("공사종류 (복수 선택 가능)", project_type_options, default=[])
    
    req_grade = st.selectbox("기술자 등급", ["전체", "특급", "고급", "중급", "초급"])
    req_age = st.slider("최대 나이", 20, 100, 50)
    
    st.header("💡 선택 검색 조건")
    opt_name = st.text_input("이름")
    opt_year = st.text_input("출생연도")
    opt_career = st.text_input("대표 경력 키워드")
    opt_client = st.text_input("발주처 (추가 정보 필요 시)")
    req_cert = st.text_input("보유 자격증 (예:건축사)")

# 메인 화면
st.title("HAEAHN PCM Career Management System")

df = load_data(folder_path)

if df is not None:
    # 매칭 비율 계산 로직 (필수조건 기반 % + 선택조건은 동점자 정렬용)
    def compute_match(row):
        matches = 0
        total_required = 0

        # 공종 (필수로 설정된 경우)
        if req_job:
            total_required += 1
            if any(j in str(row.get('공종', '')) for j in req_job):
                matches += 1

        # 공사종류 (필수로 설정된 경우)
        if req_project_types:
            total_required += 1
            if any(pt in str(row.get('공사종류', '')) for pt in req_project_types):
                matches += 1

        # 등급 (전체가 아니면 필수)
        if req_grade != "전체":
            total_required += 1
            if str(row.get('기술자등급', '')) == req_grade:
                matches += 1

        # 나이(항상 필수로 간주)
        total_required += 1
        if row.get('나이') is not None and row.get('나이') <= req_age:
            matches += 1

        percent = int(matches * 100 / total_required) if total_required > 0 else 0

        # 선택조건(옵션) 매칭은 동점자 정렬용 가감치로 사용
        opt_matches = 0
        if opt_name and opt_name in str(row.get('이름', '')): opt_matches += 1
        if opt_year and str(opt_year) in str(row.get('출생연도', '')): opt_matches += 1
        if opt_career and opt_career in str(row.get('대표 경력', '')): opt_matches += 1

        return percent, opt_matches

    # 백엔드 계산 및 정렬
    df[['조건 매칭(%)', '옵션매치']] = df.apply(lambda r: pd.Series(compute_match(r)), axis=1)
    df = df.sort_values(by=['조건 매칭(%)', '옵션매치'], ascending=False)

    # 조건 매칭 0% 항목은 결과에서 제외
    df = df[df['조건 매칭(%)'] > 0].reset_index(drop=True)

    # 결과 출력
    if df.empty:
        st.info("조건에 맞는 인원이 없습니다.")
    else:
        st.subheader(f"검색 결과 (총 {len(df)}명)")
        
        for index, row in df.iterrows():
            with st.container():
                col1, col2, col3 = st.columns([1, 4, 1])
                
                with col1:
                    st.metric("조건 매칭", f"{row['조건 매칭(%)']}%")
                    
                with col2:
                    st.markdown(f"### **{row.get('이름','')}** ({row.get('기술자등급','')})")
                    st.write(f"**나이:** {row.get('나이','')}세 | **공종:** {row.get('공종','')} | **공사종류:** {row.get('공사종류','')}")
                    st.write(f"**자격증:** {row.get('보유 자격증','')}")
                    st.write(f"**대표경력:** {row.get('대표 경력','')}")
                
                with col3:
                    # 파일명 컬럼 우선, 없으면 이름으로 추정
                    pdf_filename = row.get('파일명') or f"{row.get('이름','')}.pdf"
                    pdf_path = os.path.join(folder_path, pdf_filename)
                    
                    if os.path.exists(pdf_path):
                        try:
                            with open(pdf_path, "rb") as f:
                                pdf_bytes = f.read()
                            st.write(f"📄 {os.path.basename(pdf_filename)}")
                            st.download_button(
                                label="다운로드",
                                data=pdf_bytes,
                                file_name=os.path.basename(pdf_filename),
                                mime="application/pdf",
                                key=f"download_{index}_{os.path.basename(pdf_filename)}"
                            )
                        except Exception:
                            st.error("PDF 파일을 읽을 수 없습니다.")
                    else:
                        st.warning("파일 없음")
                st.divider()

else:
    st.warning(f"'{folder_path}' 폴더에서 엑셀 파일을 찾을 수 없습니다. 먼저 추출 프로그램을 실행해 주세요.")
