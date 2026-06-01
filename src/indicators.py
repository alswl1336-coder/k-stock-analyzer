from __future__ import annotations

import pandas as pd


REQUIRED_OHLCV_COLUMNS = {"Open", "High", "Low", "Close", "Volume"}


def _validate_columns(df: pd.DataFrame, columns: set[str] | None = None) -> None:
    required = columns or REQUIRED_OHLCV_COLUMNS
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"필수 컬럼이 없습니다: {', '.join(missing)}")


def add_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    _validate_columns(df, {"Close"})
    result = df.copy()
    for window in (5, 20, 60, 120):
        result[f"MA{window}"] = result["Close"].rolling(window=window).mean()
    return result


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    _validate_columns(df, {"Close"})
    if period <= 0:
        raise ValueError("period는 1 이상이어야 합니다.")

    result = df.copy()
    delta = result["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    result[f"RSI{period}"] = 100 - (100 / (1 + rs))
    result.loc[(avg_loss == 0) & (avg_gain > 0), f"RSI{period}"] = 100
    result.loc[(avg_loss == 0) & (avg_gain == 0), f"RSI{period}"] = 50
    return result


def add_macd(df: pd.DataFrame) -> pd.DataFrame:
    _validate_columns(df, {"Close"})
    result = df.copy()
    ema12 = result["Close"].ewm(span=12, adjust=False).mean()
    ema26 = result["Close"].ewm(span=26, adjust=False).mean()
    result["MACD"] = ema12 - ema26
    result["MACD_SIGNAL"] = result["MACD"].ewm(span=9, adjust=False).mean()
    result["MACD_HIST"] = result["MACD"] - result["MACD_SIGNAL"]
    return result


def add_bollinger_bands(
    df: pd.DataFrame,
    period: int = 20,
    std: float = 2,
) -> pd.DataFrame:
    _validate_columns(df, {"Close"})
    if period <= 0:
        raise ValueError("period는 1 이상이어야 합니다.")
    if std <= 0:
        raise ValueError("std는 0보다 커야 합니다.")

    result = df.copy()
    middle = result["Close"].rolling(window=period).mean()
    deviation = result["Close"].rolling(window=period).std()
    result["BB_MIDDLE"] = middle
    result["BB_UPPER"] = middle + (deviation * std)
    result["BB_LOWER"] = middle - (deviation * std)
    return result


def add_returns(df: pd.DataFrame) -> pd.DataFrame:
    _validate_columns(df, {"Close"})
    result = df.copy()
    result["RETURN_1D"] = result["Close"].pct_change() * 100
    result["RETURN_5D"] = result["Close"].pct_change(periods=5) * 100
    result["RETURN_20D"] = result["Close"].pct_change(periods=20) * 100
    result["HIGH_52W"] = result["Close"].rolling(window=252, min_periods=1).max()
    result["LOW_52W"] = result["Close"].rolling(window=252, min_periods=1).min()
    return result


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    _validate_columns(df)
    result = add_moving_averages(df)
    result = add_rsi(result)
    result = add_macd(result)
    result = add_bollinger_bands(result)
    result = add_returns(result)
    result["VOLUME_MA20"] = result["Volume"].rolling(window=20).mean()
    result["VOLUME_RATIO"] = result["Volume"] / result["VOLUME_MA20"]
    return result
