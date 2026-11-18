from collections import defaultdict
from types import SimpleNamespace

from sqlalchemy import func, select, update
from sqlalchemy.orm import joinedload

from app import db
from app.models import Barang, DetailTransaksi, Transaksi, TransaksiHeader


class ItemNotFound(Exception):
    pass


class InsufficientStock(Exception):
    def __init__(self, remaining, item_id=None):
        self.remaining = remaining
        self.item_id = item_id


def record_sale_batch(lines, sold_on):
    """Reserve every line atomically, then persist one header and its details."""
    quantities = defaultdict(int)
    for line in lines:
        item_id, quantity = line['barang_id'], line['jumlah_terjual']
        if (not isinstance(item_id, int) or isinstance(item_id, bool) or item_id <= 0
                or not isinstance(quantity, int) or isinstance(quantity, bool)
                or quantity <= 0):
            raise ValueError('ID barang dan jumlah transaksi harus berupa bilangan bulat positif.')
        quantities[item_id] += quantity
    if not quantities:
        raise ValueError('Minimal satu barang harus dipilih.')

    items = {
        item.id: item for item in db.session.scalars(
            select(Barang).where(Barang.id.in_(quantities))
        ).all()
    }
    missing = set(quantities) - set(items)
    if missing:
        raise ItemNotFound

    remaining_stock = {}
    try:
        for item_id, quantity in quantities.items():
            result = db.session.execute(
                update(Barang).where(
                    Barang.id == item_id,
                    Barang.stok >= quantity,
                ).values(stok=Barang.stok - quantity)
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                db.session.rollback()
                current = db.session.get(Barang, item_id)
                raise InsufficientStock(current.stok if current else 0, item_id)
            remaining_stock[item_id] = items[item_id].stok - quantity

        header = TransaksiHeader(tanggal=sold_on)
        db.session.add(header)
        db.session.flush()
        db.session.add_all([
            DetailTransaksi(
                transaksi_id=header.id,
                barang_id=item_id,
                jumlah_terjual=quantity,
                harga_satuan=items[item_id].harga,
            )
            for item_id, quantity in quantities.items()
        ])
        db.session.commit()
        return remaining_stock
    except Exception:
        db.session.rollback()
        raise


def record_sale(item_id, quantity, sold_on):
    remaining = record_sale_batch(
        [{'barang_id': item_id, 'jumlah_terjual': quantity}], sold_on
    )
    return remaining[item_id]


def _daily_legacy(start, until):
    return db.session.query(
        Transaksi.tanggal,
        func.count(Transaksi.id).label('total_transaksi'),
        func.coalesce(func.sum(Transaksi.jumlah_terjual), 0).label('jumlah_terjual'),
        func.coalesce(
            func.sum(Transaksi.jumlah_terjual * Transaksi.harga_satuan), 0
        ).label('total_penghasilan'),
    ).filter(Transaksi.tanggal.between(start, until)) \
     .group_by(Transaksi.tanggal).all()


def _daily_header(start, until):
    return db.session.query(
        TransaksiHeader.tanggal,
        func.count(func.distinct(TransaksiHeader.id)).label('total_transaksi'),
        func.coalesce(func.sum(DetailTransaksi.jumlah_terjual), 0).label('jumlah_terjual'),
        func.coalesce(
            func.sum(DetailTransaksi.jumlah_terjual * DetailTransaksi.harga_satuan), 0
        ).label('total_penghasilan'),
    ).join(DetailTransaksi).filter(TransaksiHeader.tanggal.between(start, until)) \
     .group_by(TransaksiHeader.tanggal).all()


def daily_rows(start, until):
    totals = {}
    for row in [*_daily_legacy(start, until), *_daily_header(start, until)]:
        day = totals.setdefault(row.tanggal, {
            'tanggal': row.tanggal,
            'total_transaksi': 0,
            'jumlah_terjual': 0,
            'total_penghasilan': 0,
        })
        day['total_transaksi'] += int(row.total_transaksi)
        day['jumlah_terjual'] += int(row.jumlah_terjual)
        day['total_penghasilan'] += row.total_penghasilan
    return [
        SimpleNamespace(**totals[day])
        for day in sorted(totals)
    ]


def daily_sales_for_period(start, until):
    totals = defaultdict(int)
    legacy = db.session.query(
        Transaksi.barang_id,
        Transaksi.tanggal,
        func.sum(Transaksi.jumlah_terjual).label('total_harian'),
    ).filter(Transaksi.tanggal.between(start, until)) \
     .group_by(Transaksi.barang_id, Transaksi.tanggal).all()
    details = db.session.query(
        DetailTransaksi.barang_id,
        TransaksiHeader.tanggal,
        func.sum(DetailTransaksi.jumlah_terjual).label('total_harian'),
    ).join(TransaksiHeader).filter(TransaksiHeader.tanggal.between(start, until)) \
     .group_by(DetailTransaksi.barang_id, TransaksiHeader.tanggal).all()
    for row in [*legacy, *details]:
        totals[(row.barang_id, row.tanggal)] += int(row.total_harian)
    return [
        SimpleNamespace(barang_id=item_id, tanggal=day, total_harian=quantity)
        for (item_id, day), quantity in sorted(totals.items())
    ]


def latest_sales(limit=8):
    legacy = db.session.scalars(
        select(Transaksi).options(joinedload(Transaksi.barang))
        .order_by(Transaksi.tanggal.desc(), Transaksi.id.desc()).limit(limit)
    ).all()
    details = db.session.scalars(
        select(DetailTransaksi).options(
            joinedload(DetailTransaksi.barang),
            joinedload(DetailTransaksi.transaksi),
        ).join(TransaksiHeader)
        .order_by(TransaksiHeader.tanggal.desc(), DetailTransaksi.id.desc()).limit(limit)
    ).all()
    entries = [
        (sale.tanggal, sale.id, 0, sale) for sale in legacy
    ] + [
        (sale.transaksi.tanggal, sale.transaksi_id, sale.id, sale) for sale in details
    ]
    entries.sort(key=lambda entry: entry[:3], reverse=True)
    return [entry[3] for entry in entries[:limit]]


def get_all_receipt_itemsets():
    """Return a list of item_id sets representing transactions."""
    receipts_map = defaultdict(set)
    details = db.session.query(DetailTransaksi.transaksi_id, DetailTransaksi.barang_id).all()
    for tx_id, item_id in details:
        receipts_map[f"h_{tx_id}"].add(item_id)

    # Legacy rows do not share a receipt identifier, so treat each as a
    # separate single-item transaction rather than inventing daily baskets.
    if len([r for r in receipts_map.values() if len(r) > 1]) < 5:
        legacy = db.session.query(Transaksi.id, Transaksi.barang_id).all()
        for transaction_id, item_id in legacy:
            receipts_map[f"legacy_{transaction_id}"].add(item_id)

    return list(receipts_map.values())


def get_recent_transactions_for_anomaly_detection(limit=100):
    """Retrieve recent transaction summaries for Isolation Forest anomaly detection."""
    headers = (
        db.session.query(TransaksiHeader)
        .options(joinedload(TransaksiHeader.detail))
        .order_by(TransaksiHeader.tanggal.desc(), TransaksiHeader.id.desc())
        .limit(limit)
        .all()
    )
    result = []
    for h in headers:
        total_harga = float(sum(d.harga_satuan * d.jumlah_terjual for d in h.detail))
        total_item = len(h.detail)
        total_unit = sum(d.jumlah_terjual for d in h.detail)
        result.append({
            'transaksi_id': f"TRX-{h.id}",
            'tanggal': h.tanggal.isoformat(),
            'total_harga': total_harga,
            'total_item': total_item,
            'total_unit': total_unit,
        })
    if len(result) < 5:
        legacy = (
            db.session.query(Transaksi)
            .order_by(Transaksi.tanggal.desc(), Transaksi.id.desc())
            .limit(limit)
            .all()
        )
        for t in legacy:
            price = float(t.harga_satuan or (t.barang.harga if t.barang else 0))
            result.append({
                'transaksi_id': f"LEG-{t.id}",
                'tanggal': t.tanggal.isoformat(),
                'total_harga': price * t.jumlah_terjual,
                'total_item': 1,
                'total_unit': t.jumlah_terjual,
            })
    return result

