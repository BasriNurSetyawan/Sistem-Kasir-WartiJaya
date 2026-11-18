from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.repositories import barang_repository
from app.repositories.barang_repository import ItemHasSales


def create_item(values):
    try:
        return barang_repository.create_item(values)
    except SQLAlchemyError:
        db.session.rollback()
        raise


def get_item(item_id):
    try:
        return barang_repository.get_item(item_id)
    except SQLAlchemyError:
        db.session.rollback()
        raise


def list_items(page, per_page):
    try:
        return barang_repository.list_items(page, per_page)
    except SQLAlchemyError:
        db.session.rollback()
        raise


def search_items(query, limit=10):
    try:
        return barang_repository.search_items(query, limit)
    except SQLAlchemyError:
        db.session.rollback()
        raise


def update_item(item_id, values):
    try:
        return barang_repository.update_item(item_id, values)
    except SQLAlchemyError:
        db.session.rollback()
        raise


def delete_item(item_id):
    try:
        return barang_repository.delete_item(item_id)
    except SQLAlchemyError:
        db.session.rollback()
        raise
