"""Single Exponential Smoothing and matching-horizon evaluation."""

import math
from decimal import Decimal, ROUND_CEILING


ALPHA_CANDIDATES = tuple(Decimal(value) / Decimal(100) for value in range(1, 101))
MIN_BACKTEST_TRAINING_DAYS = 7
MIN_ALPHA_TUNING_DAYS = 7
MIN_BUFFER_BACKTEST_WINDOWS = 7
UNDERFORECAST_BUFFER_PERCENTILE = Decimal('0.75')
DEFAULT_ALPHA = Decimal('0.30')


def proyeksikan_permintaan(penjualan_harian, jumlah_hari):
    """Keep the average-based projection for existing callers."""
    if (not isinstance(jumlah_hari, int) or isinstance(jumlah_hari, bool)
            or jumlah_hari <= 0):
        raise ValueError('jumlah_hari harus berupa bilangan bulat positif.')
    _validate_series(penjualan_harian)
    average = Decimal(sum(penjualan_harian)) / Decimal(len(penjualan_harian))
    projected = average * jumlah_hari
    return average, int(projected.to_integral_value(rounding=ROUND_CEILING))


def _validate_series(penjualan_harian):
    if not penjualan_harian:
        raise ValueError('Minimal satu hari histori penjualan diperlukan.')
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0
           for value in penjualan_harian):
        raise ValueError('Penjualan harian harus berupa bilangan bulat tidak negatif.')


def _ses_step(level, actual, alpha):
    return alpha * Decimal(actual) + (Decimal(1) - alpha) * level


def _fit_level(series, alpha):
    level = Decimal(series[0])
    for actual in series[1:]:
        level = _ses_step(level, actual, alpha)
    return level


def _mape_percent(errors):
    valid = [(actual, forecast) for actual, forecast in errors if actual > 0]
    if not valid:
        return None, 0
    value = sum(
        (abs(Decimal(actual) - forecast) / Decimal(actual) for actual, forecast in valid),
        Decimal(0),
    ) / Decimal(len(valid)) * Decimal(100)
    return value, len(valid)


def _adaptive_underforecast_buffer(error_pairs, window_count):
    if window_count < MIN_BUFFER_BACKTEST_WINDOWS:
        return 0, 'histori_backtest_terbatas'
    recent_errors = error_pairs[-MIN_BUFFER_BACKTEST_WINDOWS:]
    underforecast_units = sorted(
        max(Decimal(0), Decimal(actual) - forecast)
        for actual, forecast in recent_errors
    )
    if not underforecast_units:
        return 0, 'galat_backtest_tidak_tersedia'
    rank = int(
        (UNDERFORECAST_BUFFER_PERCENTILE * len(underforecast_units))
        .to_integral_value(rounding=ROUND_CEILING)
    )
    selected_error = underforecast_units[max(0, rank - 1)]
    buffer_units = int(selected_error.to_integral_value(rounding=ROUND_CEILING))
    return buffer_units, 'berbasis_persentil_galat_75'


def _select_alpha(training):
    if len(training) < MIN_ALPHA_TUNING_DAYS or not any(training):
        return DEFAULT_ALPHA, (
            'default_histori_terbatas' if len(training) < MIN_ALPHA_TUNING_DAYS
            else 'default_data_latih_nol'
        )

    candidates = []
    for candidate in ALPHA_CANDIDATES:
        level = Decimal(training[0])
        errors = []
        for actual in training[1:]:
            errors.append((actual, level))
            level = _ses_step(level, actual, candidate)
        score, _ = _mape_percent(errors)
        if score is not None:
            candidates.append((score, candidate))

    if not candidates:
        return DEFAULT_ALPHA, 'default_mape_tidak_tersedia'
    return min(candidates, key=lambda pair: (pair[0], pair[1]))[1], 'terpilih_mape_data_latih'


def _rolling_horizon_backtest(series, horizon, max_windows=None):
    mape_errors = []
    error_pairs = []
    zero_actual_windows = 0
    forecast_windows = 0
    last_origin = len(series) - horizon

    origins = list(range(MIN_BACKTEST_TRAINING_DAYS, last_origin + 1))
    if max_windows is not None:
        origins = origins[-max_windows:]
    for origin in origins:
        training = series[:origin]
        alpha, _ = _select_alpha(training)
        level = _fit_level(training, alpha)
        actual_total = sum(series[origin:origin + horizon])
        predicted_total = level * horizon
        forecast_windows += 1
        error_pairs.append((actual_total, predicted_total))
        if actual_total > 0:
            mape_errors.append((actual_total, predicted_total))
        else:
            zero_actual_windows += 1

    mape, valid_windows = _mape_percent(mape_errors)
    mae = None
    rmse = None
    if error_pairs:
        mae = sum(
            abs(Decimal(actual) - forecast) for actual, forecast in error_pairs
        ) / Decimal(len(error_pairs))
        mse = sum(
            (Decimal(actual) - forecast) ** 2 for actual, forecast in error_pairs
        ) / Decimal(len(error_pairs))
        rmse = Decimal(str(round(math.sqrt(float(mse)), 4)))

    buffer_units, buffer_status = _adaptive_underforecast_buffer(
        error_pairs, forecast_windows
    )
    return mape, mae, rmse, forecast_windows, valid_windows, zero_actual_windows, buffer_units, buffer_status


def peramalkan_ses(penjualan_harian, jumlah_hari, *, max_backtest_windows=None):
    """Forecast with SES and evaluate matching-horizon rolling-origin windows."""
    _validate_series(penjualan_harian)
    if (not isinstance(jumlah_hari, int) or isinstance(jumlah_hari, bool)
            or jumlah_hari <= 0):
        raise ValueError('jumlah_hari harus berupa bilangan bulat positif.')
    if (max_backtest_windows is not None
            and (not isinstance(max_backtest_windows, int)
                 or isinstance(max_backtest_windows, bool)
                 or max_backtest_windows <= 0)):
        raise ValueError('max_backtest_windows harus berupa bilangan bulat positif.')

    alpha, alpha_status = _select_alpha(penjualan_harian)
    level = _fit_level(penjualan_harian, alpha)
    projected = int(
        (level * jumlah_hari).to_integral_value(rounding=ROUND_CEILING)
    )
    (mape, mae, rmse, forecast_windows, valid_windows, zero_actual_windows,
     buffer_units, buffer_status) = _rolling_horizon_backtest(
        penjualan_harian, jumlah_hari, max_backtest_windows
    )
    return {
        'alpha': alpha,
        'level_terakhir': level,
        'prediksi_harian': level,
        'prediksi_periode': projected,
        'mape_persen': mape,
        'mae': mae,
        'rmse': rmse,
        'jumlah_data_latih': len(penjualan_harian),
        'jumlah_data_uji': forecast_windows,
        'jumlah_data_uji_mape': valid_windows,
        'jumlah_data_uji_nol': zero_actual_windows,
        'buffer_adaptif': buffer_units,
        'status_buffer': buffer_status,
        'status_alpha': alpha_status,
    }
