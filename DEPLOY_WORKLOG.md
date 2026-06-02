# Deploy Worklog

## 작업 원칙

- 원본 폴더: `C:\Users\kkk\Downloads\누나\코덱스\PDF_이미지뷰어\korea-stock-dashboard`
- 배포 작업본 폴더: `C:\Users\kkk\Downloads\누나\코덱스\PDF_이미지뷰어\korea-stock-dashboard-deploy`
- 원본 폴더는 백업/원본으로 보존하고, 배포 관련 수정은 작업본 폴더에서만 진행합니다.

## 복사 요약

원본 `korea-stock-dashboard`의 파일과 하위 폴더를 `korea-stock-dashboard-deploy`로 복사했습니다.

복사된 주요 항목:

- `app.py`
- `src/`
- `tests/`
- `data/`
- `.streamlit/`
- `requirements.txt`
- `README.md`
- `Dockerfile`
- `render.yaml`
- `.env.example`
- `.gitignore`

로컬 `.env` 파일은 작업본에도 복사되어 있지만 `.gitignore`에 포함되어 있으므로 GitHub에 올리면 안 됩니다.

## 배포 작업본 변경 사항

- `src/config.py`에서 `data/` 폴더를 자동 생성하도록 보완했습니다.
- `app.py` 사이드바에 `배포 상태 / 시스템 체크` expander를 추가했습니다.
- 시스템 체크는 API 키 값을 표시하지 않고 설정 여부만 표시합니다.
- 외부 접속 보호를 위해 `APP_PASSWORD` 기반 비밀번호 화면을 추가했습니다.
- PC용 전체 화면인 `app.py`는 유지하고, 모바일 전용 핵심 화면은 별도 `app_mobile.py`로 추가했습니다.

## 원본과 작업본 차이

- 원본은 그대로 보존합니다.
- 작업본은 배포 검증과 클라우드 실행을 위한 설정 파일 및 배포 상태 점검 UI를 포함합니다.
- 작업본의 `.env`는 로컬 실행용이며, 배포 환경에서는 Streamlit secrets 또는 환경변수를 사용합니다.
- 모바일 접속용으로는 `streamlit run app_mobile.py --server.address 0.0.0.0 --server.port 8503`을 사용할 수 있습니다.
