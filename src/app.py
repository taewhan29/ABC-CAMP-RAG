import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re
import os
from collections import Counter

# ──────────────────────────────────────────────
# 페이지 설정
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="YES24 IT 베스트셀러 대시보드",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# 커스텀 CSS
# ──────────────────────────────────────────────
st.markdown(
    """
    <style>
    .main .block-container { padding-top: 1.5rem; padding-bottom: 1.5rem; }

    .kpi-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 14px; padding: 1.2rem 1.4rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.06);
        transition: transform 0.2s;
    }
    .kpi-card:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(0,0,0,0.10); }
    .kpi-label { font-size: 13px; color: #636e72; font-weight: 500; margin-bottom: 4px; }
    .kpi-value { font-size: 26px; font-weight: 700; margin: 0; }
    .kpi-sub   { font-size: 11px; color: #b2bec3; margin-top: 4px; }

    .book-card {
        background: #fff; border-left: 5px solid #4A90E2;
        border-radius: 10px; padding: 1.3rem 1.5rem;
        margin: 0.8rem 0; box-shadow: 0 4px 18px rgba(0,0,0,0.06);
    }
    .book-card-title   { font-size: 20px; font-weight: 700; color: #2c3e50; }
    .book-card-sub     { font-size: 14px; color: #95a5a6; font-style: italic; margin-top: 2px; }
    .book-card-grid    { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px,1fr)); gap: 12px; font-size: 13px; margin-top: 12px; }
    .badge { display:inline-block; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; margin-right:4px; }
    .badge-blue   { background:#e3f2fd; color:#0d47a1; }
    .badge-green  { background:#e8f5e9; color:#1b5e20; }
    .badge-orange { background:#fff8e1; color:#e65100; }
    .badge-red    { background:#ffebee; color:#b71c1c; }

    .highlight { background-color: #fff176; padding: 0 3px; border-radius: 3px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────
# 데이터 로드 & 전처리
# ──────────────────────────────────────────────
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "yes24_it_bestseller.csv")


@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        st.error(f"데이터 파일을 찾을 수 없습니다: `{path}`")
        st.stop()

    df = pd.read_csv(path, on_bad_lines="skip")

    # 결측치 처리
    df["부제목"] = df["부제목"].fillna("")
    df["저자"]   = df["저자"].fillna("저자 미상")
    df["출판사"] = df["출판사"].fillna("출판사 미상")

    # 수치형 변환
    for col in ["판매가", "정가", "적립포인트", "판매지수", "리뷰수"]:
        if col in df.columns:
            df[col] = (
                pd.to_numeric(
                    df[col].astype(str).str.replace(r"[^\d.]", "", regex=True),
                    errors="coerce",
                )
                .fillna(0)
                .astype(int)
            )
    if "평점" in df.columns:
        df["평점"] = pd.to_numeric(df["평점"], errors="coerce").fillna(0.0)

    # 할인율
    df["할인율"] = df.apply(
        lambda r: round((r["정가"] - r["판매가"]) / r["정가"] * 100, 1)
        if r["정가"] > 0
        else 0.0,
        axis=1,
    )

    # 출판일 파싱
    def _parse_date(s):
        if not isinstance(s, str):
            return 2026, 1
        m = re.search(r"(\d{4})년?\s*[-/.\s]*\s*(\d{1,2})월?", s)
        if m:
            return int(m.group(1)), int(m.group(2))
        m2 = re.search(r"(\d{4})[-/.](\d{2})", s)
        if m2:
            return int(m2.group(1)), int(m2.group(2))
        return 2026, 1

    dates = df["출판일"].apply(_parse_date)
    df["출판연도"] = [d[0] for d in dates]
    df["출판월"]   = [d[1] for d in dates]
    df["출판연월"] = df.apply(lambda r: f"{r['출판연도']}-{r['출판월']:02d}", axis=1)

    return df


df_raw = load_data(DATA_PATH)
if df_raw.empty:
    st.warning("데이터가 비어 있습니다.")
    st.stop()

# ──────────────────────────────────────────────
# 사이드바 필터
# ──────────────────────────────────────────────
st.sidebar.markdown("## ⚙️ 필터")

# 판매가 범위
price_min, price_max = int(df_raw["판매가"].min()), int(df_raw["판매가"].max())
sel_price = st.sidebar.slider("판매가 범위 (원)", price_min, price_max, (price_min, price_max), step=1000)

# 최소 평점
sel_rating = st.sidebar.slider("최소 평점", 0.0, 10.0, 0.0, 0.1)

# 출판사
sel_publishers = st.sidebar.multiselect("출판사", sorted(df_raw["출판사"].unique()), default=[])

# 필터 적용
df = df_raw[
    (df_raw["판매가"] >= sel_price[0])
    & (df_raw["판매가"] <= sel_price[1])
    & (df_raw["평점"] >= sel_rating)
].copy()
if sel_publishers:
    df = df[df["출판사"].isin(sel_publishers)]

# ──────────────────────────────────────────────
# 헤더
# ──────────────────────────────────────────────
st.title("📊 YES24 IT 분야 베스트셀러 대시보드")
st.caption(f"총 **{len(df_raw):,}**권 데이터 기반 탐색적 분석 & 도서 검색  |  필터 적용: **{len(df):,}**권")

# ──────────────────────────────────────────────
# KPI 카드
# ──────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
avg_rating = df["평점"].mean() if len(df) else 0
avg_price  = int(df["판매가"].mean()) if len(df) else 0
best_idx   = df.loc[df["판매지수"].idxmax()] if len(df) else None
best_title = (best_idx["도서명"][:16] + "...") if best_idx is not None and len(best_idx["도서명"]) > 18 else (best_idx["도서명"] if best_idx is not None else "-")
best_val   = best_idx["판매지수"] if best_idx is not None else 0

for col, label, value, sub, color in [
    (k1, "총 도서 수",      f"{len(df):,} 권",  f"(전체 {len(df_raw):,}권)", "#2980b9"),
    (k2, "평균 평점",       f"⭐ {avg_rating:.2f}",  f"최고 {df['평점'].max():.1f}" if len(df) else "", "#f39c12"),
    (k3, "평균 판매가",     f"{avg_price:,}원",  f"평균 할인율 {df['할인율'].mean():.1f}%", "#27ae60"),
    (k4, "최고 판매지수",   best_title,           f"지수 {best_val:,}", "#e74c3c"),
]:
    with col:
        st.markdown(
            f'<div class="kpi-card">'
            f'<p class="kpi-label">{label}</p>'
            f'<p class="kpi-value" style="color:{color}">{value}</p>'
            f'<p class="kpi-sub">{sub}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown("---")

# ──────────────────────────────────────────────
# 탭
# ──────────────────────────────────────────────
tabs = st.tabs([
    "🔍 도서 검색",
    "📈 판매 · 평점 분석",
    "💰 가격 · 할인 분석",
    "🏢 출판사 · 저자 분석",
    "📅 출판 트렌드",
    "🔗 변수 상관관계",
])

# ══════════════════════════════════════════════
# TAB 1 — 도서 검색
# ══════════════════════════════════════════════
with tabs[0]:
    st.header("🔍 키워드 검색")
    st.caption("도서명 · 부제목 · 저자 · 출판사에서 키워드를 검색합니다.")

    query = st.text_input("검색어를 입력하세요", placeholder="예: 클로드, 파이썬, AI, 조코딩 ...")

    if query:
        q = query.lower()
        mask = (
            df["도서명"].str.lower().str.contains(q, na=False)
            | df["부제목"].str.lower().str.contains(q, na=False)
            | df["저자"].str.lower().str.contains(q, na=False)
            | df["출판사"].str.lower().str.contains(q, na=False)
        )
        results = df[mask].copy()
    else:
        results = df.copy()

    st.write(f"**{len(results)}권** 검색되었습니다.")

    if not results.empty:
        show_cols = ["순위", "도서명", "부제목", "저자", "출판사", "판매가", "평점", "판매지수"]
        st.dataframe(results[show_cols].set_index("순위"), use_container_width=True, height=400)

        # 상세 조회
        st.markdown("### 📖 도서 상세 정보")
        pick = st.selectbox("도서를 선택하세요", results["도서명"].tolist(), key="search_pick")
        if pick:
            b = results[results["도서명"] == pick].iloc[0]
            discount_color = "#e74c3c" if b["할인율"] > 0 else "#27ae60"
            st.markdown(
                f"""
                <div class="book-card">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                        <div>
                            <span class="badge badge-blue">#{int(b['순위'])}위</span>
                            <div class="book-card-title">{b['도서명']}</div>
                            <div class="book-card-sub">{b['부제목'] if b['부제목'] else '(부제 없음)'}</div>
                        </div>
                        <div style="text-align:right;">
                            <span class="badge badge-green" style="font-size:14px;">⭐ {b['평점']}</span><br>
                            <span class="badge badge-orange" style="font-size:12px;margin-top:4px;">판매지수 {int(b['판매지수']):,}</span>
                        </div>
                    </div>
                    <hr>
                    <div class="book-card-grid">
                        <div><strong>✍️ 저자:</strong> {b['저자']}</div>
                        <div><strong>🏢 출판사:</strong> {b['출판사']}</div>
                        <div><strong>📅 출판일:</strong> {b['출판일']}</div>
                        <div><strong>💵 판매가:</strong> {int(b['판매가']):,}원 <span style="color:#999;text-decoration:line-through;">{int(b['정가']):,}원</span> <span style="color:{discount_color};font-weight:600;">{b['할인율']}%↓</span></div>
                        <div><strong>🎁 적립포인트:</strong> {int(b['적립포인트']):,}P</div>
                        <div><strong>💬 리뷰:</strong> {int(b['리뷰수']):,}개</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if "상품번호" in b.index:
                st.markdown(f"[🔗 YES24 상세 페이지 바로가기](https://www.yes24.com/Product/Goods/{int(b['상품번호'])})")
    else:
        st.info("검색 결과가 없습니다. 필터 조건을 완화하거나 검색어를 변경해 보세요.")

# ══════════════════════════════════════════════
# TAB 2 — 판매 · 평점 분석
# ══════════════════════════════════════════════
with tabs[1]:
    st.header("📈 판매지수 & 평점 분석")

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("🔥 판매지수 TOP 10")
        top10 = df.nlargest(10, "판매지수")
        fig = px.bar(
            top10, x="판매지수", y="도서명", orientation="h",
            text_auto=",.0f", color="판매지수",
            color_continuous_scale="OrRd",
        )
        fig.update_layout(
            yaxis={"categoryorder": "total ascending"}, height=460,
            yaxis_ticktext=[t[:20] + "..." if len(t) > 22 else t for t in top10["도서명"]],
            yaxis_tickmode="array", yaxis_tickvals=top10["도서명"],
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("⭐ 평점 분포")
        fig2 = px.histogram(
            df, x="평점", nbins=15, color_discrete_sequence=["#f1c40f"],
            marginal="box", labels={"평점": "평점", "count": "도서 수"},
        )
        fig2.update_layout(height=460)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    st.subheader("💡 평점 vs 리뷰수 vs 판매지수")
    st.caption("버블 크기 = 판매지수 · 마우스 호버 시 상세 정보 표시")
    if len(df):
        fig3 = px.scatter(
            df, x="평점", y="리뷰수", size="판매지수", color="평점",
            color_continuous_scale="Viridis", hover_name="도서명",
            hover_data=["저자", "출판사", "판매지수", "리뷰수"],
            size_max=55,
        )
        fig3.update_layout(height=520)
        st.plotly_chart(fig3, use_container_width=True)

# ══════════════════════════════════════════════
# TAB 3 — 가격 · 할인 분석
# ══════════════════════════════════════════════
with tabs[2]:
    st.header("💰 가격 & 할인 분석")

    c3, c4 = st.columns(2)

    with c3:
        st.subheader("💵 가격대 분포")
        fig4 = px.histogram(
            df, x="판매가", nbins=25, color_discrete_sequence=["#2ecc71"],
            marginal="violin", labels={"판매가": "판매가 (원)"},
        )
        fig4.update_layout(height=450)
        st.plotly_chart(fig4, use_container_width=True)

    with c4:
        st.subheader("🏷️ 할인율 분포")
        fig5 = px.histogram(
            df, x="할인율", nbins=12, color_discrete_sequence=["#e74c3c"],
            marginal="box", labels={"할인율": "할인율 (%)"},
        )
        fig5.update_layout(height=450)
        st.plotly_chart(fig5, use_container_width=True)

    st.markdown("---")
    st.subheader("🏷️ 할인율 TOP 10 실속 도서")
    top_disc = df.nlargest(10, "할인율")
    if len(top_disc):
        fig6 = px.bar(
            top_disc, x="할인율", y="도서명", orientation="h",
            text_auto=True, color="할인율", color_continuous_scale="Reds",
        )
        fig6.update_layout(
            yaxis={"categoryorder": "total ascending"}, height=440,
            yaxis_ticktext=[t[:20] + "..." if len(t) > 22 else t for t in top_disc["도서명"]],
            yaxis_tickmode="array", yaxis_tickvals=top_disc["도서명"],
            showlegend=False,
        )
        st.plotly_chart(fig6, use_container_width=True)

# ══════════════════════════════════════════════
# TAB 4 — 출판사 · 저자 분석
# ══════════════════════════════════════════════
with tabs[3]:
    st.header("🏢 출판사 & 저자 분석")

    c5, c6 = st.columns(2)

    with c5:
        st.subheader("출판사별 베스트셀러 수 TOP 10")
        pub_cnt = df["출판사"].value_counts().head(10).reset_index()
        pub_cnt.columns = ["출판사", "도서 수"]
        fig7 = px.bar(
            pub_cnt, x="도서 수", y="출판사", orientation="h",
            text_auto=True, color="도서 수", color_continuous_scale="Purples",
        )
        fig7.update_layout(yaxis={"categoryorder": "total ascending"}, height=450, showlegend=False)
        st.plotly_chart(fig7, use_container_width=True)

    with c6:
        st.subheader("저자별 등재 횟수 TOP 10")
        auth_list = []
        for a in df["저자"].dropna():
            parts = re.split(r"[,·\s&/]+", str(a))
            auth_list.extend([x.strip() for x in parts if x.strip() and x.strip() not in ("저", "공저", "엮음", "편저", "글")])
        auth_df = pd.Series(auth_list).value_counts().head(10).reset_index()
        auth_df.columns = ["저자", "횟수"]
        fig8 = px.bar(
            auth_df, x="횟수", y="저자", orientation="h",
            text_auto=True, color="횟수", color_continuous_scale="Tealgrn",
        )
        fig8.update_layout(yaxis={"categoryorder": "total ascending"}, height=450, showlegend=False)
        st.plotly_chart(fig8, use_container_width=True)

    st.markdown("---")
    st.subheader("출판사별 시장 점유 비교 (상위 5개사)")
    top5_pubs = df_raw["출판사"].value_counts().head(5).index.tolist()
    df_top5 = df[df["출판사"].isin(top5_pubs)]
    if len(df_top5):
        grp = df_top5.groupby("출판사").agg(
            평균평점=("평점", "mean"), 평균판매지수=("판매지수", "mean"), 도서수=("도서명", "count")
        ).reset_index()
        cc1, cc2 = st.columns(2)
        with cc1:
            fig9 = px.bar(grp, x="출판사", y="평균평점", color="출판사", text=grp["평균평점"].round(2))
            fig9.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig9, use_container_width=True)
        with cc2:
            fig10 = px.bar(grp, x="출판사", y="평균판매지수", color="출판사", text=grp["평균판매지수"].round(0))
            fig10.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig10, use_container_width=True)
    else:
        st.info("비교 대상 데이터가 없습니다.")

# ══════════════════════════════════════════════
# TAB 5 — 출판 트렌드
# ══════════════════════════════════════════════
with tabs[4]:
    st.header("📅 출판 트렌드 분석")

    c7, c8 = st.columns(2)

    with c7:
        st.subheader("연도별 추이")
        yearly = df.groupby("출판연도").size().reset_index(name="도서 수")
        fig11 = px.line(yearly, x="출판연도", y="도서 수", markers=True, color_discrete_sequence=["#8e44ad"])
        fig11.update_layout(height=400)
        st.plotly_chart(fig11, use_container_width=True)

    with c8:
        st.subheader("월별 출판 분포")
        monthly = df.groupby("출판월").size().reset_index(name="도서 수")
        fig12 = px.bar(monthly, x="출판월", y="도서 수", color="도서 수", color_continuous_scale="Blues")
        fig12.update_layout(height=400, xaxis=dict(tickmode="linear", tick0=1, dtick=1))
        st.plotly_chart(fig12, use_container_width=True)

    st.markdown("---")

    # 연-월 히트맵
    st.subheader("📅 연도 × 월 베스트셀러 출판 히트맵")
    heat = df.groupby(["출판연도", "출판월"]).size().reset_index(name="도서 수")
    if len(heat):
        heat_pivot = heat.pivot(index="출판연도", columns="출판월", values="도서 수").fillna(0)
        fig_heat = px.imshow(
            heat_pivot, labels=dict(x="월", y="연도", color="도서 수"),
            color_continuous_scale="YlOrRd", aspect="auto",
        )
        fig_heat.update_layout(height=max(300, len(heat_pivot) * 50))
        st.plotly_chart(fig_heat, use_container_width=True)

    st.markdown("---")
    st.subheader("⏳ 최근 출판 도서 TOP 10")
    latest = df.sort_values(["출판연도", "출판월"], ascending=False).head(10)
    if len(latest):
        st.table(latest[["순위", "도서명", "저자", "출판사", "출판일", "판매가", "평점"]].set_index("순위"))

    # ── 워드 클라우드 (대체: 바 차트) ──
    st.markdown("---")
    st.subheader("☁️ 도서명 키워드 빈도 (상위 30)")
    all_words = []
    for t in df["도서명"].dropna():
        # 한글/영문 토큰 추출 (2글자 이상)
        tokens = re.findall(r"[a-zA-Z]{2,}|[가-힣]{2,}", str(t))
        all_words.extend([w.lower() for w in tokens])
    # 불용어
    stopwords = {"에서", "까지", "부터", "위한", "그리고", "하는", "하는", "한", "의", "에", "를", "이", "가", "은", "는", "으로", "로", "와", "과", "도", "의한", "만", "만의", "더", "바로", "나는", "완전", "초보"}
    filtered_words = [w for w in all_words if w not in stopwords and len(w) >= 2]
    word_freq = Counter(filtered_words).most_common(30)
    if word_freq:
        wf_df = pd.DataFrame(word_freq, columns=["단어", "빈도"])
        fig_wc = px.bar(
            wf_df, x="빈도", y="단어", orientation="h",
            text_auto=True, color="빈도", color_continuous_scale="Turbo",
        )
        fig_wc.update_layout(yaxis={"categoryorder": "total ascending"}, height=550, showlegend=False)
        st.plotly_chart(fig_wc, use_container_width=True)

# ══════════════════════════════════════════════
# TAB 6 — 변수 상관관계
# ══════════════════════════════════════════════
with tabs[5]:
    st.header("🔗 수치 변수 상관관계 분석")

    num_cols = ["판매가", "정가", "적립포인트", "판매지수", "평점", "리뷰수", "할인율"]
    existing = [c for c in num_cols if c in df.columns]
    corr = df[existing].corr()

    fig_corr = px.imshow(
        corr, text_auto=".2f", color_continuous_scale="RdBu_r",
        zmin=-1, zmax=1, aspect="auto",
        labels=dict(color="상관계수"),
    )
    fig_corr.update_layout(height=550)
    st.plotly_chart(fig_corr, use_container_width=True)

    st.caption("상관계수: +1 (양의 상관) ~ 0 (상관 없음) ~ -1 (음의 상관)")

# ──────────────────────────────────────────────
# 푸터
# ──────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<p style='text-align:center;color:#b2bec3;font-size:12px;'>"
    "YES24 IT Bestseller EDA Dashboard · Built with Streamlit &amp; Plotly"
    "</p>",
    unsafe_allow_html=True,
)
