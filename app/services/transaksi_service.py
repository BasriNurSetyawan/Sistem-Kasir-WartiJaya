from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.repositories import transaksi_repository


def record_sale(item_id, quantity, sold_on):
    try:
        return transaksi_repository.record_sale(item_id, quantity, sold_on)
    except SQLAlchemyError:
        db.session.rollback()
        raise


def record_sale_batch(lines, sold_on):
    try:
        return transaksi_repository.record_sale_batch(lines, sold_on)
    except SQLAlchemyError:
        db.session.rollback()
        raise


def latest_sales(limit=8):
    try:
        return transaksi_repository.latest_sales(limit)
    except SQLAlchemyError:
        db.session.rollback()
        raise
