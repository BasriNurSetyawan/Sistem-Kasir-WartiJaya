from sqlalchemy import func, select, update
from sqlalchemy.orm import joinedload

from app import db
from app.models import Barang, Transaksi


class ItemNotFound(Exception):
    pass


class InsufficientStock(Exception):
    def __init__(self, remaining):
        self.remaining = remaining


def record_sale(item_id, quantity, sold_on):
    item = db.session.get(Barang, item_id)
    if item is None:
        raise ItemNotFound

    result = db.session.execute(
        update(Barang).where(Barang.id == item_id, Barang.stok >= quantity)
        .values(stok=Barang.stok - quantity)
    )
    if result.rowcount != 1:
        db.session.rollback()
        item = db.session.get(Barang, item_id)
        raise InsufficientStock(item.stok if item else 0)

    db.session.add(Transaksi(
        barang_id=item_id,
        jumlah_terjual=quantity,
        harga_satuan=item.harga,
        tanggal=sold_on,
    ))
    db.session.commit()
    return db.session.get(Barang, item_id).stok


def daily_rows(start, until):
    return db.session.query(
        Transaksi.tanggal,
        func.count(Transaksi.id).label('total_transaksi'),
        func.coalesce(func.sum(Transaksi.jumlah_terjual), 0).label('jumlah_terjual'),
        func.coalesce(
            func.sum(Transaksi.jumlah_terjual * Transaksi.harga_satuan), 0
        ).label('total_penghasilan'),
    ).filter(Transaksi.tanggal.between(start, until)) \
     .group_by(Transaksi.tanggal).all()


def daily_sales_for_period(start, until):
    return db.session.query(
        Transaksi.barang_id,
        Transaksi.tanggal,
        func.sum(Transaksi.jumlah_terjual).label('total_harian'),
    ).filter(Transaksi.tanggal.between(start, until)) \
     .group_by(Transaksi.barang_id, Transaksi.tanggal) \
     .order_by(Transaksi.barang_id, Transaksi.tanggal).all()


def latest_sales(limit=8):
    return db.session.scalars(
        select(Transaksi).options(joinedload(Transaksi.barang))
        .order_by(Transaksi.tanggal.desc(), Transaksi.id.desc()).limit(limit)
    ).all()
