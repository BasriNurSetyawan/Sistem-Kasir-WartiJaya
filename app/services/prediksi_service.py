from datetime import timedelta
from decimal import Decimal

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.repositories import barang_repository, transaksi_repository
from algorithm.ml_forecast import MIN_ML_HISTORY_DAYS, peramalkan_random_forest
from algorithm.retail_optimizer import calculate_restock_priority
from app.services.peramalan_penjualan import (
    MIN_ALPHA_TUNING_DAYS,
    MIN_BACKTEST_TRAINING_DAYS,
    MIN_BUFFER_BACKTEST_WINDOWS,
    peramalkan_ses,
)

HISTORY_WINDOW_DAYS = 120
FORECAST_HORIZON_DAYS = 7
SES_BACKTEST_WINDOWS = 15


class ItemNotFound(Exception):
    pass


def _item_forecast(item, daily_sales, history_start, today):
    if not daily_sales:
        return {
            'barang_id': item.id,
            'nama_barang': item.nama_barang,
            'stok_saat_ini': item.stok,
            'total_terjual_28_hari': 0,
            'total_terjual_120_hari': 0,
            'hari_histori': 0,
            'rata_rata_harian': None,
            'prediksi_harian_ses': None,
            'prediksi_penjualan_ses': None,
            'prediksi_penjualan_ml': None,
            'prediksi_penjualan': None,
            'metode_peramalan': 'Belum ada model; tinjau manual',
            'status_ml': 'tanpa_histori',
            'alasan_pemilihan_model': 'Tidak ada penjualan dalam 120 hari terakhir.',
            'alpha': None,
            'mape_persen': None,
            'mae': None,
            'rmse': None,
            'mape_ses_persen': None,
            'mape_ml_persen': None,
            'jumlah_data_latih': 0,
            'jumlah_data_uji': 0,
            'jumlah_data_uji_mape': 0,
            'jumlah_data_uji_nol': 0,
            'jumlah_data_uji_ses': 0,
            'buffer_adaptif': 0,
            'status_buffer': 'tidak_ada_histori',
            'status_alpha': 'data_tidak_tersedia',
            'tanggal_awal_histori': None,
            'tanggal_akhir_histori': None,
            'tanggal_mulai_uji': None,
            'tanggal_akhir_uji': None,
            'rekomendasi_restock': None,
            'stok_target_7_hari': None,
            'cakupan_stok_hari': None,
            'tingkat_risiko': 'tinjau_manual',
            'skor_prioritas': 5 if item.stok > 0 else 0,
            'tier_prioritas': 'P5_DEAD_STOCK' if item.stok > 0 else 'P4_CUKUP',
            'label_prioritas': 'Dead Stock (Mengendap)' if item.stok > 0 else 'Stok Cukup',
            'hari_habis_stok': None,
            'estimasi_modal_restok': '0.00',
            '_estimasi_modal_raw': Decimal('0.00'),
            'status_data': 'tanpa_histori',
            'alasan_rekomendasi': 'Tidak ada penjualan dalam 120 hari; periksa pencatatan dan barang secara manual.',
            'histori_terbatas': True,
            'status': 'tanpa_data_terbaru',
        }

    observed_start = max(history_start, min(daily_sales))
    days_observed = (today - observed_start).days + 1
    daily_values = [
        daily_sales.get(observed_start + timedelta(days=offset), 0)
        for offset in range(days_observed)
    ]
    ses = peramalkan_ses(
        daily_values,
        FORECAST_HORIZON_DAYS,
        max_backtest_windows=SES_BACKTEST_WINDOWS,
    )
    try:
        ml = peramalkan_random_forest(daily_values, FORECAST_HORIZON_DAYS)
    except Exception:
        current_app.logger.exception('Kandidat ML gagal; rekomendasi memakai fallback SES')
        ml = {
            'tersedia': False,
            'status': 'model_ml_gagal',
            'alasan': 'Kandidat ML mengalami kegagalan; sistem memakai SES dan mencatat detail pada log aplikasi.',
        }
    selected = ml if ml['tersedia'] else ses
    forecast_units = selected['prediksi_periode']
    buffer_units = selected['buffer_adaptif']
    target_stock = forecast_units + buffer_units
    restock_units = max(0, target_stock - item.stok)

    if item.stok < forecast_units:
        risk = 'risiko_tinggi'
    elif item.stok < target_stock:
        risk = 'risiko_sedang'
    else:
        risk = 'risiko_rendah'

    if days_observed < MIN_ALPHA_TUNING_DAYS:
        data_status = 'histori_tuning_terbatas'
    elif ses['jumlah_data_uji'] < MIN_BACKTEST_TRAINING_DAYS:
        data_status = 'jendela_backtest_terbatas'
    else:
        data_status = 'backtest_tersedia'

    model_label = (
        'Random Forest Regressor (fitur lag)' if ml['tersedia']
        else 'Single Exponential Smoothing (SES)'
    )
    if data_status != 'backtest_tersedia':
        decision_reason = (
            f"Histori evaluasi terbatas; {model_label} memproyeksikan "
            f"{forecast_units} unit. Periksa rekomendasi secara manual."
        )
    elif restock_units:
        decision_reason = (
            f"{model_label}: target 7 hari {forecast_units} unit + buffer adaptif "
            f"{buffer_units} unit = {target_stock} unit; stok {item.stok} unit, "
            f"sehingga disarankan restok {restock_units} unit."
        )
    else:
        decision_reason = (
            f"{model_label}: stok {item.stok} unit memenuhi target 7 hari "
            f"{target_stock} unit (ramalan {forecast_units} + buffer {buffer_units})."
        )

    stock_cover = (
        Decimal(item.stok) / selected['prediksi_harian']
        if selected['prediksi_harian'] > 0 else None
    )
    total_28_days = sum(
        quantity for sale_date, quantity in daily_sales.items()
        if sale_date >= today - timedelta(days=27)
    )
    has_ml_validation = ml.get('jumlah_data_uji', 0) > 0
    chosen_mape = (
        selected.get('mape_persen') if ml['tersedia']
        else ml.get('mape_ses_persen') if has_ml_validation
        else ses.get('mape_persen')
    )
    chosen_mae = (
        selected.get('mae') if ml['tersedia']
        else ml.get('mae_ses') if has_ml_validation
        else ses.get('mae')
    )
    chosen_rmse = (
        selected.get('rmse') if ml['tersedia']
        else ml.get('rmse_ses') if has_ml_validation
        else ses.get('rmse')
    )
    evaluation_windows = (
        ml['jumlah_data_uji'] if has_ml_validation else selected['jumlah_data_uji']
    )
    evaluation_valid_windows = (
        ml['jumlah_data_uji_mape'] if has_ml_validation
        else selected['jumlah_data_uji_mape']
    )
    evaluation_zero_windows = (
        ml['jumlah_data_uji_nol'] if has_ml_validation
        else selected['jumlah_data_uji_nol']
    )
    validation_start_offset = (
        ml.get('offset_uji_awal') if has_ml_validation
        else MIN_BACKTEST_TRAINING_DAYS
    )
    priority_info = calculate_restock_priority(
        item.stok,
        selected['prediksi_harian'],
        restock_units,
        item.harga,
        total_28_days,
    )
    return {
        'barang_id': item.id,
        'nama_barang': item.nama_barang,
        'stok_saat_ini': item.stok,
        'total_terjual_28_hari': total_28_days,
        'total_terjual_120_hari': sum(daily_sales.values()),
        'hari_histori': days_observed,
        'rata_rata_harian': f"{Decimal(sum(daily_values)) / Decimal(len(daily_values)):.2f}",
        'prediksi_harian_ses': f"{ses['prediksi_harian']:.2f}",
        'prediksi_penjualan_ses': ses['prediksi_periode'],
        'prediksi_penjualan_ml': ml.get('prediksi_periode') if ml['tersedia'] else None,
        'prediksi_penjualan': forecast_units,
        'metode_peramalan': model_label,
        'status_ml': ml['status'],
        'alasan_pemilihan_model': ml['alasan'],
        'alpha': f"{ses['alpha']:.2f}",
        'mape_persen': f'{chosen_mape:.2f}' if chosen_mape is not None else None,
        'mape_ses_persen': (
            f"{ml['mape_ses_persen']:.2f}"
            if ml.get('mape_ses_persen') is not None
            else f"{ses['mape_persen']:.2f}"
            if ses['mape_persen'] is not None else None
        ),
        'mape_ses_rolling_persen': (
            f"{ses['mape_persen']:.2f}" if ses['mape_persen'] is not None else None
        ),
        'mape_ml_persen': (
            f"{ml['mape_persen']:.2f}" if ml.get('mape_persen') is not None else None
        ),
        '_mape_persen_raw': str(chosen_mape) if chosen_mape is not None else None,
        'mae': f"{chosen_mae:.2f}" if chosen_mae is not None else None,
        'rmse': f"{chosen_rmse:.2f}" if chosen_rmse is not None else None,
        '_mae_raw': str(chosen_mae) if chosen_mae is not None else None,
        '_rmse_raw': str(chosen_rmse) if chosen_rmse is not None else None,
        'jumlah_data_latih': ses['jumlah_data_latih'],
        'jumlah_data_uji': evaluation_windows,
        'jumlah_data_uji_mape': evaluation_valid_windows,
        'jumlah_data_uji_nol': evaluation_zero_windows,
        'jumlah_data_uji_ses': ses['jumlah_data_uji'],
        'status_alpha': ses['status_alpha'],
        'tanggal_awal_histori': observed_start.isoformat(),
        'tanggal_akhir_histori': today.isoformat(),
        'tanggal_mulai_uji': (
            (
                observed_start + timedelta(days=validation_start_offset)
            ).isoformat() if selected['jumlah_data_uji'] else None
        ),
        'tanggal_akhir_uji': today.isoformat() if selected['jumlah_data_uji'] else None,
        'rekomendasi_restock': restock_units,
        'buffer_adaptif': buffer_units,
        'status_buffer': selected['status_buffer'],
        'stok_target_7_hari': target_stock,
        'cakupan_stok_hari': f'{stock_cover:.2f}' if stock_cover is not None else None,
        'tingkat_risiko': risk,
        'skor_prioritas': priority_info['skor_prioritas'],
        'tier_prioritas': priority_info['tier_prioritas'],
        'label_prioritas': priority_info['label_prioritas'],
        'hari_habis_stok': priority_info['hari_habis_stok'],
        'estimasi_modal_restok': f"{priority_info['estimasi_modal_restok']:.2f}",
        '_estimasi_modal_raw': priority_info['estimasi_modal_restok'],
        'status_data': data_status,
        'alasan_rekomendasi': decision_reason,
        'histori_terbatas': data_status != 'backtest_tersedia',
        'status': 'perlu_restock' if restock_units > 0 else 'stok_cukup',
    }


def restock_plan(today):
    history_start = today - timedelta(days=HISTORY_WINDOW_DAYS - 1)
    try:
        items = barang_repository.list_all_items()
        sales = transaksi_repository.daily_sales_for_period(history_start, today)
    except SQLAlchemyError:
        db.session.rollback()
        raise

    daily_by_item = {}
    daily_totals = {}
    for row in sales:
        daily_by_item.setdefault(row.barang_id, {})[row.tanggal] = int(row.total_harian)
        daily_totals[row.tanggal] = daily_totals.get(row.tanggal, 0) + int(row.total_harian)

    recommendations = [
        _item_forecast(item, daily_by_item.get(item.id, {}), history_start, today)
        for item in items
    ]
    def _sort_key(row):
        tier = row.get('tier_prioritas', '')
        tier_rank = 0 if tier == 'P1_KRITIS' else 1 if tier == 'P2_TINGGI' else 2 if tier == 'P3_SEDANG' else 4 if tier == 'P5_DEAD_STOCK' else 3
        return (
            tier_rank,
            -int(row.get('skor_prioritas', 0)),
            -int(row['rekomendasi_restock'] or 0),
            row['nama_barang'].casefold(),
        )

    recommendations.sort(key=_sort_key)
    mape_samples = sum(row.get('jumlah_data_uji_mape', 0) for row in recommendations)
    zero_actual_samples = sum(row.get('jumlah_data_uji_nol', 0) for row in recommendations)
    weighted_mape = sum(
        Decimal(row['_mape_persen_raw']) * row['jumlah_data_uji_mape']
        for row in recommendations if row.get('mape_persen') is not None
    )
    ml_count = sum(row['status_ml'] == 'random_forest_mengungguli_ses' for row in recommendations)
    total_anggaran_restok = sum(
        row.get('_estimasi_modal_raw', Decimal('0.00'))
        for row in recommendations
        if row.get('status') == 'perlu_restock'
    )
    barang_kritis = [row for row in recommendations if row.get('tier_prioritas') == 'P1_KRITIS']
    barang_dead_stock = [row for row in recommendations if row.get('tier_prioritas') == 'P5_DEAD_STOCK']

    valid_mae_rows = [row for row in recommendations if row.get('_mae_raw') is not None]
    valid_rmse_rows = [row for row in recommendations if row.get('_rmse_raw') is not None]
    mae_gabungan = (
        f"{sum(Decimal(r['_mae_raw']) for r in valid_mae_rows) / Decimal(len(valid_mae_rows)):.2f}"
        if valid_mae_rows else None
    )
    rmse_gabungan = (
        f"{sum(Decimal(r['_rmse_raw']) for r in valid_rmse_rows) / Decimal(len(valid_rmse_rows)):.2f}"
        if valid_rmse_rows else None
    )

    for row in recommendations:
        row.pop('_mape_persen_raw', None)
        row.pop('_mae_raw', None)
        row.pop('_rmse_raw', None)
        row.pop('_estimasi_modal_raw', None)
    return {
        'metode': 'Random Forest Regressor dibandingkan dengan SES melalui backtest berurutan waktu; SES digunakan bila ML tidak cukup data atau tidak lebih baik',
        'metode_detail': {
            'model_ml': 'Random Forest Regressor dengan fitur lag 1, 2, 3, 7, 14, 21, 28 hari dan rerata bergerak 7, 14, 28 hari',
            'minimum_histori_ml_hari': MIN_ML_HISTORY_DAYS,
            'validasi_ml': 'Jendela uji mingguan kronologis tanpa pengacakan; ML dipilih hanya bila MAPE lebih rendah pada jendela yang sama',
            'metode_fallback': 'SES menjadi baseline/fallback jika histori ML terbatas atau hasil ML tidak lebih baik',
            'nama': 'Single Exponential Smoothing (SES)',
            'pemilihan_alpha': 'MAPE terkecil pada data latih, dengan kandidat alpha 0.01 sampai 1.00',
            'evaluasi_ses': 'MAPE total permintaan 7 hari pada backtest rolling-origin; jendela aktual total nol dilaporkan tetapi tidak masuk penyebut MAPE',
            'minimum_histori_backtest_hari': MIN_BACKTEST_TRAINING_DAYS + FORECAST_HORIZON_DAYS,
            'minimum_histori_tuning_alpha_hari': MIN_ALPHA_TUNING_DAYS,
            'minimum_jendela_buffer': MIN_BUFFER_BACKTEST_WINDOWS,
            'maksimum_jendela_backtest_ses': SES_BACKTEST_WINDOWS,
            'aturan_keputusan': 'risiko tinggi bila stok di bawah ramalan 7 hari; risiko sedang bila stok di bawah target setelah buffer; risiko rendah bila stok memenuhi target; tanpa histori ditinjau manual',
            'buffer_adaptif': 'Buffer dibentuk dari galat underforecast model terpilih jika jendela cukup; hasilnya heuristik, bukan jaminan service level',
            'horizon_hari': FORECAST_HORIZON_DAYS,
            'histori_model_hari': HISTORY_WINDOW_DAYS,
        },
        'periode': {
            'mulai': (today + timedelta(days=1)).isoformat(),
            'sampai': (today + timedelta(days=FORECAST_HORIZON_DAYS)).isoformat(),
            'jumlah_hari': FORECAST_HORIZON_DAYS,
        },
        'jumlah_barang_direstok': sum(row['status'] == 'perlu_restock' for row in recommendations),
        'total_anggaran_restok': f'{total_anggaran_restok:.2f}',
        'total_anggaran_restok_formatted': f'{total_anggaran_restok:,.2f}',
        'jumlah_barang_kritis': len(barang_kritis),
        'jumlah_barang_dead_stock': len(barang_dead_stock),
        'barang_kritis': barang_kritis,
        'barang_dead_stock': barang_dead_stock,
        'jumlah_risiko_tinggi': sum(row['tingkat_risiko'] == 'risiko_tinggi' for row in recommendations),
        'jumlah_risiko_sedang': sum(row['tingkat_risiko'] == 'risiko_sedang' for row in recommendations),
        'jumlah_tinjau_manual': sum(row['tingkat_risiko'] == 'tinjau_manual' for row in recommendations),
        'jumlah_model_ml_digunakan': ml_count,
        'jumlah_fallback_ses': len(recommendations) - ml_count,
        'mape_gabungan': f'{weighted_mape / Decimal(mape_samples):.2f}' if mape_samples else None,
        'mae_gabungan': mae_gabungan,
        'rmse_gabungan': rmse_gabungan,
        'jumlah_sampel_mape': mape_samples,
        'jumlah_data_uji_nol': zero_actual_samples,
        'tren_penjualan': [
            {
                'tanggal': (today - timedelta(days=offset)).isoformat(),
                'unit': daily_totals.get(today - timedelta(days=offset), 0),
            }
            for offset in range(27, -1, -1)
        ],
        'total_prediksi_penjualan': sum(int(row['prediksi_penjualan'] or 0) for row in recommendations),
        'total_unit_restock': sum(int(row['rekomendasi_restock'] or 0) for row in recommendations),
        'barang': recommendations,
    }


def forecast(item_id, today):
    item = barang_repository.get_item(item_id)
    if item is None:
        raise ItemNotFound
    history_start = today - timedelta(days=HISTORY_WINDOW_DAYS - 1)
    sales = transaksi_repository.daily_sales_for_period(history_start, today)
    daily_sales = {row.tanggal: int(row.total_harian) for row in sales if row.barang_id == item_id}
    res = _item_forecast(item, daily_sales, history_start, today)
    res.pop('_mape_persen_raw', None)
    res.pop('_mae_raw', None)
    res.pop('_rmse_raw', None)
    res.pop('_estimasi_modal_raw', None)
    return {
        'metode': 'Random Forest Regressor dibandingkan dengan SES melalui backtest berurutan waktu; SES digunakan bila ML tidak cukup data atau tidak lebih baik',
        'periode': {
            'mulai': (today + timedelta(days=1)).isoformat(),
            'sampai': (today + timedelta(days=FORECAST_HORIZON_DAYS)).isoformat(),
            'jumlah_hari': FORECAST_HORIZON_DAYS,
        },
        **res,
    }

