"""
데이터 분석 전체 파이프라인 구축

[목표]

데이터 입력받고 분석결과를 자동으로 생성하는 프로그램 제작 

[[전체처리과정]]

1. 원본데이터 불러오기 
2. 데이터정제(cleaning)
3. 통계 집계 및 품질검사(Analysis)
4. CSV/JSON 파일 저장
5. 저장된 파일 다시 읽고 검증
6. 그래프 생성(Visualization)
7. 분석 결과 및 검증 정보 저장
8. 모든 단계가 성공하면 최종 결과 반영

[이번 실습에서 연결할 이전 실습]

실습 02 - clean_runs()
    → 잘못된 데이터와 결측값을 정리

실습 03 - aggregate_runs()
    → 에이전트별 평균, 실행 수, 성공률 등을 계산

실습 04 - plot_bar(), plot_hist()
    → 분석 결과를 막대그래프와 히스토그램으로 표현

실습 05 - save_tables(), read_back(), verify_roundtrip()
    → 분석 데이터를 CSV/JSON으로 저장하고 검증

[이번 프로젝트의 중요한 원칙]

- 원본 입력 데이터를 임의로 변경하지 않습니다.
- 데이터에 오류가 있으면 잘못된 결과를 생성하지 않습니다.
- NaN(결측값)을 임의로 0으로 변경하지 않습니다.
- 집계된 수치와 실제 데이터 수가 일치하는지 검사합니다.
- 결과를 임시 위치에 먼저 저장하고 검증합니다.
- 모든 검증에 성공한 경우에만 최종 결과로 반영합니다.
"""

#필요한 라이브러리 및 함수 불러오기

# 파일과 폴더의 경로 관리 
from pathlib import Path
# 프로그램 실행 시 명령어 인자 처리
import argparse
# 파일의 해시값을 계산하기 위한 라이브러리 
# SHA_256 해시 알고리즘을 사용하여 파일의 무결성을 확인
import hashlib
#json 형식의 데이터 처리
import json
#numpy 라이브러리: 수치 계산 및 배열 처리
import numpy as np

# ------------------------------------------------------------
# support.py에서 제공하는 공통 기능
# ------------------------------------------------------------

from support import (
    read_raw,               # 원본 CSV 파일을 읽어오는 함수
    write_json,             # JSON 파일을 쓰는 함수
    json_safe,              # JSON 직렬화에 안전한 데이터로 변환하는 함수
    protect_inputs,         # 원본 입력 데이터를 보호하는 함수
    staged_output,          # 단계별 출력 디렉토리를 생성하고 관리하는 함수
    DEFAULT_AGENTS          # 기본 에이전트 목록을 제공하는 상수
)


# ------------------------------------------------------------
# 실습 02: 데이터 정제 관련 함수
# ------------------------------------------------------------

from eda.clean import (
    clean_runs,             # 원본 데이터를 정제하는 함수, 숫자 변환, 공백 제거, 중복 제거 등을 수행
    quality_report,         # 데이터 품질을 평가하고 보고서를 생성하는 함수
    DataContractError       # 데이터 계약 위반 시 발생하는 예외 클래스
)

# ------------------------------------------------------------
# 실습 03: 통계 분석 관련 함수
# ------------------------------------------------------------

from eda.analyze import (
    aggregate_runs,         # 에이전트별 통계 집계를 수행하는 함수, 평균, 실행 수, 성공률 등을 계산
    make_pivot,             # 피벗 테이블을 생성하는 함수
    join_meta,              # 메타데이터를 조인하는 함수
    daily_summary,          # 날짜별 실행 횟수와 평균 실행 시간을 계산
    cost_audit              # 토큰 사용 비용과 비용 데이터의 누락 여부를 확인
)


# ------------------------------------------------------------
# 실습 04: 데이터 시각화 관련 함수
# ------------------------------------------------------------

from eda.plot import (
    plot_bar,               # 막대그래프를 생성하는 함수
    plot_hist,              # 히스토그램을 생성하는 함수
    plot_scatter,           # 산점도를 생성하는 함수
    plot_daily              # 날짜별 실행 횟수와 평균 실행 시간을 시각화하는 함수
)


# ------------------------------------------------------------
# 실습 05: 파일 저장 및 검증 관련 함수
# ------------------------------------------------------------

from eda.io_utils import (
    save_tables,            # 분석 데이터를 CSV/JSON으로 저장하는 함수
    read_back,              # 저장된 CSV/JSON 파일을 다시 읽어오는 함수
    verify_roundtrip,       # 저장된 파일을 읽고 검증하는 함수
    read_meta               # 메타데이터를 읽어오는 함수
)




# ============================================================
# 2. 프로그램의 기본 설정
# ============================================================
# 현재 파일(main.py)의 경로를 기준으로 프로젝트의 기본 디렉토리(BASE_DIR)를 설정
BASE_DIR = Path(__file__).resolve().parent

#프로젝트 실습 난이도 지정 , basic, applied, advanced 중 하나를 선택
LEVEL = "basic"


# ============================================================
# 3. 전체 데이터 분석 파이프라인
# ============================================================
def run_pipeline(input_path, out_dir, meta_path=None):
    """
    전체 데이터 분석 파이프라인을 실행하는 함수

    Args:
        input_path (str): 원본 CSV 파일 경로
        out_dir (str): 분석 결과를 저장할 디렉토리 경로
        meta_path (str, optional): 메타데이터 파일 경로. 기본값은 None.

    Returns:
        전체 실행 결과를 요약한 딕셔너리 
    """

    """
    [전체 처리 흐름]
        ① 입력 경로 확인 및 원본 보호
        ② 원본 파일의 SHA-256 해시 계산
        ③ 필요하면 메타데이터 로드
        ④ 원본 CSV 읽기
        ⑤ 데이터 정제 및 통계 집계
        ⑥ 데이터 개수와 집계 결과 검증
        ⑦ 임시 폴더에 CSV/JSON 저장
        ⑧ 저장된 파일을 다시 읽고 검증
        ⑨ 그래프 생성 및 분석 결과 저장
        ⑩ 원본 파일이 변경되지 않았는지 최종 확인
        ⑪ 모든 과정이 성공하면 최종 결과 반영

    """
    #. 파일 경로를 절대 경로로 변환
    input_path = Path(input_path).resolve()
    out_dir = Path(out_dir).resolve()

    # 원본 입력 데이터 보호 
    protect_inputs(
        out_dir,
        input_path,
        BASE_DIR / "data",
        meta_path
    )

    # --------------------------------------------------------
    # [3단계] 원본 파일의 SHA-256 해시값 계산
    # --------------------------------------------------------
    original_hash = hashlib.sha256(
        input_path.read_bytes()     # 원본 파일의 바이트 데이터를 읽어와 SHA-256 해시를 계산
    ).hexdigest()                   # 16진수 문자열로 변환하여 저장

    # --------------------------------------------------------
    # [4단계] 메타데이터 불러오기
    # --------------------------------------------------------
    # 메타데이터 파일이 제공되면 읽어오고, 그렇지 않으면 None으로 설정
    meta = read_meta(meta_path) if meta_path is not None else None

    # 응용(applied) 또는 심화(advanced) 실습에서는
    # 메타데이터가 반드시 필요합니다.
    #
    # LEVEL != "basic"
    #   → 현재 난이도가 기본필수가 아닌지 검사합니다.
    #
    # meta is None
    #   → 메타데이터를 불러오지 않았는지 검사합니다.
    #
    # 두 조건이 모두 참이면 오류를 발생시킵니다.
    if LEVEL != "basic" and meta is None:
        raise ValueError(
            "응용/심화 프로젝트에는 역할 메타데이터 경로가 필요합니다."
        )

    # --------------------------------------------------------
    # [5단계] 허용할 에이전트 목록 설정
    # --------------------------------------------------------
    # 메타데이터에 에이전트 정보가 포함되어 있으면 그 정보를 사용하고,
    # 그렇지 않으면 기본 에이전트 목록을 사용합니다.
    allowed = (
        tuple(meta["agent"])
        if meta is not None
        else DEFAULT_AGENTS
    )


    # ========================================================
    # TODO PIPE_CORE: 수강생이 직접 구현할 부분
    # ========================================================
    #
    # [목표]
    # 원본 데이터를 읽고 정제한 다음,
    # 에이전트별 통계와 데이터 품질 정보를 생성합니다.
    #
    # 다음 네 개의 변수를 완성해야 합니다.
    #
    # raw
    #   → 원본 실행 기록 DataFrame
    #
    # clean
    #   → 정제된 실행 기록 DataFrame
    #
    # summary
    #   → 에이전트별 통계 DataFrame
    #
    # quality
    #   → 데이터 품질 검사 결과
    #
    # [구현 순서]
    #
    # ① read_raw()를 사용해 CSV 파일을 읽습니다.
    #
    #    입력: input_path
    #    출력: raw
    #
    #    원본 데이터에는 중복 기록이나
    #    잘못된 숫자 등이 포함될 수 있습니다.
    raw = read_raw(input_path)

    # ② clean_runs()로 원본 데이터를 정제합니다.
    #
    #    입력: raw, allowed
    #    출력: clean
    #
    #    allowed는 허용할 에이전트 목록입니다.
    #
    #    clean_runs()는 앞선 실습에서 구현한 함수입니다.
    #    잘못된 값은 규칙에 따라 처리하고
    #    완전히 동일한 중복 기록 등을 제거합니다.
    clean = clean_runs(raw, allowed)
    # ③ aggregate_runs()로 통계를 계산합니다.
    #
    #    입력: clean
    #    출력: summary
    #
    #    계산할 주요 통계:
    #    - 전체 실행 횟수
    #    - 유효 측정 횟수
    #    - 평균 실행 시간
    #    - 중앙값
    #    - 성공률
    #

    summary = aggregate_runs(clean)

    # ④ quality_report()로 데이터 품질을 확인합니다.
    #
    #    정제 데이터에 대한 품질 검사 결과를
    #    quality 변수에 저장합니다.
    #
    quality = quality_report(clean, summary)
    # [중요]
    # 함수들을 따로 실행하는 것이 아니라
    # 앞 단계의 결과를 다음 단계의 입력으로 전달해야 합니다.
    #
    # 원본 → 정제 → 집계 → 품질 검사
    #
    # 필요한 함수:
    # read_raw()
    # clean_runs()
    # aggregate_runs()
    # quality_report()
    #
    # 아래 오류는 아직 구현하지 않았음을 의미합니다.
    # 수강생이 코드를 완성한 뒤 제거해야 합니다.
    # raise NotImplementedError("TODO PIPE_CORE")


    # --------------------------------------------------------
    # [6단계] 정제 및 집계 결과 검증

    # 정제(clean)한 데이터와 그룹별 집계(summary) 결과가
    # 논리적으로 일치하는지 확인하는 단계.
    #
    # 이런 검사를 불변식(Invariant) 검사라고 함.
    # 불변식이란 프로그램이 정상적으로 처리되었다면 반드시 성립해야 하는 조건을 의미.
    # --------------------------------------------------------

    # 정제된 데이터의 run_id가 고유한지 확인하고,
    # 집계된 실행 횟수와 정제 데이터의 행 수가 일치하는지 확인
    if (
        not clean["run_id"].is_unique
        or int(summary["runs"].sum()) != len(clean) # 모든 에이전트의 실행 횟수를 합한 값과 정제 데이터의 행 수가 일치하는지 확인
    ):
        raise ValueError("정제/집계의 행 수 불변식이 깨졌습니다.")



    # 정제된 데이터의 유효 측정 개수와 집계된 유효 측정 개수가 일치하는지 확인
    # 유효 측정 개수란?
    # → 실행시간(latency_ms)이 실제로 기록된 데이터의 개수
    # → NaN(결측값)은 측정되지 않은 값이므로 제외합니다.
    #
    # 예시: 정제된 데이터(clean)
    #
    # agent       latency_ms
    # planner     100
    # planner     120
    # coder       200
    # coder       NaN
    # reviewer    150
    #
    # 전체 실행 기록은 5건이지만
    # latency_ms가 존재하는 기록은 4건입니다.
    #
    # 따라서 유효 측정 개수는 4건입니다.


    # ① clean["latency_ms"].count()
    #    → 정제 데이터에서 latency_ms가 존재하는 행의 개수
    #    → Pandas의 count()는 NaN을 제외하고 계산합니다.
    #
    #    위 예시에서는 4가 반환됩니다.


    # ② summary["measured"].sum()
    #    → 에이전트별로 집계한 유효 측정 개수를 모두 더합니다.
    #
    # 예시: 그룹별 집계 결과(summary)
    #
    # agent       runs    measured
    # planner       2        2
    # coder         2        1
    # reviewer      1        1
    #
    # runs     : 전체 실행 횟수 (NaN 포함)
    # measured : 실행시간이 기록된 횟수 (NaN 제외)
    #
    # summary["measured"].sum() = 2 + 1 + 1 = 4
    # clean["latency_ms"].count() = 4
    #
    # 두 값은 반드시 일치해야 합니다.


    # 왜 비교할까?
    #
    # clean은 정제된 개별 실행 기록이고,
    # summary는 clean을 에이전트별로 묶어 요약한 결과입니다.
    #
    # 따라서 원본에서 직접 센 유효 측정 개수와
    # 그룹별로 집계한 유효 측정 개수의 합은 같아야 합니다.
    #
    # 예를 들어:
    #
    # clean에서 직접 센 유효 측정 개수 = 4
    # summary에서 집계한 유효 측정 개수 = 3
    #
    # → 집계 과정에서 데이터가 누락되었을 가능성이 있습니다.
    # → 두 값이 다르면 ValueError를 발생시킵니다.
    #
    # int()는 비교할 값을 정수형으로 변환하기 위해 사용합니다.

    if int(summary["measured"].sum()) != int(clean["latency_ms"].count()):
        raise ValueError("유효 측정 개수가 집계와 일치하지 않습니다.")

    # --------------------------------------------------------
    # [7단계] 실행 기록과 메타데이터 결합
    # --------------------------------------------------------
    # 메타데이터가 제공되면 정제(clean)된 실행 기록과 결합(join)합니다.
    joined = join_meta(clean, meta) if meta is not None else None

    # --------------------------------------------------------
    # [8단계] 임시 저장 영역 준비
    # --------------------------------------------------------
    with staged_output(out_dir) as stage:
        # ====================================================
        # TODO PIPE_FILES: 수강생이 직접 구현할 부분
        # ====================================================
        #
        # [목표]
        # 정제 데이터와 집계 데이터를 파일로 저장한 뒤
        # 다시 읽고 검증합니다.
        #
        # [구현 순서]
        #
        # ① save_tables()를 사용합니다.
        #
        #    clean 데이터를 CSV 파일로 저장합니다.
        #    summary 데이터를 JSON 파일로 저장합니다.
        #
        #    저장 위치는 최종 out_dir가 아닌
        #    임시 출력 경로인 stage입니다.
        #
        save_tables(clean, summary, stage)
        # ② read_back()을 사용합니다.
        #
        #    임시 폴더에 저장한 CSV와 JSON을 다시 읽습니다.
        #
        #    반환되는 두 값:
        #    back    → CSV 복원 데이터
        #    records → JSON 복원 데이터
        #
        back, records = read_back(stage)

        # ③ verify_roundtrip()을 사용합니다.
        #
        #    저장 전 데이터와 복원 데이터를 비교합니다.
        #
        #    검증 항목:
        #    - 행 개수
        #    - 실행 ID
        #    - 문자열
        #    - 숫자
        #    - 결측값
        #    - 날짜
        #    - 요약 데이터
        #
        # ④ 검증 결과를 roundtrip 변수에 저장합니다.
        roundtrip = verify_roundtrip(clean, summary, back, records)
        #
        # [중요]
        # roundtrip 변수는 이후 코드에서 사용하므로
        # 반드시 생성해야 합니다.
        #
        # 아래 오류는 구현이 완료되면 제거합니다.
        # raise NotImplementedError("TODO PIPE_FILES")

        # ====================================================
        # TODO PIPE_CHARTS: 수강생이 직접 구현할 부분
        # ====================================================
        #
        # [목표]
        # 데이터를 시각화하여 두 개의 그래프를 생성합니다.
        #
        # [구현 순서]
        #
        # ① 그래프 저장 폴더를 지정합니다.
        #
        #    stage / "charts"
        #
        #    임시 폴더 안에 charts 폴더를 사용하는 구조입니다.
        #
        stage_charts = stage / "charts"
        # ② plot_bar()를 호출합니다.
        #
        #    입력 데이터: summary
        #    출력 이미지: latency_by_agent.png
        #
        #    에이전트별 평균 실행 시간을 비교하는
        #    막대그래프를 생성합니다.
        #
        plot_bar(summary, stage_charts / "latency_by_agent.png")
        # ③ plot_hist()를 호출합니다.
        #
        #    입력 데이터: clean
        #    출력 이미지: latency_hist.png
        #
        #    실행 시간의 구간별 분포를 보여주는
        #    히스토그램을 생성합니다.
        #
        plot_hist(clean, stage_charts / "latency_hist.png")
        # ④ 두 함수의 반환값을 chart_audit에 저장합니다.
        #
        #    chart_audit는 다음 키를 가진 딕셔너리입니다.
        #
        #    "bar"  → 막대그래프 분석 정보
        #    "hist" → 히스토그램 분석 정보
        chart_audit = {
            "bar": plot_bar(summary, stage_charts / "latency_by_agent.png"),
            "hist": plot_hist(clean, stage_charts / "latency_hist.png")
        }
        #
        # [참고]
        # 그래프 이미지뿐 아니라 그래프에 사용한 수치도
        # 저장하여 결과를 검증할 수 있도록 합니다.
        #
        # 아래 오류는 구현한 뒤 제거합니다.
        # raise NotImplementedError("TODO PIPE_CHARTS")


        # ----------------------------------------------------
        # [9단계] 응용/심화 실습 추가 분석
        # ----------------------------------------------------

        # 현재 LEVEL이 "basic"이 아니라면
        # 추가 시각화 및 데이터 결합 결과를 저장합니다.
        #
        # basic: 실행하지 않음
        # applied: 실행
        # advanced: 실행
        if LEVEL != "basic":

            # [9-1] 토큰 사용량과 실행 시간의 산점도를 생성합니다.
            #
            # chart_audit 딕셔너리에 "scatter" 항목을 추가합니다.
            #
            # 출력 파일: charts/tokens_latency.png
            chart_audit["scatter"] = plot_scatter(
                clean,
                stage / "charts"
            )

            # [9-2] 에이전트×상태별 평균 실행 시간 표를 저장합니다.
            #
            # make_pivot():
            #   → agent와 status를 기준으로 피벗 테이블 생성
            #
            # to_csv():
            #   → 생성한 피벗 테이블을 CSV로 저장
            #
            # 출력 파일: pivot.csv
            #
            # 인덱스(agent)는 기본 설정에 따라 함께 저장됩니다.
            make_pivot(clean).to_csv(
                stage / "pivot.csv",
                encoding="utf-8-sig"
            )

            # [9-3] 메타데이터가 결합된 실행 기록을 저장합니다.
            #
            # joined에는 원본 실행 기록 외에도
            # 단가와 토큰 사용 비용 등의 정보가 포함됩니다.
            #
            # 출력 파일: joined_runs.csv
            #
            # index=False:
            #   → DataFrame 인덱스를 별도 열로 저장하지 않습니다.
            #
            # date_format:
            #   → 날짜를 연도-월-일 형식으로 저장합니다.
            joined.to_csv(
                stage / "joined_runs.csv",
                index=False,
                encoding="utf-8-sig",
                date_format="%Y-%m-%d"
            )

        # ----------------------------------------------------
        # [10단계] 심화 실습 추가 분석
        # ----------------------------------------------------

        # LEVEL이 "advanced"인 경우에만 실행합니다.
        #
        # 날짜별 통계와 날짜별 선그래프를 추가 생성합니다.
        if LEVEL == "advanced":

            # [10-1] 날짜별 집계 결과를 CSV로 저장합니다.
            #
            # daily_summary():
            #   → 날짜별 전체 실행 횟수
            #   → 유효 측정 횟수
            #   → 평균 실행 시간
            #
            # 출력 파일: daily.csv
            #
            # 날짜가 없는 기록(NaT)도 집계에 포함됩니다.
            daily_summary(clean).to_csv(
                stage / "daily.csv",
                encoding="utf-8-sig",
                date_format="%Y-%m-%d"
            )

            # [10-2] 날짜별 평균 실행 시간 선그래프를 생성합니다.
            #
            # 출력 파일: charts/daily_latency.png
            #
            # 날짜가 없는 기록은 별도로 계산하고
            # 데이터가 없는 날짜는 임의로 채우지 않습니다.
            chart_audit["daily"] = plot_daily(
                clean,
                stage / "charts"
            )

        # ----------------------------------------------------
        # [11단계] 전체 실행 시간 통계 계산
        # ----------------------------------------------------

        # clean의 latency_ms 열에서 NaN을 제외합니다.
        #
        # dropna():
        #   → 결측값을 제외합니다.
        #
        # to_numpy():
        #   → Pandas Series를 NumPy 배열로 변환합니다.
        #
        # values에는 정상적으로 측정된 실행 시간만 남습니다.
        #
        # 예:
        # [100, 200, NaN, 400]
        #           ↓
        # [100, 200, 400]
        values = clean["latency_ms"].dropna().to_numpy()

        # ----------------------------------------------------
        # [12단계] 분석 결과를 하나의 딕셔너리로 정리
        # ----------------------------------------------------

        # facts:
        # 최종 분석 결과의 핵심 수치를 모아 놓은 딕셔너리입니다.
        #
        # 딕셔너리는 다음 형태로 데이터를 저장합니다.
        #
        # {
        #     "키": 값,
        #     "키": 값
        # }
        facts = {

            # 정제 데이터의 품질 검사 결과입니다.
            "quality": quality,

            # 전체 유효 실행 시간의 평균입니다.
            #
            # values.mean():
            #   → 유효 측정값들의 산술평균을 계산합니다.
            #
            # len(values):
            #   → 유효 측정값의 개수입니다.
            #
            # 값이 하나도 없다면 평균을 계산할 수 없으므로
            # np.nan을 반환합니다.
            #
            # 예:
            # [100, 200, 300] → 평균 200
            "overall_mean_ms": (
                float(values.mean())
                if len(values)
                else np.nan
            ),

            # 전체 실행 시간의 중앙값입니다.
            #
            # np.median():
            #   → 데이터를 정렬했을 때 중앙에 위치하는 값
            #
            # 예:
            # [100, 200, 900] → 중앙값 200
            #
            # 평균은 400이지만 중앙값은 200입니다.
            # 큰 값의 영향을 비교할 때 유용합니다.
            "overall_median_ms": (
                float(np.median(values))
                if len(values)
                else np.nan
            ),

            # 전체 실행 시간의 90백분위수(P90)입니다.
            #
            # np.quantile(values, 0.9):
            #   → 데이터 분포의 90% 지점에 해당하는 값을 계산합니다.
            #
            # 예를 들어 P90이 800ms라면
            # 실행 시간 분포의 상위 10%가 시작되는
            # 경계 수준을 이해하는 데 사용할 수 있습니다.
            #
            # method="linear":
            #   → 인접한 값 사이를 선형 보간하여
            #     백분위수를 계산하는 방식입니다.
            #
            # 유효한 값이 없다면 NaN을 반환합니다.
            "p90_ms": (
                float(np.quantile(values, .9, method="linear"))
                if len(values)
                else np.nan
            ),

            # 히스토그램의 구간별 데이터 개수입니다.
            #
            # plot_hist()에서 계산한 결과를 재사용합니다.
            #
            # 예:
            # [3, 5, 2, 0, 1]
            #
            # 각 구간에 몇 개의 실행 기록이 있는지 의미합니다.
            "hist_counts": chart_audit["hist"]["counts"],

            # 토큰 사용 비용에 대한 감사 정보입니다.
            #
            # joined가 존재하면 cost_audit()를 실행합니다.
            #
            # 메타데이터가 없어 joined가 None이면
            # 비용 정보도 None으로 저장합니다.
            #
            # 비용은 실습용 가상 단가를 기준으로 계산됩니다.
            "cost": (
                cost_audit(joined)
                if joined is not None
                else None
            ),

            # 분석 시작 시 계산한 원본 파일의 SHA-256 해시입니다.
            #
            # 분석 결과가 어떤 입력 파일 내용을 기반으로
            # 생성되었는지 확인할 때 사용할 수 있습니다.
            "input_sha256": original_hash,

            # 이번 실습 데이터가 합성 데이터라는 표시입니다.
            #
            # True:
            #   → 제공된 데이터가 실제 운영 데이터가 아닌
            #     실습용 합성 데이터라는 의미로 기록합니다.
            #
            # 이 값은 별도 탐지 결과가 아니라
            # 프로젝트에서 지정한 메타 정보입니다.
            "synthetic_data": True
        }

        # ----------------------------------------------------
        # [13단계] 분석 결과와 검증 정보 저장
        # ----------------------------------------------------

        # 각 결과를 별도의 JSON 파일로 저장합니다.
        #
        # 모든 파일은 우선 임시 폴더(stage)에 생성됩니다.

        # [13-1] 데이터 품질 검사 결과
        #
        # 출력 파일: quality.json
        write_json(
            stage / "quality.json",
            quality
        )

        # [13-2] CSV/JSON 왕복 저장 검증 결과
        #
        # 출력 파일: roundtrip_check.json
        #
        # 저장 전후 데이터가 동일한지 검사한 결과를 기록합니다.
        write_json(
            stage / "roundtrip_check.json",
            roundtrip
        )

        # [13-3] 그래프 생성에 사용한 수치 정보
        #
        # 출력 파일: chart_audit.json
        #
        # 막대그래프와 히스토그램의 측정 정보 등을 저장합니다.
        # 응용/심화에서는 추가 그래프 정보도 포함됩니다.
        write_json(
            stage / "chart_audit.json",
            chart_audit
        )

        # [13-4] 최종 핵심 분석 수치
        #
        # 출력 파일: facts.json
        #
        # 평균, 중앙값, P90, 비용, 해시 등의 정보가 포함됩니다.
        write_json(
            stage / "facts.json",
            facts
        )

        # ----------------------------------------------------
        # [14단계] 실행 중 원본 파일 변경 여부 검사
        # ----------------------------------------------------

        # 분석 시작 시 계산한 original_hash와
        # 현재 원본 파일을 다시 읽어 계산한 해시값을 비교합니다.
        #
        # 해시값이 다르면 원본 파일 내용이
        # 실행 도중 변경되었을 가능성이 있습니다.
        #
        # 이 경우 이미 생성한 분석 결과가
        # 현재 원본 파일과 일치한다고 보장할 수 없습니다.
        #
        # 따라서 ValueError를 발생시켜
        # 최종 결과 반영을 중단합니다.
        if hashlib.sha256(input_path.read_bytes()).hexdigest() != original_hash:
            raise ValueError(
                "실행 중 원본이 바뀌어 결과 게시를 중단합니다."
            )

    # --------------------------------------------------------
    # [15단계] 전체 실행 결과 요약 반환
    # --------------------------------------------------------

    # with 블록이 정상적으로 종료되면
    # staged_output()의 처리 흐름에 따라
    # 검증된 결과가 최종 출력 폴더에 반영됩니다.
    #
    # 이제 파이프라인 실행 결과를 딕셔너리로 반환합니다.
    #
    # raw_rows:
    #   → 원본 CSV의 전체 행 개수
    #
    # clean_rows:
    #   → 정제 후 실행 기록 수
    #
    # summary_rows:
    #   → 에이전트별 집계 결과의 행 개수
    #
    # measured:
    #   → 유효한 실행 시간의 개수
    #
    # charts:
    #   → 생성한 그래프 개수
    #   → basic=2, applied=3, advanced=4
    #
    # out:
    #   → 최종 출력 폴더의 이름
    #
    # roundtrip_verified:
    #   → CSV/JSON 왕복 저장 검증 통과 여부
    #
    # 참고:
    # out_dir.name은 전체 경로가 아닌 마지막 폴더 이름입니다.
    #
    # 예:
    # C:/AI_Project/out → "out"
    return {
        "raw_rows": len(raw),
        "clean_rows": len(clean),
        "summary_rows": len(summary),
        "measured": int(clean["latency_ms"].count()),
        "charts": (
            2 if LEVEL == "basic"
            else (3 if LEVEL == "applied" else 4)
        ),
        "out": out_dir.name,
        "roundtrip_verified": roundtrip["verified"]
    }


# ============================================================
# 4. 프로그램 실행 설정 및 명령행 인자 처리
# ============================================================

def main():
    """프로그램 실행 옵션을 읽고 전체 파이프라인을 호출합니다.

    [명령행 인자란?]

    프로그램 실행 시 사용자가 추가로 전달하는 옵션입니다.

    예:
    python main.py --input data/agent_runs.csv --out out

    이 명령어에서

    python main.py
        → main.py 파일을 실행합니다.

    --input
        → 분석할 입력 CSV 파일을 지정합니다.

    --out
        → 분석 결과를 저장할 폴더를 지정합니다.

    별도의 옵션을 지정하지 않으면
    프로그램에 설정된 기본값을 사용합니다.
    """

    # --------------------------------------------------------
    # [1단계] 명령행 인자 처리 객체 생성
    # --------------------------------------------------------

    # argparse.ArgumentParser():
    #   → 프로그램의 실행 옵션을 정의하고 분석합니다.
    #
    # description=__doc__
    #   → 파일 맨 위에 작성한 설명 문자열을
    #     명령어 도움말에 사용합니다.
    #
    # 예:
    # python main.py --help
    #
    # 명령어를 실행하면 사용 가능한 옵션을 확인할 수 있습니다.
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    # --------------------------------------------------------
    # [2단계] 입력 CSV 옵션 설정
    # --------------------------------------------------------

    # --input:
    #   → 분석할 원본 CSV 파일의 경로를 지정합니다.
    #
    # default="data/agent_runs.csv":
    #   → 사용자가 지정하지 않으면 기본 입력 파일을 사용합니다.
    #
    # 예:
    # python main.py --input data/test.csv
    parser.add_argument(
        "--input",
        default="data/agent_runs.csv"
    )

    # --------------------------------------------------------
    # [3단계] 메타데이터 옵션 설정
    # --------------------------------------------------------

    # --meta:
    #   → 에이전트 메타데이터 JSON 파일의 경로입니다.
    #
    # LEVEL이 basic인 경우:
    #   → 기본값 None
    #   → 메타데이터를 지정하지 않아도 됩니다.
    #
    # LEVEL이 applied 또는 advanced인 경우:
    #   → 기본값 data/agents_meta.json
    #
    # 예:
    # python main.py --meta data/agents_meta.json
    parser.add_argument(
        "--meta",
        default=(
            None if LEVEL == "basic"
            else "data/agents_meta.json"
        )
    )

    # --------------------------------------------------------
    # [4단계] 결과 저장 경로 옵션 설정
    # --------------------------------------------------------

    # --out:
    #   → 분석 결과를 저장할 폴더입니다.
    #
    # default="out":
    #   → 별도 지정이 없으면 out 폴더에 저장합니다.
    #
    # help:
    #   → --help 실행 시 표시할 설명 문구입니다.
    #
    # 원본 데이터 폴더인 data를 출력 경로로 사용하는 것은 금지합니다.
    parser.add_argument(
        "--out",
        default="out",
        help="main.py 기준 결과 폴더. data는 금지"
    )

    # --------------------------------------------------------
    # [5단계] 사용자가 입력한 명령행 옵션 읽기
    # --------------------------------------------------------

    # parse_args():
    #   → 사용자가 전달한 옵션을 분석합니다.
    #
    # 예:
    # python main.py --input data/test.csv --out results
    #
    # args.input = "data/test.csv"
    # args.out   = "results"
    #
    # 옵션을 생략하면 위에서 정의한 기본값을 사용합니다.
    args = parser.parse_args()

    # --------------------------------------------------------
    # [6단계] 상대 경로를 프로젝트 폴더 기준으로 변환
    # --------------------------------------------------------

    def here(text):
        """상대 경로는 BASE_DIR 기준으로, 절대 경로는 그대로 반환합니다.

        예:
        BASE_DIR = C:/AI_Project

        상대 경로:
        data/agent_runs.csv
            → C:/AI_Project/data/agent_runs.csv

        절대 경로:
        D:/datasets/test.csv
            → D:/datasets/test.csv
        """

        # 문자열 경로를 Path 객체로 변환합니다.
        path = Path(text)

        # is_absolute():
        #   → 입력 경로가 절대 경로인지 확인합니다.
        #
        # 절대 경로라면 그대로 반환하고,
        # 상대 경로라면 BASE_DIR과 결합합니다.
        return path if path.is_absolute() else BASE_DIR / path

    # --------------------------------------------------------
    # [7단계] 전체 분석 파이프라인 실행
    # --------------------------------------------------------

    # try:
    #   → 실행 중 오류가 발생할 수 있는 코드를 작성합니다.
    #
    # except:
    #   → 특정 오류가 발생했을 때 처리하는 부분입니다.
    #
    # 데이터 분석에서는 잘못된 데이터를 발견했을 때
    # 무조건 프로그램을 계속 실행하기보다는
    # 오류의 원인을 명확히 알려주는 것이 중요합니다.
    try:

        # run_pipeline()에 입력 경로, 출력 경로,
        # 메타데이터 경로를 전달합니다.
        #
        # here(args.input)
        #   → 입력 파일 경로
        #
        # here(args.out)
        #   → 출력 폴더 경로
        #
        # here(args.meta) if args.meta else None
        #   → 메타데이터가 지정된 경우에만 경로를 변환합니다.
        #
        # 모든 과정이 정상적으로 완료되면
        # 실행 결과 딕셔너리가 result에 저장됩니다.
        result = run_pipeline(
            here(args.input),
            here(args.out),
            here(args.meta) if args.meta else None
        )

    # --------------------------------------------------------
    # [8단계] 데이터 계약 오류 처리
    # --------------------------------------------------------

    # DataContractError:
    #   → 입력 데이터의 구조나 값이
    #     정해진 규칙을 만족하지 않을 때 발생하는 오류입니다.
    #
    # 예:
    # - 필수 열 누락
    # - 허용되지 않은 agent
    # - 잘못된 입력 데이터 구조
    #
    # as exc:
    #   → 발생한 예외 객체를 exc 변수로 받습니다.
    except DataContractError as exc:

        # 오류 메시지를 출력합니다.
        print("중단:", str(exc))

        # 어떤 데이터에 문제가 있었는지 상세 정보를 출력합니다.
        #
        # to_string(index=False):
        #   → DataFrame을 문자열 표 형태로 변환합니다.
        #   → 행 인덱스는 표시하지 않습니다.
        print(exc.issues.to_string(index=False))

        # 반환값 1은 프로그램이 정상적으로 완료되지 않았음을 나타냅니다.
        return 1

    # --------------------------------------------------------
    # [9단계] 일반적인 데이터/파일 관련 오류 처리
    # --------------------------------------------------------

    # ValueError:
    #   → 데이터 값이 유효하지 않을 때 발생합니다.
    #
    # OSError:
    #   → 파일 읽기/쓰기 등 운영체제 관련 오류입니다.
    #
    # UnicodeError:
    #   → 문자 인코딩 또는 디코딩 관련 오류입니다.
    #
    # 예:
    # - 잘못된 저장 경로
    # - 파일 접근 실패
    # - 유효하지 않은 데이터 값
    # - 문자열 인코딩 문제
    except (ValueError, OSError, UnicodeError) as exc:

        # type(exc).__name__
        #   → 발생한 오류의 클래스 이름을 가져옵니다.
        #
        # 예:
        # ValueError: 유효하지 않은 데이터
        print(f"중단: {type(exc).__name__}: {exc}")

        # 오류가 발생했으므로 1을 반환합니다.
        return 1

    # --------------------------------------------------------
    # [10단계] 정상 실행 결과 출력
    # --------------------------------------------------------

    # 모든 분석 과정이 성공하면
    # 실행 결과 딕셔너리를 JSON 문자열로 출력합니다.
    #
    # json_safe():
    #   → JSON으로 표현 가능한 값으로 변환합니다.
    #
    # json.dumps():
    #   → 파이썬 데이터를 JSON 문자열로 변환합니다.
    #
    # ensure_ascii=False:
    #   → 한글을 유니코드 이스케이프 없이 표시합니다.
    #
    # indent=2:
    #   → 들여쓰기 2칸으로 보기 좋게 출력합니다.
    print(
        json.dumps(
            json_safe(result),
            ensure_ascii=False,
            indent=2
        )
    )

    # --------------------------------------------------------
    # [11단계] 정상 종료 코드 반환
    # --------------------------------------------------------

    # 프로그램이 모든 작업을 정상적으로 완료한 경우
    # 종료 코드 0을 반환합니다.
    #
    # 일반적으로
    # 0: 정상 종료
    # 1: 오류로 인한 종료
    return 0


# ============================================================
# 5. 프로그램 시작
# ============================================================

# __name__ == "__main__":
#   → 현재 파이썬 파일을 직접 실행했는지 확인합니다.
#
# 예:
# python main.py
#
# 이 경우 main()을 실행합니다.
#
# 다른 파이썬 파일에서 이 모듈을 import할 때는
# main()이 자동 실행되지 않습니다.
#
# SystemExit():
#   → main()의 반환값을 프로그램의 종료 코드로 사용합니다.
#
# 정상 실행:
#   main() → 0 → 정상 종료
#
# 오류 발생:
#   main() → 1 → 비정상 종료
#
# 참고:
# TODO에 남아 있는 NotImplementedError는
# 현재 main()의 except 대상이 아닙니다.
# 따라서 TODO를 완성하기 전에는 해당 예외가 그대로 표시됩니다.
if __name__ == "__main__":
    raise SystemExit(main())
