# K-Stock Analyzer

개인용 한국 주식/국내 ETF 분석 Streamlit 웹앱 MVP입니다. KOSPI/KOSDAQ 종목과 국내 상장 ETF를 검색하고, 가격 차트, 기술적 지표, 외국인/기관 수급, 공매도 현황, ETF 구조 지표, 조건검색, 관심종목을 확인할 수 있습니다.

이 앱은 투자 추천, 매수/매도 추천, 자동매매, 주문 기능을 제공하지 않습니다. 모든 결과는 사용자가 직접 판단하기 위한 분석 보조 지표입니다.

## 기능

- KOSPI/KOSDAQ 종목 검색 및 분석
- 국내 ETF 검색 및 분석
- 캔들차트, 이동평균선, 거래량, RSI, MACD, 볼린저밴드
- 외국인/기관 순매매, 누적 순매매, 수급 강도
- 공매도 현황, 공매도 비중, 공매도 잔고, 공매도 추세 분석
- ETF 현재가, NAV, 괴리율, 추적오차율, PDF 구성종목
- 일반주식/ETF 조건검색
- 로컬 JSON 기반 관심종목 추가, 삭제, 메모 수정
- 네이버 뉴스 API, OpenDART, pykrx 보조 데이터 연동

## 설치

Python 3.11 이상을 권장합니다.

```bash
pip install -r requirements.txt
cp .env.example .env
```

`.env`에는 실제 API 키를 입력합니다. `.env`는 GitHub에 올리면 안 됩니다.

```text
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=
DART_API_KEY=
KRX_ID=
KRX_PW=
APP_ENV=local
DEBUG_MODE=false
```

Streamlit Cloud에서는 `runtime.txt`로 Python 3.11을 사용하도록 지정합니다. `pykrx`가 `pkg_resources`를 사용하므로 `requirements.txt`에 `setuptools`를 포함했습니다.

앱은 설정값을 다음 순서로 읽습니다.

1. Streamlit `st.secrets`
2. 환경변수
3. 로컬 `.env`
4. 기본값

민감값은 화면에 직접 출력하지 않고, 설정 여부만 `true/false`로 표시합니다.

## 실행

로컬 실행:

```bash
streamlit run app.py
```

로컬 네트워크 접속 허용:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

클라우드 서버 실행:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port ${PORT:-8501}
```

Windows PowerShell 예시:

```powershell
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

## Streamlit Community Cloud

1. GitHub 저장소를 연결합니다.
2. Main file path를 `app.py`로 설정합니다.
3. App secrets에 아래 형식으로 값을 등록합니다.
4. Deploy를 실행합니다.

```toml
NAVER_CLIENT_ID = "your_naver_client_id"
NAVER_CLIENT_SECRET = "your_naver_client_secret"
DART_API_KEY = "your_dart_api_key"
KRX_ID = "your_krx_id"
KRX_PW = "your_krx_password"
APP_ENV = "production"
DEBUG_MODE = false
```

실제 `.streamlit/secrets.toml`은 GitHub에 올리지 마세요. 예시는 `.streamlit/secrets.toml.example`만 커밋합니다.

## Render

Render Dashboard에서 GitHub 저장소를 연결하고 Environment Variables에 API 키를 등록합니다. `render.yaml`에는 실제 비밀값을 넣지 않습니다.

수동 설정 시:

```bash
pip install -r requirements.txt
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT
```

## Docker

이미지 빌드:

```bash
docker build -t k-stock-analyzer .
```

로컬 `.env`를 사용해 실행:

```bash
docker run -p 8501:8501 --env-file .env k-stock-analyzer
```

서버 환경변수로 실행:

```bash
docker run -p 8501:8501 -e APP_ENV=production k-stock-analyzer
```

## Railway, Fly.io, 개인 VPS

Railway/Fly.io에서는 `PORT` 환경변수를 플랫폼이 주입하므로 다음 명령을 start command로 사용합니다.

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT
```

개인 VPS 예시:

```bash
git clone <repo-url>
cd korea-stock-dashboard
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

## 테스트

```bash
pytest
```

## 폴더 구조

```text
korea-stock-dashboard/
  app.py
  requirements.txt
  README.md
  Dockerfile
  render.yaml
  .env.example
  .streamlit/
    config.toml
    secrets.toml.example
  src/
    config.py
    charts.py
    data_loader.py
    etf_analysis.py
    etf_loader.py
    news_loader.py
    dart_loader.py
    indicators.py
    investor_flow.py
    screener.py
    shorting.py
    watchlist.py
  tests/
```

## 주의사항

- 조건검색 결과는 조건 충족 종목 또는 분석 후보이며 추천이 아닙니다.
- FinanceDataReader와 pykrx 데이터는 실시간 시세가 아닙니다.
- pykrx/KRX 데이터 제공 상태에 따라 일부 가격, NAV, 수급, 공매도, PDF 데이터가 비어 있을 수 있습니다.
- 공매도 증가가 반드시 주가 하락을 의미하지 않으며, 공매도 감소가 반드시 주가 상승을 의미하지 않습니다.
- OpenDART, 한국투자증권 API 연동은 후속 확장 계획으로 고려합니다.
