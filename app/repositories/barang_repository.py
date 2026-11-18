from app import db
from app.models import Barang, DetailTransaksi, Transaksi


def create_item(values):
    item = Barang(**values)
    db.session.add(item)
    db.session.commit()
    return item


def get_item(item_id):
    return db.session.get(Barang, item_id)


class ItemHasSales(Exception):
    pass


def list_items(page, per_page):
    return db.paginate(
        db.select(Barang).order_by(Barang.id), page=page, per_page=per_page,
        error_out=False,
    )


def list_all_items():
    return db.session.scalars(db.select(Barang).order_by(Barang.nama_barang)).all()


def search_items(query, limit=10):
    escaped_query = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return db.session.scalars(
        db.select(Barang)
        .where(Barang.nama_barang.ilike(f'%{escaped_query}%', escape='\\'))
        .order_by(Barang.nama_barang, Barang.id)
        .limit(limit)
    ).all()


def update_item(item_id, values):
    item = db.session.get(Barang, item_id)
    if item is None:
        return None
    for field, value in values.items():
        setattr(item, field, value)
    db.session.commit()
    return item


def delete_item(item_id):
    item = db.session.get(Barang, item_id)
    if item is None:
        return False
    if (db.session.query(Transaksi.id).filter_by(barang_id=item_id).first()
            or db.session.query(DetailTransaksi.id).filter_by(barang_id=item_id).first()):
        raise ItemHasSales
    db.session.delete(item)
    db.session.commit()
    return True
