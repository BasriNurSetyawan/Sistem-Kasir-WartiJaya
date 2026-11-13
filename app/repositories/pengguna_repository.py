from app import db
from app.models import Pengguna


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
    user = db.session.get(Pengguna, user_id)
    if user is None:
        return None
    user.aktif = active
    db.session.commit()
    return user


def set_role(user_id, role):
    user = db.session.get(Pengguna, user_id)
    if user is None:
        return None
    user.role = role
    db.session.commit()
    return user
