import pandas as pd

from src import etf_loader
from src.etf_loader import load_etf_portfolio, make_recent_date_candidates, normalize_etf_portfolio, to_yyyymmdd


def test_to_yyyymmdd_and_recent_candidates():
    assert to_yyyymmdd("2024-01-02") == "20240102"
    assert make_recent_date_candidates("2024-01-03", lookback_days=3) == ["20240103", "20240102", "20240101"]


def test_normalize_pykrx_portfolio_shape(monkeypatch):
    monkeypatch.setattr(etf_loader, "lookup_component_name", lambda code: {"005930": "삼성전자"}.get(code, code))
    raw = pd.DataFrame(
        {"계약수": [10, 20], "금액": [1000, 3000], "비중": [25.0, 75.0]},
        index=["005930", "KRD010010001"],
    )

    result = normalize_etf_portfolio(raw, "20240102")

    assert {"ComponentCode", "ContractCount", "Amount", "Weight"}.issubset(result.columns)
    assert result.loc[0, "ComponentName"] == "삼성전자"
    assert result.loc[1, "ComponentName"] == "원화현금"
    assert result.loc[0, "IsDomesticStock"]
    assert result.loc[1, "BaseDate"] == "20240102"


def test_weight_is_calculated_from_amount_when_zero(monkeypatch):
    monkeypatch.setattr(etf_loader, "lookup_component_name", lambda code: code)
    raw = pd.DataFrame(
        {"계약수": [1, 1], "금액": [1000, 3000], "비중": [0, 0]},
        index=["ABC.US", "FUT2024"],
    )

    result = normalize_etf_portfolio(raw, "20240102")

    assert round(result.loc[0, "Weight"], 2) == 25.0
    assert round(result.loc[1, "Weight"], 2) == 75.0
    assert not result.loc[0, "IsDomesticStock"]


def test_non_standard_code_does_not_raise(monkeypatch):
    monkeypatch.setattr(etf_loader, "lookup_component_name", lambda code: code)
    raw = pd.DataFrame({"계약수": [1], "금액": [0], "비중": [0]}, index=["SWAP-NASDAQ"])

    result = normalize_etf_portfolio(raw, "20240102")

    assert result.loc[0, "ComponentName"] == "SWAP-NASDAQ"
    assert result.loc[0, "Weight"] == 0


def test_normalize_does_not_mutate_input(monkeypatch):
    monkeypatch.setattr(etf_loader, "lookup_component_name", lambda code: code)
    raw = pd.DataFrame({"계약수": [1], "금액": [1000], "비중": [100]}, index=["005930"])
    before = raw.copy(deep=True)

    normalize_etf_portfolio(raw, "20240102")

    pd.testing.assert_frame_equal(raw, before)


def test_load_portfolio_skips_pykrx_when_krx_credentials_missing(monkeypatch):
    monkeypatch.setattr(
        etf_loader,
        "get_krx_env_status",
        lambda: {
            "env_path": "test/.env",
            "env_exists": False,
            "has_krx_id": False,
            "has_krx_pw": False,
        },
    )

    def fail_import():
        raise AssertionError("pykrx should not be imported without KRX credentials")

    monkeypatch.setattr(etf_loader, "_import_pykrx_stock", fail_import)
    load_etf_portfolio.clear()

    result = load_etf_portfolio("122630", "2024-01-02", 2)
    debug = result.attrs["debug"]

    assert result.empty
    assert debug["disabled_reason"] == "missing_krx_credentials"
    assert debug["exception_type"] == "MissingKrxCredentials"
