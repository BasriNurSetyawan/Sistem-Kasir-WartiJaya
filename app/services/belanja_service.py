from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.repositories import belanja_repository


def list_summaries(page, per_page):
    try:
        return belanja_repository.list_summaries(page, per_page)
    except SQLAlchemyError:
        db.session.rollback()
        raise


def list_details(page, per_page):
    try:
        return belanja_repository.list_details(page, per_page)
    except SQLAlchemyError:
        db.session.rollback()
        raise
