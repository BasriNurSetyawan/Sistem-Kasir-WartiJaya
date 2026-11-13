from datetime import date
from decimal import Decimal

from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.repositories import transaksi_repository


def daily_report(start, until):
    try:
        rows = transaksi_repository.daily_rows(start, until)
    except SQLAlchemyError:
        db.session.rollback()
        raise
    by_date = {row.tanggal: row for row in rows}
    daily = []
    transaction_count = 0
    quantity_total = 0
    income_total = Decimal('0.00')

    for ordinal in range(start.toordinal(), until.toordinal() + 1):
        day = date.fromordinal(ordinal)
        row = by_date.get(day)
        count = row.total_transaksi if row else 0
        quantity = row.jumlah_terjual if row else 0
        income = Decimal(str(row.total_penghasilan)) if row else Decimal('0.00')
        transaction_count += count
        quantity_total += quantity
        income_total += income
        daily.append({
            'tanggal': day.isoformat(),
            'total_transaksi': count,
            'jumlah_terjual': quantity,
            'total_penghasilan': f'{income:.2f}',
        })

    return {
        'dari': start.isoformat(),
        'sampai': until.isoformat(),
        'total_transaksi': transaction_count,
        'jumlah_terjual': quantity_total,
        'total_penghasilan': f'{income_total:.2f}',
        'harian': daily,
    }
