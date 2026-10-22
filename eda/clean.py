"""실습 02 / EDA 프로젝트: 원본을 보존하며 정제 규칙을 적용합니다."""
import numpy as np
import pandas as pd
from support import COLUMNS, DEFAULT_AGENTS, require_columns


class DataContractError(ValueError):
    """분석을 중단할 식별자·범주 문제와 해당 행을 함께 전달합니다."""
    def __init__(self, issues):
        self.issues = issues
        super().__init__("데이터 계약 위반: " + ", ".join(sorted(set(issues["issue"]))))


def audit_contract(raw, allowed_agents=DEFAULT_AGENTS):
    """원본 표 -> issue/run_id/source_row 표. 충돌의 양쪽 행 모두 기록합니다.

    완전 중복 제거 후 문자열을 정리하여 검사합니다. 원본 순서의 source_row는
    CSV 헤더를 제외한 1부터 시작합니다. 빈 ID·충돌 ID·미등록 역할·상태 위반은
    임의로 한 행을 선택하지 않고 호출자에게 전달합니다.
    """
    # 해설 C_AUDIT: 완전 중복을 뺀 뒤 ID 공백/충돌, 역할/상태 허용값을 검사. issue, run_id, source_row 열의 표를 반환하세요. source_row는 원본 위치+1입니다.
    require_columns(raw)
    if raw.empty:
        raise ValueError("빈 입력: 분석할 실행 기록이 없습니다.")
    work = raw.loc[~raw.duplicated()].copy()
    work["source_row"] = np.flatnonzero(~raw.duplicated().to_numpy()) + 1
    ids = work["run_id"].astype("string").str.strip()
    agents = work["agent"].astype("string").str.strip().str.lower()
    states = work["status"].astype("string").str.strip().str.lower()
    masks = {
        "missing_id": ids.isna() | ids.eq(""),
        "conflicting_id": ids.duplicated(keep=False),
        "unknown_agent": ~agents.isin(allowed_agents),
        "unknown_status": ~states.isin(["ok", "error"]),
    }
    issues = []
    for reason, mask in masks.items():
        for pos in np.flatnonzero(mask.fillna(True).to_numpy()):
            row = work.iloc[pos]
            issues.append({"issue": reason, "run_id": row["run_id"], "source_row": int(row["source_row"])})
    return pd.DataFrame(issues, columns=["issue", "run_id", "source_row"])


def clean_runs(raw, allowed_agents=DEFAULT_AGENTS, *, parse_dates=True, strict_tokens=False):
    """6열 원본 -> 정제 DataFrame. 실패 행을 지우거나 결측을 0으로 채우지 않습니다.

    parse_dates=False는 실습 02 기본필수용입니다. strict_tokens=True이면
    분수 토큰도 NaN으로 표시합니다. 오류 행의 정체성은 원본에 남겨 둡니다.
    """
    issues = audit_contract(raw, allowed_agents)
    if not issues.empty:
        raise DataContractError(issues)
    # 해설 C_COPY: 모든 열이 같은 행만 제거해 복사하세요. ID 공백을 제거하고 agent/status는 공백 제거 후 소문자로 통일하세요.
    # 해설 C_COPY: 완전히 같은 기록만 제거합니다. ID만으로 지우지 않습니다.
    df = raw.drop_duplicates().copy().reset_index(drop=True)
    for col in ["run_id", "agent", "status"]:
        df[col] = df[col].astype("string").str.strip()
    df["agent"] = df["agent"].str.lower()
    df["status"] = df["status"].str.lower()
    # 해설 C_NUMERIC: latency_ms/tokens를 to_numeric(errors="coerce")로 변환. 음수·무한대는 NaN. strict_tokens이면 분수 토큰도 결측 처리하세요.
    # 해설 C_NUMERIC: 형식 오류와 범위 위반을 결측으로 표시합니다. 0은 유효합니다.
    for col in ["latency_ms", "tokens"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
        bad = ~np.isfinite(df[col]) | (df[col] < 0)
        df.loc[bad, col] = np.nan
    if strict_tokens:
        fractional = df["tokens"].notna() & df["tokens"].mod(1).ne(0)
        df.loc[fractional, "tokens"] = np.nan
    if parse_dates:
        # 해설 C_DATE: day를 format="%Y-%m-%d", errors="coerce"로 변환하세요. invalid는 NaT입니다.
        # 해설 C_DATE: 해석할 수 없는 날짜를 추측하지 않고 NaT로 남깁니다.
        df["day"] = pd.to_datetime(df["day"], format="%Y-%m-%d", errors="coerce")
    return df


def quality_report(raw, clean):
    """변환 전후 개수와 영향을 받은 실행 ID를 사전으로 반환합니다."""
    # 해설 C_QUALITY: README의 품질 사전 키에 맞게 원본/정제/결측/성공/실패 개수와 영향받은 ID를 반환하세요. 실패 행은 삭제하지 않습니다.
    day_missing = pd.to_datetime(clean["day"], format="%Y-%m-%d", errors="coerce").isna()
    return {
        "raw_rows": int(len(raw)), "clean_rows": int(len(clean)),
        "exact_duplicates_removed": int(raw.duplicated().sum()),
        "unique_ids": int(clean["run_id"].nunique()),
        "latency_valid": int(clean["latency_ms"].count()),
        "latency_missing": int(clean["latency_ms"].isna().sum()),
        "latency_missing_ids": clean.loc[clean["latency_ms"].isna(), "run_id"].tolist(),
        "tokens_valid": int(clean["tokens"].count()),
        "tokens_missing": int(clean["tokens"].isna().sum()),
        "day_missing": int(day_missing.sum()),
        "day_missing_ids": clean.loc[day_missing, "run_id"].tolist(),
        "ok": int(clean["status"].eq("ok").sum()),
        "error": int(clean["status"].eq("error").sum()),
        "policy": "실패 행 보존; 평균은 유효 측정; 성공률은 전체 실행; 결측 0 대체 금지",
    }
