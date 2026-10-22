"""실습 05: CSV/JSON 왕복 저장 및 자료형·결측의 의미를 확인합니다."""
from pathlib import Path
import numpy as np
import pandas as pd
from support import COLUMNS, read_raw, strict_json, staged_output, protect_inputs, require_columns
from eda.analyze import validate_meta


def flatten_meta(payload):
    """{agents:[{agent, pricing:{rate}}]} -> agent/rate_per_1k 표."""
    if not isinstance(payload, dict) or not isinstance(payload.get("agents"), list) or not payload["agents"]:
        raise ValueError("메타 JSON에는 비어 있지 않은 agents 목록이 필요합니다.")
    if not all(isinstance(item, dict) and isinstance(item.get("pricing"), dict)
               and "rate" in item["pricing"] for item in payload["agents"]):
        raise ValueError("각 역할에는 pricing.rate가 필요합니다.")
    # 해설 I_FLATTEN: json_normalize(payload["agents"], sep="_") 후 pricing_rate를 rate_per_1k로 바꾸고 validate_meta 결과를 반환하세요.
    flat = pd.json_normalize(payload["agents"], sep="_")
    meta = flat.rename(columns={"pricing_rate": "rate_per_1k"})
    return validate_meta(meta)


def read_meta(path):
    """문법이 맞아도 내용의 스키마를 따로 검사합니다."""
    return flatten_meta(strict_json(path))


def save_tables(clean, summary, out_dir):
    """정제 CSV와 요약 JSON을 지정한 임시/출력 폴더에 씁니다."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # 해설 I_CSV: clean_runs.csv를 index=False, encoding="utf-8-sig", date_format="%Y-%m-%d"로 저장하세요.
    # 해설 I_CSV: 날짜는 문자로, NaN은 빈 셀로 저장됩니다. 인덱스 열은 제외합니다.
    clean.to_csv(out_dir / "clean_runs.csv", index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    # 해설 I_JSON: summary.json을 orient="records", force_ascii=False, indent=2로 저장하세요. NaN을 문자열로 쓰지 않습니다.
    # 해설 I_JSON: pandas는 결측 수치를 JSON null로 변환합니다.
    summary.to_json(out_dir / "summary.json", orient="records", force_ascii=False, indent=2, double_precision=10)


def read_back(out_dir):
    """CSV ID는 문자열로 명시하고 JSON은 비표준 NaN/Infinity를 거부합니다."""
    out_dir = Path(out_dir)
    # 해설 I_READ: CSV run_id는 string dtype으로, JSON은 strict_json으로 다시 읽어 (back, records)를 반환하세요.
    back = pd.read_csv(out_dir / "clean_runs.csv", encoding="utf-8-sig", dtype={"run_id": "string"})
    records = strict_json(out_dir / "summary.json")
    return back, records


def verify_roundtrip(clean, summary, back, records):
    """저장 전후 행/열/ID/수치/날짜/요약을 비교합니다. 글자 byte 일치는 요구하지 않습니다."""
    # 해설 I_VERIFY: 행 수·ID·문자열·숫자/결측·날짜·요약 값을 저장 전후 대조하세요. 다르면 ValueError, 같으면 csv_rows/json_rows/latency_missing/verified 사전을 반환하세요.
    require_columns(back)
    if len(back) != len(clean) or not back["run_id"].is_unique:
        raise ValueError("CSV 행 수 또는 ID 고유성이 달라졌습니다.")
    if not isinstance(records, list) or len(records) != len(summary):
        raise ValueError("JSON은 요약 행 수와 같은 길이의 목록이어야 합니다.")
    restored = pd.DataFrame(records)
    require_columns(restored, list(summary.columns))
    # JSON null로 인해 object가 된 숫자 열을 복원한 뒤 의미를 비교합니다.
    for col in summary.columns:
        if pd.api.types.is_numeric_dtype(summary[col]):
            restored[col] = pd.to_numeric(restored[col], errors="raise").astype(float)
    try:
        for col in ["run_id", "agent", "status"]:
            if clean[col].astype("string").tolist() != back[col].astype("string").tolist():
                raise ValueError("CSV 문자열 열이 달라졌습니다: " + col)
        for col in ["latency_ms", "tokens"]:
            np.testing.assert_allclose(clean[col].to_numpy(float), back[col].to_numpy(float), equal_nan=True)
        before_day = pd.to_datetime(clean["day"], format="%Y-%m-%d", errors="coerce")
        after_day = pd.to_datetime(back["day"], format="%Y-%m-%d", errors="coerce")
        pd.testing.assert_series_equal(before_day.reset_index(drop=True), after_day.reset_index(drop=True), check_names=False)
        pd.testing.assert_frame_equal(summary.reset_index(drop=True), restored.reset_index(drop=True),
                                      check_dtype=False, check_exact=False, rtol=1e-8, atol=1e-8)
    except (AssertionError, TypeError) as exc:
        raise ValueError("저장 전후 수치·날짜·요약이 다릅니다.") from exc
    return {"csv_rows": len(back), "json_rows": len(records),
            "latency_missing": int(back["latency_ms"].isna().sum()), "verified": True}


def export_tables(clean, summary, out_dir, data_dir):
    """제공 흐름: 임시 저장 -> 재읽기 검사 -> 성공 시 기존 결과 교체."""
    protect_inputs(out_dir, data_dir)
    with staged_output(out_dir) as stage:
        save_tables(clean, summary, stage)
        back, records = read_back(stage)
        result = verify_roundtrip(clean, summary, back, records)
    return result
