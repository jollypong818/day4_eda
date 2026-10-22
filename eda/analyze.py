"""실습 03 / EDA 프로젝트: 집계의 분모와 결합의 유효성을 확인합니다."""
import numpy as np
import pandas as pd
from support import require_columns


def aggregate_runs(clean):
    """정제 표 -> 역할별 runs/measured/mean_ms/median_ms/success_rate/success_pct.

    평균은 유효 측정만, 성공률은 error를 포함한 전체 실행이 분모입니다.
    원본을 수정하지 않으며 표시용 반올림을 계산에 적용하지 않습니다.
    """
    require_columns(clean)
    if not clean["status"].isin(["ok", "error"]).all():
        raise ValueError("알 수 없는 상태를 실패로 간주할 수 없습니다.")
    # 해설 A_GROUP: ok bool 열을 복사본에 만들고 이름 있는 groupby.agg로 6개 지표를 계산하세요. success_pct=success_rate*100입니다.
    df = clean.copy()
    df["ok"] = df["status"].eq("ok")
    result = df.groupby("agent", as_index=False, sort=True, observed=True).agg(
        runs=("run_id", "size"), measured=("latency_ms", "count"),
        mean_ms=("latency_ms", "mean"), median_ms=("latency_ms", "median"),
        success_rate=("ok", "mean"),
    )
    result["success_pct"] = result["success_rate"] * 100
    return result


def make_pivot(clean):
    """역할×상태 평균 표. NaN을 0으로 채우지 않습니다."""
    # 해설 A_PIVOT: agent×status 평균 pivot_table(observed=True)을 만들고 역할/상태 열을 reindex하세요. NaN은 0으로 채우지 않습니다.
    pivot = clean.pivot_table(index="agent", columns="status", values="latency_ms",
                             aggfunc="mean", observed=True)
    # 모든 측정이 결측인 역할과 관측이 없는 상태도 표에서 볼 수 있게 합니다.
    return pivot.reindex(index=sorted(clean["agent"].unique()), columns=["error", "ok"])


def validate_meta(meta):
    """결합 전에 메타데이터 스키마·키·단가를 검증하는 제공 안전장치입니다."""
    require_columns(meta, ["agent", "rate_per_1k"])
    result = meta.copy()
    result["agent"] = result["agent"].astype("string").str.strip().str.lower()
    if result.empty or result["agent"].isna().any() or result["agent"].eq("").any():
        raise ValueError("메타데이터의 역할 키가 비어 있습니다.")
    if result["agent"].duplicated().any():
        raise ValueError("중복 메타 키: " + ", ".join(result.loc[result["agent"].duplicated(), "agent"]))
    result["rate_per_1k"] = pd.to_numeric(result["rate_per_1k"], errors="coerce").astype(float)
    if (~np.isfinite(result["rate_per_1k"]) | result["rate_per_1k"].lt(0)).any():
        raise ValueError("단가는 0 이상의 유한한 수치여야 합니다.")
    return result


def join_meta(clean, meta):
    """실행 표에 다대일 메타 결합. 미연결 키는 오류로 보고 중단합니다."""
    meta = validate_meta(meta)
    if clean["agent"].isna().any():
        raise ValueError("왼쪽 역할 키가 결측입니다.")
    # 해설 A_JOIN: left merge(validate="many_to_one", indicator=True). 행 수와 _merge를 검사하고 미연결 시 ValueError. cost_unit을 계산하세요.
    joined = clean.merge(meta, on="agent", how="left", validate="many_to_one", indicator=True)
    if len(joined) != len(clean):
        raise ValueError("결합 후 실행 행 수가 달라졌습니다.")
    unmatched = joined.loc[joined["_merge"].ne("both"), "agent"].unique().tolist()
    if unmatched:
        raise ValueError("미등록 메타 키: " + ", ".join(unmatched))
    joined["cost_unit"] = joined["tokens"] / 1000 * joined["rate_per_1k"]
    return joined


def daily_summary(clean):
    """날짜 미상도 남긴 날짜별 실행 수/유효 수/평균을 반환합니다."""
    # 해설 A_DAILY: day를 dropna=False로 묶어 runs/measured/mean_ms를 집계하세요. 날짜 미상도 남깁니다.
    return clean.groupby("day", dropna=False, sort=True).agg(
        runs=("run_id", "size"), measured=("latency_ms", "count"), mean_ms=("latency_ms", "mean"))


def cost_audit(joined):
    """토큰 관측이 없는 전체 합계를 0이라고 쓰지 않습니다."""
    # 해설 A_COST: 유효 비용 개수와 sum(min_count=1), 전체 수, 부분합 여부를 README의 사전 키로 반환하세요.
    count = int(joined["cost_unit"].count())
    value = float(joined["cost_unit"].sum(min_count=1))
    return {"cost_unit": value, "measured": count, "runs": len(joined),
            "is_partial": count < len(joined), "unit": "가상 단위/실제 가격 아님"}


def weighted_mean(means, counts):
    """분모가 다른, 중복 없는 같은 단위 집단의 평균을 합칩니다."""
    # 해설 A_WEIGHT: 평균과 개수 shape/범위를 검사하고 양수 가중치의 np.average를 반환하세요. 전부 0건이면 NaN.
    means = np.asarray(means, dtype=float)
    counts = np.asarray(counts, dtype=float)
    if means.shape != counts.shape or means.ndim != 1:
        raise ValueError("평균과 개수는 길이가 같은 1차원 배열이어야 합니다.")
    if (~np.isfinite(counts) | (counts < 0) | (counts % 1 != 0)).any():
        raise ValueError("측정 개수는 0 이상의 유한한 정수여야 합니다.")
    if ((counts > 0) & ~np.isfinite(means)).any():
        raise ValueError("측정이 있는 그룹의 평균이 유효하지 않습니다.")
    valid = counts > 0
    return float(np.average(means[valid], weights=counts[valid])) if valid.any() else np.nan
