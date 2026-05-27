# 00_spec - make-start-batfile

작성: Gemini 3.5 Flash (High)
일시: 2026-05-27

## 목표
- 백엔드(FastAPI) 애플리케이션인 `src/stocks-api`를 Windows 환경에서 손쉽게 실행할 수 있도록 돕는 배치 파일(`.bat`)을 작성한다.

## 기능명
- feature_name: make-start-batfile
- naming_reason: 백엔드(FastAPI)를 Windows 환경에서 시작할 수 있는 배치파일(.bat) 제작 기능이므로 제공된 이름을 유지함.

## Acceptance Criteria
- `src/stocks-api/start.bat` 배치 파일이 신규 생성되어야 한다.
- 배치 파일 실행 시 한글 깨짐이 없도록 UTF-8 코드페이지(`chcp 65001`)를 적용한다.
- 배치 파일 실행 시 가상 환경(`.venv` 또는 `venv`)이 존재하는지 탐색하고, 존재하면 해당 가상 환경을 활성화(`Scripts\activate.bat`)하여 구동한다.
  - 가상 환경 탐색 경로: `src/stocks-api/.venv`, `src/stocks-api/venv`, `src/.venv`, 프로젝트 루트(`.venv`, `venv`) 등 다각도로 탐색하여 유연성을 제공한다.
- 가상 환경이 존재하지 않으면 시스템 전역 `python` 명령어를 사용하여 실행한다.
- 백엔드 서버는 `python main.py`를 호출하여 실행한다.
- 배치 파일 실행 중 에러가 발생하여 비정상 종료 시, 콘솔 창이 바로 닫히지 않고 에러 메시지를 확인할 수 있도록 `pause` 처리를 포함한다.

## 제외 범위
- Git 명령어 직접 실행 (`git commit`, `git checkout` 등)은 로컬 하네스가 전담하므로 범위에서 제외된다.
- 프론트엔드(`stocks-dashboard`)용 구동 배치파일 및 기타 배포용 스크립트 작성은 포함하지 않는다.

## 기존 코드 영향
- 관련 파일:
  - [NEW] [start.bat](file:///D:/test/vibe-coding-toolkit/vibe-coding-toolkit/src/stocks-api/start.bat)
- 재사용할 기존 모듈/패턴:
  - `src/stocks-api/main.py` 내의 uvicorn 실행 로직을 이용하므로 `python main.py`를 호출한다.
- 충돌 가능성이 있는 부분:
  - 없음 (신규 생성하는 독립적인 배치 파일이므로 기존 백엔드/프론트엔드 코드에 영향을 주지 않는다)

## 구현 계획
- `src/stocks-api/start.bat` [NEW]:
  - `@echo off`, `chcp 65001` 설정.
  - 가상환경 활성화 체크 로직 작성:
    - 배치파일 위치(`%~dp0`) 기준으로 `.venv` 혹은 `venv`가 존재하는지 확인.
    - 부모 디렉터리(`%~dp0..`) 또는 프로젝트 루트(`%~dp0..\..`)에 `.venv` 혹은 `venv`가 존재하는지 확인.
    - 매칭되는 가상 환경이 있으면 `Scripts\activate.bat` 실행.
  - `python main.py` 실행.
  - 실행 실패 시 `pause`를 통해 화면 유지.

## 데이터 / 제어 흐름
- 사용자가 `src/stocks-api/start.bat` 실행 -> 가상환경 자동 감지 및 활성화 -> `python main.py` 실행 -> `uvicorn`에 의해 FastAPI 백엔드 구동 -> 에러 발생 시 `pause`로 대기.

## 검증 계획
- 실행할 테스트/빌드 명령:
  - 배치파일 직접 실행 테스트 (`cmd.exe`에서 `src\stocks-api\start.bat` 실행)
- 정상 경로:
  - 가상환경 활성화 상태에서 정상 구동 및 FastAPI 서버 `http://localhost:8000/health` 또는 설정된 포트로 접근 성공.
- 오류/엣지 경로:
  - 파이썬 미설치 환경 또는 패키지 미설치 환경에서 에러 메시지가 출력되고 `pause` 상태로 대기하여 사용자가 에러를 확인 가능한지 검증.

## 위험도 및 파이프라인 판단
- risk_level: low
- fast_pipeline_allowed: true
- full_pipeline_recommended: false
- 판단 근거: 백엔드를 구동하기 위한 단순 배치파일 신규 생성 건이며, 기존 비즈니스 로직 수정이나 파괴적인 변경이 전혀 없으므로 low 위험도로 분류하고 fast 파이프라인으로 처리가 충분히 가능함.

## 단계 결과
- status: PASS
- next_stage: 01_develop
- human_gate_required: false
- blocking_reason: 없음
- risk_level: low
- produced_files:
  - .ai/features/make-start-batfile/00_spec.md
- changed_files:
- commit_created: false
- commit_message:
- model_mismatch: false
- actual_model: Gemini 3.5 Flash (High)
