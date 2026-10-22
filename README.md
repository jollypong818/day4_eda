# day4_eda · 기본필수

PPT 16~17쪽의 **수업용 합성 Multi Agent 실행 로그 13행**을 정제하고, 수치·그림·저장 결과를 검증하는 프로젝트입니다.

## 환경과 실행
현재 `day4_eda`를 작업 폴더로 열고 준비된 Python 3.13 가상환경을 선택합니다.
```text
python -m pip install -r requirements.txt
python main.py
python -m unittest discover -s tests -v
```
다른 작업 폴더에서는 `main.py`의 절대 경로로 실행할 수 있습니다. 상대 입력·출력 경로는 `main.py`의 위치를 기준으로 해석합니다. 검수 버전은 Python 3.13.5·NumPy 2.3.5·pandas 2.2.3·Matplotlib 3.10.8입니다.

## 생성되는 결과
기본필수는 `out/clean_runs.csv`, `out/summary.json`, `out/charts/latency_by_agent.png`, `out/charts/latency_hist.png`를 만듭니다. 응용은 산점도 `tokens_latency.png`, 상태별 `pivot.csv`, 역할 결합 `joined_runs.csv`를 추가합니다. 심화는 `daily.csv`와 `daily_latency.png`도 추가합니다.

`quality.json`, `facts.json`, `roundtrip_check.json`, `chart_audit.json`은 계산과 검증 근거입니다. **`reports/eda_report.md`는 직접 작성하는 문서이며 프로그램이 덮어쓰지 않습니다.** 실행 전에 수정한 결과가 있다면 별도로 보관하세요. 성공한 재실행은 이전 `out` 폴더를 새 결과로 교체합니다.

## 데이터 정책과 실패 처리
공유가 허용된 합성 데이터만 사용하며 메타데이터의 단가는 가상 단위입니다. 완전 중복만 제거하고 ID 충돌·미등록 역할·알 수 없는 상태는 진단 후 중단합니다. 음수·무한대·숫자로 변환할 수 없는 측정은 결측으로, 0은 유효값으로 처리합니다. 날짜 미상은 별도로 집계합니다. 심화는 정수가 아닌 토큰 수도 결측으로 처리합니다.

헤더만 있는 CSV와 완전히 빈 파일은 각각 원인을 안내하며, 빈 분석을 성공으로 처리하지 않습니다. 원본 `data`와 결과 `out`은 분리합니다. 임시 폴더에서 생성·검증을 완료한 뒤에만 결과를 교체하므로 읽기·정제·검증 실패가 기존 결과를 지우지 않습니다. 이 방식이 정전·동시 작성까지 보장하는 데이터베이스 트랜잭션은 아닙니다.

## 심화 확장 입력
아래 명령은 **심화 프로젝트에서만** 실행합니다.
```text
python main.py --input data/fixtures/extended_runs.csv --meta data/fixtures/extended_meta.json --out out_extended
```
확장 입력은 19행이며 정제 후 18행·4개 역할입니다. 원본의 13→12행 기준을 함수 내부에 하드코딩하지 마세요. `out_extended`는 기본 `out`과 구분하여 저장합니다.

## 개인 기여와 제출
자신이 수행한 작업, 실제 실행환경, 테스트 결과, 동료 리뷰를 `reports`에 기록합니다. 현재 README는 제공된 초안입니다. 본인의 실행 방법과 관찰을 보완한 뒤 Git에 기록하세요. 실습 06에서 시작한 저장소를 그대로 유지하고 실습 08에서 이 폴더를 최종 검증합니다.
