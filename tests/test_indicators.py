import pandas as pd

from src.indicators import (
    add_all_indicators,
    add_bollinger_bands,
    add_macd,
    add_moving_averages,
    add_returns,
    add_rsi,
)


def sample_df(rows=260):
    close = pd.Series(range(1000, 1000 + rows), dtype="float64")
    return pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=rows),
            "Open": close - 5,
            "High": close + 10,
            "Low": close - 10,
            "Close": close,
            "Volume": range(10000, 10000 + rows),
        }
    )


def test_add_moving_averages_creates_columns():
    result = add_moving_averages(sample_df())
    assert {"MA5", "MA20", "MA60", "MA120"}.issubset(result.columns)


def test_add_rsi_creates_column():
    result = add_rsi(sample_df())
    assert "RSI14" in result.columns
    assert result["RSI14"].notna().any()


def test_add_macd_creates_columns():
    result = add_macd(sample_df())
    assert {"MACD", "MACD_SIGNAL", "MACD_HIST"}.issubset(result.columns)


def test_add_bollinger_bands_creates_columns():
    result = add_bollinger_bands(sample_df())
    assert {"BB_MIDDLE", "BB_UPPER", "BB_LOWER"}.issubset(result.columns)


def test_add_returns_creates_columns():
    result = add_returns(sample_df())
    assert {"RETURN_1D", "RETURN_5D", "RETURN_20D", "HIGH_52W", "LOW_52W"}.issubset(result.columns)


def test_indicator_functions_do_not_mutate_input_dataframe():
    original = sample_df()
    before_columns = list(original.columns)
    before_values = original.copy(deep=True)

    add_all_indicators(original)

    assert list(original.columns) == before_columns
    pd.testing.assert_frame_equal(original, before_values)
