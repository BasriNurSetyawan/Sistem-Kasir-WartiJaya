from pathlib import Path
import hashlib

from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.importers.rekap_belanja_xlsx import read_workbook
from app.repositories.belanja_repository import import_rows


def import_workbook(path):
    summaries, details = read_workbook(path)
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    try:
        imported = import_rows(summaries, details, digest)
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return {
        'imported': imported,
        'summary_rows': len(summaries),
        'detail_rows': len(details),
        'possible_duplicate_details': sum(row['kemungkinan_duplikat'] for row in details),
        'summary_total': sum((row['total'] for row in summaries), start=0),
        'detail_total': sum((row['harga_total'] for row in details), start=0),
    }
