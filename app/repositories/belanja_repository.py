from app import db
from app.models import DetailBelanja, RekapBelanja


def import_rows(summaries, details, source_hash):
    imported_before = (
        db.session.query(RekapBelanja.id)
        .filter_by(source_sha256=source_hash).first()
        or db.session.query(DetailBelanja.id)
        .filter_by(source_sha256=source_hash).first()
    )
    if imported_before:
        return False
    db.session.add_all(RekapBelanja(**row) for row in summaries)
    db.session.add_all(DetailBelanja(**row) for row in details)
    db.session.commit()
    return True


def list_summaries(page, per_page):
    return db.paginate(
        db.select(RekapBelanja).order_by(
            RekapBelanja.tanggal_acuan.desc(), RekapBelanja.id.desc()
        ), page=page, per_page=per_page, error_out=False,
    )


def list_details(page, per_page):
    return db.paginate(
        db.select(DetailBelanja).order_by(DetailBelanja.tanggal.desc(), DetailBelanja.id.desc()),
        page=page, per_page=per_page, error_out=False,
    )
