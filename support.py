"""제공 코드: 경로·파일 검사와 테스트용 입력을 지원합니다. 정제·분석 정답은 없습니다."""
from contextlib import contextmanager
from pathlib import Path
import csv
import json
import math
import os
import shutil
import tempfile
import numpy as np
import pandas as pd

COLUMNS = ["run_id", "agent", "latency_ms", "tokens", "status", "day"]
DEFAULT_AGENTS = ("planner", "researcher", "writer")


def require_columns(frame, columns=COLUMNS):
    """명시적인 외부 입력 검증은 assert 대신 ValueError로 수행합니다."""
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError("필수 열 누락: " + ", ".join(missing))


def read_raw(path):
    """원본은 문자열로 읽어 공백·앞자리 0·잘못된 값을 보존합니다."""
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as f:
        header = next(csv.reader(f), None)
    if not header:
        raise ValueError("완전히 빈 CSV 파일입니다.")
    if len(header) != len(set(header)):
        raise ValueError("CSV 헤더에 중복된 열 이름이 있습니다.")
    frame = pd.read_csv(path, encoding="utf-8-sig", dtype="string", keep_default_na=False)
    require_columns(frame)
    if frame.empty:
        raise ValueError("헤더만 있는 CSV입니다. 분석할 실행 기록이 없습니다.")
    return frame.loc[:, COLUMNS].copy()


def read_clean(path):
    """다음 단원의 시작점으로 제공한 정제 CSV를 자료형에 맞게 복원합니다."""
    frame = pd.read_csv(path, encoding="utf-8-sig", dtype={"run_id": "string", "agent": "string", "status": "string"})
    require_columns(frame)
    for col in ["latency_ms", "tokens"]:
        frame[col] = pd.to_numeric(frame[col], errors="raise").astype(float)
    frame["day"] = pd.to_datetime(frame["day"], format="%Y-%m-%d", errors="coerce")
    return frame


def json_safe(value):
    """검사 기록용 NumPy 수치/결측을 표준 JSON 값으로 변환합니다."""
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [json_safe(v) for v in value]
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (pd.Timestamp, Path)):
        return str(value)
    return value


def write_json(path, value):
    """부모 폴더를 생성하고 표준 JSON을 저장하는 제공 보조 함수입니다."""
    path = Path(path)
    text = json.dumps(json_safe(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def strict_json(path):
    def reject_constant(text):
        raise ValueError("표준 JSON이 아닌 수치: " + text)
    with Path(path).open(encoding="utf-8-sig") as f:
        return json.load(f, parse_constant=reject_constant)


def protect_inputs(out_dir, data_dir, *input_paths):
    """원본 폴더 또는 원본 파일을 포함하는 위치에 결과를 게시하지 않습니다."""
    out_dir, data_dir = Path(out_dir).resolve(), Path(data_dir).resolve()
    if out_dir == data_dir or out_dir.is_relative_to(data_dir) or data_dir.is_relative_to(out_dir):
        raise ValueError("출력 폴더는 원본 data와 분리해야 합니다.")
    for path in input_paths:
        if path is not None and Path(path).resolve().is_relative_to(out_dir):
            raise ValueError("출력 폴더 안에 입력 파일이 있어 덮어쓰기를 중단합니다.")


@contextmanager
def staged_output(destination):
    """제공 안전장치: 모두 생성·검증한 뒤에만 결과 폴더를 교체합니다.

    읽기/정제/그림/재읽기 실패 시 기존 결과는 그대로입니다. 게시 실패 시
    백업을 복구합니다. 강제 종료·정전·동시 작성에 대한 DB 트랜잭션은 아닙니다.
    """
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not destination.is_dir():
        raise ValueError("출력 위치가 폴더가 아니라 파일입니다.")
    stage = Path(tempfile.mkdtemp(prefix=".eda-stage-", dir=destination.parent))
    backup = None
    try:
        yield stage
        if destination.exists():
            backup = Path(tempfile.mkdtemp(prefix=".eda-backup-", dir=destination.parent))
            backup.rmdir()
            os.replace(destination, backup)
        try:
            os.replace(stage, destination)
        except OSError:
            if backup is not None:
                os.replace(backup, destination)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
    finally:
        if stage.exists():
            shutil.rmtree(stage)
        # 복구 자체가 실패했다면 유일한 백업을 지우지 않고 남깁니다.


def load_inputs(base):
    """실습 03~05의 제공 체크포인트를 읽습니다."""
    base = Path(base)
    clean = read_clean(base / "data" / "clean_runs.csv")
    summary = pd.DataFrame(strict_json(base / "data" / "summary.json"))
    return clean, summary
