"""실습 04: 각 질문을 독립된 Figure에 그리고 수치와 함께 저장합니다."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # GUI 없이 PNG를 생성합니다. 저장 이미지는 파일 탐색기에서 엽니다.
import matplotlib.pyplot as plt
from eda.analyze import daily_summary


def _save(fig, chart_dir, filename):
    chart_dir = Path(chart_dir)
    chart_dir.mkdir(parents=True, exist_ok=True)
    try:
        fig.tight_layout()
        fig.savefig(chart_dir / filename, dpi=160)
    finally:
        plt.close(fig)


def plot_bar(summary, chart_dir):
    """역할별 평균/유효 측정 수를 표시하고 latency_by_agent.png를 만듭니다."""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    # 해설 P_BAR: summary로 막대를 그리고 0 기준선·단위·역할별 측정/전체 수를 표시하세요. 측정 0건은 0ms가 아니라 No measurement로 안내하세요.
    # 해설 P_BAR: 하드코딩된 3건 대신 현재 표에서 표본 수를 읽습니다.
    bars = ax.bar(summary["agent"], summary["mean_ms"])
    finite = summary["mean_ms"].dropna()
    top = max(650.0, float(finite.max()) * 1.22) if not finite.empty else 650.0
    ax.set_ylim(0, top)
    labels = [f"{v:.2f} ms\nn={n}/{r}" if np.isfinite(v) else f"No measurement\nn=0/{r}"
              for v, n, r in zip(summary["mean_ms"], summary["measured"], summary["runs"])]
    for index, (bar, label) in enumerate(zip(bars, labels)):
        value = summary.iloc[index]["mean_ms"]
        y = float(value) if np.isfinite(value) else 0.0
        ax.annotate(label, (bar.get_x() + bar.get_width()/2, y), xytext=(0, 5),
                    textcoords="offset points", ha="center", va="bottom", fontsize=9)
    ax.set(title="Mean latency by agent (valid / all runs)", xlabel="Agent", ylabel="Latency (ms)")
    _save(fig, chart_dir, "latency_by_agent.png")
    return {"agents": summary["agent"].tolist(), "measured": summary["measured"].tolist(),
            "runs": summary["runs"].tolist(), "means": summary["mean_ms"].tolist()}


def plot_hist(clean, chart_dir):
    """유효 latency 분포와 구간 개수를 반환합니다. 900ms도 보존합니다."""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    # 해설 P_HIST: latency 결측만 제외한 values를 만들고 0~1000의 200 간격 bins를 사용하세요. 범위가 커지면 확장. counts, edges를 받고 제목에 n을 표시하세요.
    values = clean["latency_ms"].dropna()
    # 수업 데이터는 PPT와 같은 0~1000 경계. 더 큰 입력은 구간을 확장합니다.
    maximum = float(values.max()) if len(values) else 0.0
    upper = max(1000, int(np.ceil(maximum / 200)) * 200)
    edges = np.arange(0, upper + 200, 200)
    counts, edges, _ = ax.hist(values, bins=edges)
    ax.set(title=f"Latency distribution (n={len(values)}, missing={len(clean)-len(values)})",
           xlabel="Latency (ms)", ylabel="Runs")
    ax.set_xticks(edges)
    if values.empty:
        ax.text(0.5, 0.5, "No valid measurement", transform=ax.transAxes, ha="center")
    _save(fig, chart_dir, "latency_hist.png")
    return {"n": len(values), "missing": len(clean)-len(values),
            "counts": counts.astype(int).tolist(), "edges": edges.tolist()}


def plot_scatter(clean, chart_dir):
    """두 수치가 모두 있는 행만 선택합니다. 인과관계를 주장하지 않습니다."""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    # 해설 P_SCATTER: tokens/latency_ms 두 열에서 dropna하여 pair를 만들고 scatter를 그리세요. 축 단위와 실제 n을 표시하세요.
    pair = clean[["tokens", "latency_ms"]].dropna()
    ax.scatter(pair["tokens"], pair["latency_ms"])
    ax.set(title=f"Tokens vs latency (n={len(pair)})", xlabel="Tokens", ylabel="Latency (ms)")
    if pair.empty:
        ax.text(0.5, 0.5, "No paired measurement", transform=ax.transAxes, ha="center")
    _save(fig, chart_dir, "tokens_latency.png")
    return {"n": len(pair), "excluded": len(clean)-len(pair), "selection": "두 측정값이 모두 유효한 행"}


def plot_daily(clean, chart_dir):
    """날짜 미상은 별도로 집계하고, 없는 날짜를 보간하지 않습니다."""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    # 해설 P_DAILY: daily_summary에서 NaT 그룹을 별도 집계. known을 날짜 정렬하고 없는 날짜는 NaN으로 reindex한 선그래프를 그리세요. unknown 변수도 설정하세요.
    daily = daily_summary(clean)
    unknown = int(daily.loc[daily.index.isna(), "runs"].sum())
    known = daily.loc[daily.index.notna()].sort_index()
    if not known.empty:
        dates = pd.date_range(known.index.min(), known.index.max(), freq="D")
        expanded = known.reindex(dates)
        ax.plot(expanded.index, expanded["mean_ms"], marker="o")
        for day, row in known.iterrows():
            if pd.notna(row["mean_ms"]):
                ax.annotate(f'n={int(row["measured"])}/{int(row["runs"])}',
                            (day, row["mean_ms"]), xytext=(0, 10),
                            textcoords="offset points", ha="center")
        ax.set_xticks(dates)
        ax.set_xticklabels([d.strftime("%m-%d") for d in dates], rotation=30)
        # 최댓값 위에 표본 수 주석을 놓을 여백을 확보합니다.
        ymax = known["mean_ms"].max()
        ax.set_ylim(0, max(1.0, float(ymax) * 1.25) if pd.notna(ymax) else 1.0)
    else:
        ax.text(0.5, 0.5, "No known observation date", transform=ax.transAxes, ha="center")
    ax.set(title=f"Daily mean latency (unknown-date runs={unknown})", xlabel="Observation date", ylabel="Latency (ms)")
    _save(fig, chart_dir, "daily_latency.png")
    return {"unknown_date_runs": unknown, "known_dates": len(known),
            "policy": "날짜 미상 별도 보고, 없는 날짜는 보간하지 않음"}
