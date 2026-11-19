from app import db
from app.models import Pengguna
from sqlalchemy import select


class LastActiveAdminError(Exception):
    """Raised when an account change would remove the final active admin."""


def get_by_username(username):
    return db.session.query(Pengguna).filter_by(username=username).first()


def get_by_id(user_id):
    return db.session.get(Pengguna, user_id)


def list_users():
    return db.session.query(Pengguna).order_by(Pengguna.username).all()


def create_user(username, password_hash, role):
    user = Pengguna(username=username, password_hash=password_hash, role=role)
    db.session.add(user)
    db.session.commit()
    return user


def set_active(user_id, active):
    users = db.session.scalars(
        select(Pengguna).order_by(Pengguna.id).with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    user = next((candidate for candidate in users if candidate.id == user_id), None)
    if user is None:
        return None
    if (user.role == 'admin' and user.aktif and not active
            and sum(candidate.role == 'admin' and candidate.aktif for candidate in users) <= 1):
        raise LastActiveAdminError
    user.aktif = active
    db.session.commit()
    return user


def set_role(user_id, role):
    users = db.session.scalars(
        select(Pengguna).order_by(Pengguna.id).with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    user = next((candidate for candidate in users if candidate.id == user_id), None)
    if user is None:
        return None
    if (user.role == 'admin' and user.aktif and role != 'admin'
            and sum(candidate.role == 'admin' and candidate.aktif for candidate in users) <= 1):
        raise LastActiveAdminError
    user.role = role
    db.session.commit()
    return user
