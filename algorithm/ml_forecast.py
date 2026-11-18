"""Conservative Random Forest candidate for short-horizon demand forecasting.

The estimator is selected only when a chronological, non-overlapping weekly
backtest has enough observations and beats SES on the same validation windows.
Otherwise callers should use SES and present the fallback reason.
"""

from decimal import Decimal, ROUND_CEILING
import math

from algorithm.ses import (
    MIN_BUFFER_BACKTEST_WINDOWS,
    UNDERFORECAST_BUFFER_PERCENTILE,
    _fit_level,
    _select_alpha,
)


FEATURE_LOOKBACK_DAYS = 28
MIN_ML_HISTORY_DAYS = 77
MIN_ML_BACKTEST_WINDOWS = 3
MAX_ML_BACKTEST_WINDOWS = 7


def _features(history):
    recent = history[-FEATURE_LOOKBACK_DAYS:]
    if len(recent) < FEATURE_LOOKBACK_DAYS:
        raise ValueError('Fitur ML memerlukan minimal 28 hari histori.')
    return [
        *[float(recent[-offset]) for offset in (1, 2, 3, 7, 14, 21, 28)],
        sum(recent[-7:]) / 7,
        sum(recent[-14:]) / 14,
        sum(recent[-28:]) / 28,
        sum(value == 0 for value in recent[-28:]),
    ]


def _training_data(series):
    features, targets = [], []
    for target_index in range(FEATURE_LOOKBACK_DAYS, len(series)):
        features.append(_features(series[:target_index]))
        targets.append(float(series[target_index]))
    return features, targets


def _new_model():
    from sklearn.ensemble import RandomForestRegressor

    return RandomForestRegressor(
        n_estimators=40,
        max_depth=8,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=1,
    )


def _forecast_daily(model, history, horizon):
    values = list(history)
    forecasts = []
    for _ in range(horizon):
        prediction = max(0.0, float(model.predict([_features(values)])[0]))
        forecasts.append(prediction)
        values.append(prediction)
    return forecasts


def _mape_and_mae(errors):
    positive = [(actual, predicted) for actual, predicted in errors if actual > 0]
    mape = None
    if positive:
        mape = sum(
            (abs(Decimal(actual) - Decimal(str(predicted))) / Decimal(actual)
             for actual, predicted in positive),
            Decimal(0),
        ) / Decimal(len(positive)) * Decimal(100)
    mae = (
        sum(abs(Decimal(actual) - Decimal(str(predicted))) for actual, predicted in errors)
        / Decimal(len(errors)) if errors else None
    )
    rmse = None
    if errors:
        mse = sum(
            (Decimal(actual) - Decimal(str(predicted))) ** 2 for actual, predicted in errors
        ) / Decimal(len(errors))
        rmse = Decimal(str(round(math.sqrt(float(mse)), 4)))
    return mape, mae, rmse, len(positive)


def _buffer(error_pairs):
    if len(error_pairs) < MIN_BUFFER_BACKTEST_WINDOWS:
        return 0, 'jendela_ml_terbatas'
    values = sorted(
        max(Decimal(0), Decimal(actual) - Decimal(str(predicted)))
        for actual, predicted in error_pairs[-MIN_BUFFER_BACKTEST_WINDOWS:]
    )
    rank = int(
        (UNDERFORECAST_BUFFER_PERCENTILE * len(values))
        .to_integral_value(rounding=ROUND_CEILING)
    )
    return int(values[max(0, rank - 1)].to_integral_value(rounding=ROUND_CEILING)), 'buffer_ml_tersedia'


def _weekly_origins(series_length, horizon):
    origins = list(range(56, series_length - horizon + 1, horizon))
    return origins[-MAX_ML_BACKTEST_WINDOWS:]


def peramalkan_random_forest(penjualan_harian, jumlah_hari, ses_reference=None):
    """Return validated ML output or a reason to fall back to SES.

    A weekly model comparison is made on the same chronological folds as SES.
    No shuffled split is used because sales are time ordered.
    """
    if (not isinstance(jumlah_hari, int) or isinstance(jumlah_hari, bool)
            or jumlah_hari <= 0):
        raise ValueError('jumlah_hari harus berupa bilangan bulat positif.')
    if not penjualan_harian or any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in penjualan_harian
    ):
        raise ValueError('Penjualan harian harus berupa bilangan bulat tidak negatif.')
    if len(penjualan_harian) < MIN_ML_HISTORY_DAYS:
        return {
            'tersedia': False,
            'status': 'histori_ml_terbatas',
            'alasan': f'ML memerlukan minimal {MIN_ML_HISTORY_DAYS} hari histori harian.',
            'mape_persen': None,
            'jumlah_data_uji': 0,
            'jumlah_data_uji_mape': 0,
            'jumlah_data_uji_nol': 0,
            'buffer_adaptif': 0,
            'status_buffer': 'jendela_ml_terbatas',
            'offset_uji_awal': None,
        }

    origins = _weekly_origins(len(penjualan_harian), jumlah_hari)
    if len(origins) < MIN_ML_BACKTEST_WINDOWS:
        return {
            'tersedia': False,
            'status': 'backtest_ml_terbatas',
            'alasan': f'ML memerlukan minimal {MIN_ML_BACKTEST_WINDOWS} jendela uji kronologis.',
            'mape_persen': None,
            'jumlah_data_uji': len(origins),
            'jumlah_data_uji_mape': 0,
            'jumlah_data_uji_nol': 0,
            'buffer_adaptif': 0,
            'status_buffer': 'jendela_ml_terbatas',
            'offset_uji_awal': None,
        }

    ml_errors, ses_errors = [], []
    for origin in origins:
        training = penjualan_harian[:origin]
        features, targets = _training_data(training)
        if len(features) < MIN_ML_BACKTEST_WINDOWS:
            continue
        model = _new_model()
        model.fit(features, targets)
        predicted_total = sum(_forecast_daily(model, training, jumlah_hari))
        actual_total = sum(penjualan_harian[origin:origin + jumlah_hari])
        ml_errors.append((actual_total, predicted_total))

        alpha, _ = _select_alpha(training)
        ses_level = _fit_level(training, alpha)
        ses_errors.append((actual_total, ses_level * jumlah_hari))

    ml_mape, ml_mae, ml_rmse, valid_windows = _mape_and_mae(ml_errors)
    ses_mape, ses_mae, ses_rmse, _ = _mape_and_mae(ses_errors)
    zero_windows = len(ml_errors) - valid_windows
    if len(ml_errors) < MIN_ML_BACKTEST_WINDOWS or valid_windows < MIN_ML_BACKTEST_WINDOWS:
        return {
            'tersedia': False,
            'status': 'aktual_positif_ml_terbatas',
            'alasan': 'ML memerlukan sedikitnya tiga jendela uji dengan aktual positif untuk evaluasi MAPE.',
            'mape_persen': ml_mape,
            'mape_ses_persen': ses_mape,
            'mae': ml_mae,
            'mae_ses': ses_mae,
            'rmse': ml_rmse,
            'rmse_ses': ses_rmse,
            'jumlah_data_uji': len(ml_errors),
            'jumlah_data_uji_mape': valid_windows,
            'jumlah_data_uji_nol': zero_windows,
            'buffer_adaptif': 0,
            'status_buffer': 'jendela_ml_terbatas',
            'offset_uji_awal': origins[0] if origins else None,
        }

    # Prefer SES on a tie. If MAPE is unavailable for both, compare MAE.
    beats_ses = (
        ml_mape < ses_mape if ml_mape is not None and ses_mape is not None
        else ml_mae is not None and ses_mae is not None and ml_mae < ses_mae
    )
    if not beats_ses:
        return {
            'tersedia': False,
            'status': 'ses_lebih_baik',
            'alasan': 'Validasi waktu tidak menunjukkan MAPE/MAE Random Forest lebih baik daripada SES.',
            'mape_persen': ml_mape,
            'mape_ses_persen': ses_mape,
            'mae': ml_mae,
            'mae_ses': ses_mae,
            'rmse': ml_rmse,
            'rmse_ses': ses_rmse,
            'jumlah_data_uji': len(ml_errors),
            'jumlah_data_uji_mape': valid_windows,
            'jumlah_data_uji_nol': zero_windows,
            'buffer_adaptif': 0,
            'status_buffer': 'jendela_ml_terbatas',
            'offset_uji_awal': origins[0] if origins else None,
        }

    features, targets = _training_data(penjualan_harian)
    model = _new_model()
    model.fit(features, targets)
    daily = _forecast_daily(model, penjualan_harian, jumlah_hari)
    predicted_total = int(Decimal(str(sum(daily))).to_integral_value(rounding=ROUND_CEILING))
    buffer_units, buffer_status = _buffer(ml_errors)
    return {
        'tersedia': True,
        'status': 'random_forest_mengungguli_ses',
        'alasan': 'Random Forest dipilih karena MAPE/MAE lebih rendah pada jendela validasi waktu yang sama.',
        'prediksi_harian': Decimal(str(sum(daily))) / Decimal(jumlah_hari),
        'prediksi_periode': predicted_total,
        'mape_persen': ml_mape,
        'mape_ses_persen': ses_mape,
        'mae': ml_mae,
        'mae_ses': ses_mae,
        'rmse': ml_rmse,
        'rmse_ses': ses_rmse,
        'jumlah_data_uji': len(ml_errors),
        'jumlah_data_uji_mape': valid_windows,
        'jumlah_data_uji_nol': zero_windows,
        'buffer_adaptif': buffer_units,
        'status_buffer': buffer_status,
        'offset_uji_awal': origins[0],
    }
