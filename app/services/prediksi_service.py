from datetime import date

from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.repositories import barang_repository, transaksi_repository
from app.services.prediksi_ses import hitung_ses_mape

MAX_FORECAST_DAYS = 36_500


class ItemNotFound(Exception):
    pass


class InsufficientHistory(Exception):
    pass


class ForecastRangeTooLong(Exception):
    pass


def forecast(item_id, alpha, today):
    try:
        item = barang_repository.get_item(item_id)
        if item is None:
            raise ItemNotFound
        sales = transaksi_repository.daily_sales_for_item(item_id)
    except SQLAlchemyError:
        db.session.rollback()
        raise
    if len(sales) < 2:
        raise InsufficientHistory

    by_date = {row.tanggal: row.total_harian for row in sales}
    first_day = sales[0].tanggal
    last_day = max(sales[-1].tanggal, today)
    if (last_day - first_day).days + 1 > MAX_FORECAST_DAYS:
        raise ForecastRangeTooLong

    dates = [date.fromordinal(n) for n in range(first_day.toordinal(), last_day.toordinal() + 1)]
    actuals = [by_date.get(day, 0) for day in dates]
    prediction, mape = hitung_ses_mape(actuals, alpha)
    return {
        'barang_id': item.id,
        'nama_barang': item.nama_barang,
        'parameter_alpha': alpha,
        'total_hari_transaksi': len(sales),
        'total_hari_periode': len(actuals),
        'data_aktual': actuals,
        'tanggal_historis': [day.isoformat() for day in dates],
        'prediksi_penjualan_besok': prediction,
        'mape': mape,
    }
