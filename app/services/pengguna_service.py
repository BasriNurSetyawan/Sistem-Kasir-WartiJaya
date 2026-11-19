from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.repositories import pengguna_repository
from app.repositories.pengguna_repository import LastActiveAdminError


def authenticate(username, password):
    user = pengguna_repository.get_by_username(username)
    if user is None or not user.aktif or not check_password_hash(user.password_hash, password):
        return None
    return user


def create_user(username, password, role):
    try:
        return pengguna_repository.create_user(
            username, generate_password_hash(password), role
        )
    except SQLAlchemyError:
        db.session.rollback()
        raise


def list_users():
    try:
        return pengguna_repository.list_users()
    except SQLAlchemyError:
        db.session.rollback()
        raise


def set_active(user_id, active):
    try:
        return pengguna_repository.set_active(user_id, active)
    except LastActiveAdminError:
        db.session.rollback()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise


def set_role(user_id, role):
    try:
        return pengguna_repository.set_role(user_id, role)
    except LastActiveAdminError:
        db.session.rollback()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise
