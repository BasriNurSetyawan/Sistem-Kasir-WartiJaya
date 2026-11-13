from datetime import timedelta

from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.repositories import barang_repository, transaksi_repository
from app.services.peramalan_penjualan import proyeksikan_permintaan

HISTORY_WINDOW_DAYS = 28
FORECAST_HORIZON_DAYS = 7


class ItemNotFound(Exception):
    pass


def _item_forecast(item, daily_sales, history_start, today):
    total_sold = sum(daily_sales.values())
    if not daily_sales:
        return {
            'barang_id': item.id,
            'nama_barang': item.nama_barang,
            'stok_saat_ini': item.stok,
            'total_terjual_28_hari': 0,
            'hari_histori': 0,
            'rata_rata_harian': None,
            'prediksi_penjualan': None,
            'rekomendasi_restock': None,
            'histori_terbatas': True,
            'status': 'tanpa_data_terbaru',
        }

    first_sale = min(daily_sales)
    observed_start = max(history_start, first_sale)
    days_observed = (today - observed_start).days + 1
    daily_values = [
        daily_sales.get(observed_start + timedelta(days=offset), 0)
        for offset in range(days_observed)
    ]
    average_daily, forecast_units = proyeksikan_permintaan(
        daily_values, FORECAST_HORIZON_DAYS
    )
    restock_units = max(0, forecast_units - item.stok)
    return {
        'barang_id': item.id,
        'nama_barang': item.nama_barang,
        'stok_saat_ini': item.stok,
        'total_terjual_28_hari': total_sold,
        'hari_histori': days_observed,
        'rata_rata_harian': f'{average_daily:.2f}',
        'prediksi_penjualan': forecast_units,
        'rekomendasi_restock': restock_units,
        'histori_terbatas': days_observed < 7,
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
    for row in sales:
        daily_by_item.setdefault(row.barang_id, {})[row.tanggal] = int(row.total_harian)

    recommendations = [
        _item_forecast(item, daily_by_item.get(item.id, {}), history_start, today)
        for item in items
    ]
    recommendations.sort(key=lambda row: (
        row['status'] == 'tanpa_data_terbaru',
        -int(row['rekomendasi_restock'] or 0),
        row['nama_barang'].casefold(),
    ))
    return {
        'metode': 'rata-rata penjualan harian 28 hari kalender terakhir',
        'periode': {
            'mulai': (today + timedelta(days=1)).isoformat(),
            'sampai': (today + timedelta(days=FORECAST_HORIZON_DAYS)).isoformat(),
            'jumlah_hari': FORECAST_HORIZON_DAYS,
        },
        'jumlah_barang_direstok': sum(
            row['status'] == 'perlu_restock' for row in recommendations
        ),
        'total_prediksi_penjualan': sum(
            int(row['prediksi_penjualan'] or 0) for row in recommendations
        ),
        'total_unit_restock': sum(
            int(row['rekomendasi_restock'] or 0) for row in recommendations
        ),
        'barang': recommendations,
    }


def forecast(item_id, today):
    plan = restock_plan(today)
    result = next(
        (row for row in plan['barang'] if row['barang_id'] == item_id), None
    )
    if result is None:
        raise ItemNotFound
    return {
        'metode': plan['metode'],
        'periode': plan['periode'],
        **result,
    }
