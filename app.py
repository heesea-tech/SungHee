import streamlit as st
import pandas as pd
import math
import plotly.graph_objects as go

# 페이지 기본 설정 (제목, 레이아웃)
st.set_page_config(page_title="DC Feasibility Architect", layout="wide")

# ==========================================
# 1. 계산 로직 클래스 (기존 로직 활용)
# ==========================================
class DataCenterCalculator:
    def __init__(self, site_area, bcr, far, kw_per_rack, pue, white_space_ratio, height_limit=None):
        self.site_area = site_area
        self.bcr = bcr
        self.far = far
        self.kw_per_rack = kw_per_rack
        self.pue = pue
        self.white_space_ratio = white_space_ratio / 100.0 # 퍼센트 변환
        self.height_limit = height_limit

    def calculate(self):
        # 건축 규모
        floor_height = 6.0  # 층고 가정 (m)
        max_build_area = self.site_area * (self.bcr / 100)
        total_floor_area = self.site_area * (self.far / 100)
        est_floors_by_area = math.floor(total_floor_area / max_build_area) if max_build_area > 0 else 0
        
        # 높이제한에 따른 층수 계산
        if self.height_limit is not None:
            max_floors_by_height = math.floor(self.height_limit / floor_height)
            est_floors = min(est_floors_by_area, max_floors_by_height)
        else:
            est_floors = est_floors_by_area
        
        total_height = est_floors * floor_height

        # IT 용량
        white_space_area = total_floor_area * self.white_space_ratio
        area_per_rack = 3.5 # m2/rack
        total_racks = math.floor(white_space_area / area_per_rack)

        # 설비 부하
        it_load_kw = total_racks * self.kw_per_rack
        total_power_kw = it_load_kw * self.pue
        total_power_mva = total_power_kw / 0.9 / 1000 # 역률 0.9, MVA 변환
        cooling_load_rt = (it_load_kw * 1.1) / 3.517

        return {
            "max_build_area": max_build_area,
            "total_floor_area": total_floor_area,
            "est_floors": est_floors,
            "total_height": total_height,
            "floor_height": floor_height,
            "white_space_area": white_space_area,
            "support_area": total_floor_area - white_space_area,
            "total_racks": total_racks,
            "it_load_mw": it_load_kw / 1000,
            "total_power_mva": total_power_mva,
            "cooling_load_rt": cooling_load_rt
        }

# ==========================================
# 2. 사이드바 (사용자 입력)
# ==========================================
st.sidebar.header("🏗️ 프로젝트 조건 입력")

st.sidebar.subheader("1. 건축 정보")
site_area = st.sidebar.number_input("대지면적 (m²)", value=3700.0, step=100.0)
bcr_limit = st.sidebar.slider("건폐율 (%)", 0, 100, 60)
far_limit = st.sidebar.slider("용적률 (%)", 0, 1000, 350)
height_limit = st.sidebar.number_input("높이제한 (m)", value=50.0, step=1.0)

st.sidebar.subheader("2. 설비 정보")
kw_per_rack = st.sidebar.number_input("랙당 전력 (kW)", value=6.0, step=0.5)
target_pue = st.sidebar.number_input("목표 PUE", value=1.4, step=0.05)
white_space_ratio = st.sidebar.slider("전산실(White Space) 면적 비율 (%)", 20, 60, 45)

# ==========================================
# 3. 메인 화면 구성
# ==========================================
st.title("🏢 SungHee's Datacenter Solution")
st.markdown("건축 법규와 IT/MEP 부하를 연동한 실시간 타당성 검토 도구입니다.")

# 계산 실행
calc = DataCenterCalculator(site_area, bcr_limit, far_limit, kw_per_rack, target_pue, white_space_ratio, height_limit)
res = calc.calculate()

st.divider()

# [섹션 1] 핵심 KPI (Dashboard)
st.subheader("📊 핵심 검토 결과 (Key Metrics)")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label="총 수용 랙(Rack)", value=f"{res['total_racks']:,} 개", delta="IT Capacity")
with col2:
    st.metric(label="필요 수전 용량", value=f"{res['total_power_mva']:.2f} MVA", delta="Electrical")
with col3:
    st.metric(label="예상 냉각 부하", value=f"{res['cooling_load_rt']:,.0f} RT", delta="Mechanical")
with col4:
    st.metric(label="지상 연면적", value=f"{res['total_floor_area']:,.0f} m²", help="용적률 산정용 연면적")

st.divider()

# [섹션 2] 상세 분석 및 시각화
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("📑 상세 건축 개요")
    
    # 데이터프레임으로 깔끔하게 정리
    arch_data = {
        "항목": ["대지면적", "건축면적 (바닥)", "지상 연면적", "용적률 (%)", "예상 층수", "전체 높이", "층고", "전산실 면적", "기타 공용/설비면적"],
        "수치": [
            f"{site_area:,.2f} m²",
            f"{res['max_build_area']:,.2f} m²",
            f"{res['total_floor_area']:,.2f} m²",
            f"{(res['total_floor_area'] / site_area) * 100:.2f}%",
            f"약 {res['est_floors']} 층",
            f"{res['total_height']:.2f} m",
            f"{res['floor_height']:.2f} m",
            f"{res['white_space_area']:,.2f} m²",
            f"{res['support_area']:,.2f} m²"
        ]
    }
    df_arch = pd.DataFrame(arch_data)
    st.table(df_arch)
    
    st.info(f"💡 팁: 현재 설정된 전산실 비율({white_space_ratio}%)에 따라 설비 공간이 자동 계산됩니다.")

with col_right:
    st.subheader("📈 면적 배분 (Zoning Ratio)")
    
    # 차트 데이터 생성
    chart_data = pd.DataFrame({
        'Area Type': ['White Space (Server Room)', 'Support Area (MEP/Office/Core)'],
        'Area (m2)': [res['white_space_area'], res['support_area']]
    })
    
    # 파이 차트 또는 바 차트 표시
    st.bar_chart(chart_data, x='Area Type', y='Area (m2)')
    
    st.success(f"**MEP Check Point**\n\n"
               f"- IT Load: {res['it_load_mw']:.2f} MW\n"
               f"- 랙당 {kw_per_rack}kW 기준 고밀도 설계 여부 확인 필요\n"
               f"- 변전소 인입 가능 여부: {res['total_power_mva']:.2f} MVA")

# [섹션 3] 제안 메시지
st.warning("⚠️ 본 검토는 초기 Feasibility Study용이며, 실제 실시설계 시 구조 간섭 및 덕트 샤프트 면적에 따라 10~15% 오차가 발생할 수 있습니다.")

st.divider()

st.subheader("🏗️ 3D 건물 매스 모델")

# 3D 모델 계산
floor_height = 6.0  # 층고 가정 (m)
est_floors = res['est_floors']

if est_floors > 0:
    fig = go.Figure()
    z_base = 0
    max_build_area = res['max_build_area']
    building_side = math.sqrt(max_build_area)
    white_space_area = res['white_space_area']
    support_area = res['support_area']
    
    # 구획 비율 계산 (가정: 전산실 45%, 공용 30%, 지원시설 25%)
    public_area_ratio = 0.30  # 30% - 공용 구역 (엘리베이터, 계단, 복도)
    support_facility_ratio = 0.25  # 25% - 지원시설 (화장실, 휴게실, 관리실)
    
    for floor in range(est_floors):
        z_top = z_base + floor_height
        
        # 층별 면적 계산
        ws_area_per_floor = white_space_area / est_floors
        sup_area_per_floor = support_area / est_floors
        public_area_per_floor = sup_area_per_floor * (public_area_ratio / (public_area_ratio + support_facility_ratio))
        support_facility_per_floor = sup_area_per_floor * (support_facility_ratio / (public_area_ratio + support_facility_ratio))
        
        ws_side = math.sqrt(ws_area_per_floor)
        public_side = math.sqrt(public_area_per_floor)
        support_fac_side = math.sqrt(support_facility_per_floor)
        
        # 좌표 계산 (좌측 상단 기준)
        x_offset = -building_side / 2
        y_offset = -building_side / 2
        
        # 전산실 (White Space) - 좌측 상단
        x0_ws = x_offset
        x1_ws = x0_ws + ws_side
        y0_ws = y_offset
        y1_ws = y0_ws + ws_side
        
        # 공용 (Public Area) - 우측 상단
        x0_pub = x1_ws
        x1_pub = x0_pub + public_side
        y0_pub = y_offset
        y1_pub = y0_pub + public_side
        
        # 지원시설 (Support Facility) - 우측 하단
        x0_sup_fac = x1_ws
        x1_sup_fac = x0_sup_fac + support_fac_side
        y0_sup_fac = y1_ws
        y1_sup_fac = y0_sup_fac + support_fac_side
        
        # White Space (전산실) mesh - 빨강
        fig.add_trace(go.Mesh3d(
            x=[x0_ws, x1_ws, x1_ws, x0_ws, x0_ws, x1_ws, x1_ws, x0_ws],
            y=[y0_ws, y0_ws, y1_ws, y1_ws, y0_ws, y0_ws, y1_ws, y1_ws],
            z=[z_base, z_base, z_base, z_base, z_top, z_top, z_top, z_top],
            i=[0, 0, 0, 1, 4, 4, 4, 5, 6, 6, 1, 2],
            j=[1, 2, 3, 2, 5, 6, 7, 6, 7, 3, 5, 6],
            k=[2, 3, 1, 3, 6, 7, 5, 7, 5, 7, 6, 7],
            color='#FF6B6B',
            opacity=0.9,
            name=f'전산실 (White Space) Floor {floor+1}'
        ))
        
        # Public Area (공용) mesh - 파랑
        fig.add_trace(go.Mesh3d(
            x=[x0_pub, x1_pub, x1_pub, x0_pub, x0_pub, x1_pub, x1_pub, x0_pub],
            y=[y0_pub, y0_pub, y1_pub, y1_pub, y0_pub, y0_pub, y1_pub, y1_pub],
            z=[z_base, z_base, z_base, z_base, z_top, z_top, z_top, z_top],
            i=[0, 0, 0, 1, 4, 4, 4, 5, 6, 6, 1, 2],
            j=[1, 2, 3, 2, 5, 6, 7, 6, 7, 3, 5, 6],
            k=[2, 3, 1, 3, 6, 7, 5, 7, 5, 7, 6, 7],
            color='#4ECDC4',
            opacity=0.9,
            name=f'공용 (Public) Floor {floor+1}'
        ))
        
        # Support Facility mesh - 주황
        fig.add_trace(go.Mesh3d(
            x=[x0_sup_fac, x1_sup_fac, x1_sup_fac, x0_sup_fac, x0_sup_fac, x1_sup_fac, x1_sup_fac, x0_sup_fac],
            y=[y0_sup_fac, y0_sup_fac, y1_sup_fac, y1_sup_fac, y0_sup_fac, y0_sup_fac, y1_sup_fac, y1_sup_fac],
            z=[z_base, z_base, z_base, z_base, z_top, z_top, z_top, z_top],
            i=[0, 0, 0, 1, 4, 4, 4, 5, 6, 6, 1, 2],
            j=[1, 2, 3, 2, 5, 6, 7, 6, 7, 3, 5, 6],
            k=[2, 3, 1, 3, 6, 7, 5, 7, 5, 7, 6, 7],
            color='#FFB84D',
            opacity=0.9,
            name=f'지원시설 (Support) Floor {floor+1}'
        ))
        
        z_base = z_top
    
    fig.update_layout(scene=dict(
        xaxis_title='X (m)',
        yaxis_title='Y (m)',
        zaxis_title='Z (Height m)',
        aspectmode='data'
    ))
    
    st.plotly_chart(fig)
else:
    st.write("층수가 0이므로 3D 모델을 표시할 수 없습니다.")

st.divider()

# [섹션 4] 각 층의 평면도
st.subheader("📐 각 층별 평면도 (Floor Plan)")

floor_number = st.slider("층 선택", 1, est_floors, 1)

if est_floors > 0:
    fig_floorplan = go.Figure()
    
    max_build_area = res['max_build_area']
    building_side = math.sqrt(max_build_area)
    white_space_area = res['white_space_area']
    support_area = res['support_area']
    
    # 구획 비율 계산
    public_area_ratio = 0.30
    support_facility_ratio = 0.25
    
    # 층별 면적 계산
    ws_area_per_floor = white_space_area / est_floors
    sup_area_per_floor = support_area / est_floors
    public_area_per_floor = sup_area_per_floor * (public_area_ratio / (public_area_ratio + support_facility_ratio))
    support_facility_per_floor = sup_area_per_floor * (support_facility_ratio / (public_area_ratio + support_facility_ratio))
    
    ws_side = math.sqrt(ws_area_per_floor)
    public_side = math.sqrt(public_area_per_floor)
    support_fac_side = math.sqrt(support_facility_per_floor)
    
    # 좌표 계산
    x_offset = 0
    y_offset = 0
    
    # 전산실 (White Space) - 좌측 상단
    x0_ws = x_offset
    x1_ws = x0_ws + ws_side
    y0_ws = y_offset
    y1_ws = y0_ws + ws_side
    
    # 공용 (Public Area) - 우측 상단
    x0_pub = x1_ws
    x1_pub = x0_pub + public_side
    y0_pub = y_offset
    y1_pub = y0_pub + public_side
    
    # 지원시설 (Support Facility) - 우측 하단
    x0_sup_fac = x1_ws
    x1_sup_fac = x0_sup_fac + support_fac_side
    y0_sup_fac = y1_ws
    y1_sup_fac = y0_sup_fac + support_fac_side
    
    # 전산실 사각형 - 빨강
    fig_floorplan.add_trace(go.Scatter(
        x=[x0_ws, x1_ws, x1_ws, x0_ws, x0_ws],
        y=[y0_ws, y0_ws, y1_ws, y1_ws, y0_ws],
        fill='toself',
        fillcolor='rgba(255, 107, 107, 0.6)',
        line=dict(color='red', width=3),
        name='전산실 (White Space)',
        hovertemplate=f'전산실 (White Space)<br>면적: {ws_area_per_floor:.2f} m²<extra></extra>'
    ))
    
    # 공용 사각형 - 파랑
    fig_floorplan.add_trace(go.Scatter(
        x=[x0_pub, x1_pub, x1_pub, x0_pub, x0_pub],
        y=[y0_pub, y0_pub, y1_pub, y1_pub, y0_pub],
        fill='toself',
        fillcolor='rgba(78, 205, 196, 0.6)',
        line=dict(color='#4ECDC4', width=3),
        name='공용 (Public)',
        hovertemplate=f'공용 (Public)<br>면적: {public_area_per_floor:.2f} m²<extra></extra>'
    ))
    
    # 지원시설 사각형 - 주황
    fig_floorplan.add_trace(go.Scatter(
        x=[x0_sup_fac, x1_sup_fac, x1_sup_fac, x0_sup_fac, x0_sup_fac],
        y=[y0_sup_fac, y0_sup_fac, y1_sup_fac, y1_sup_fac, y0_sup_fac],
        fill='toself',
        fillcolor='rgba(255, 184, 77, 0.6)',
        line=dict(color='#FFB84D', width=3),
        name='지원시설 (Support)',
        hovertemplate=f'지원시설 (Support)<br>면적: {support_facility_per_floor:.2f} m²<extra></extra>'
    ))
    
    fig_floorplan.update_layout(
        title=f"F{floor_number} 평면도",
        xaxis_title='X 축 (m)',
        yaxis_title='Y 축 (m)',
        hovermode='closest',
        xaxis=dict(scaleanchor='y', scaleratio=1),
        yaxis=dict(scaleanchor='x', scaleratio=1),
        height=600,
        width=600
    )
    
    # 평면도와 정보를 나란히 표시
    col_plan_left, col_plan_right = st.columns([2, 1])
    
    with col_plan_left:
        st.plotly_chart(fig_floorplan, use_container_width=True)
    
    with col_plan_right:
        st.markdown(f"### F{floor_number} 층 면적 분석")
        
        floor_data = {
            "구획": ["전산실 (White Space)", "공용 (Public)", "지원시설 (Support)"],
            "면적 (m²)": [
                f"{ws_area_per_floor:.2f}",
                f"{public_area_per_floor:.2f}",
                f"{support_facility_per_floor:.2f}"
            ],
            "비율 (%)": [
                f"{(ws_area_per_floor/sup_area_per_floor*100):.1f}%",
                f"{(public_area_per_floor/sup_area_per_floor*100):.1f}%",
                f"{(support_facility_per_floor/sup_area_per_floor*100):.1f}%"
            ]
        }
        
        df_floor = pd.DataFrame(floor_data)
        st.table(df_floor)
        
        st.markdown("---")
        st.markdown("#### 범례")
        st.markdown("🔴 **전산실**: IT 장비 설치 공간")
        st.markdown("🔵 **공용**: 엘리베이터, 계단, 복도")
        st.markdown("🟠 **지원시설**: 화장실, 휴게실, 관리실")

