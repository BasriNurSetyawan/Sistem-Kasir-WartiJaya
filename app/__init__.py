from flask import Flask, jsonify
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from config import Config

# Inisialisasi ekstensi
db = SQLAlchemy()
migrate = Migrate()

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if app.config.get('MAX_CONTENT_LENGTH') is None:
        app.config['MAX_CONTENT_LENGTH'] = 1_048_576
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=28_800,
    )
    if not app.config.get('SECRET_KEY'):
        raise RuntimeError('SECRET_KEY wajib disetel melalui environment sebelum aplikasi dijalankan.')
    token = app.config.get('API_TOKEN')
    if not isinstance(token, str) or len(token) < 32 or not token.isascii():
        raise RuntimeError('API_TOKEN wajib disetel dan minimal 32 karakter.')

    db.init_app(app)
    migrate.init_app(app, db)

    @app.get('/healthz')
    def health_check():
        try:
            db.session.execute(text('SELECT 1'))
            return jsonify({'status': 'ok', 'database': 'ok'}), 200
        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception('Health check database gagal')
            return jsonify({'status': 'error', 'database': 'unavailable'}), 503

    # Registrasi Blueprint untuk Routes
    from app.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    from app.ui import ui_bp
    app.register_blueprint(ui_bp)

    @app.cli.command('bootstrap-admin')
    def bootstrap_admin():
        """Create the configured first admin account when no admin exists."""
        from app.models import Pengguna

        username = app.config.get('BOOTSTRAP_ADMIN_USERNAME')
        password = app.config.get('BOOTSTRAP_ADMIN_PASSWORD')
        if not username or not password or len(password) < 12:
            raise RuntimeError('BOOTSTRAP_ADMIN_USERNAME/PASSWORD wajib disetel; password minimal 12 karakter.')
        existing = db.session.query(Pengguna).filter_by(role='admin', aktif=True).first()
        if existing:
            print(f'Admin aktif sudah tersedia: {existing.username}')
            return
        user = Pengguna(
            username=username,
            password_hash=generate_password_hash(password),
            role='admin',
            aktif=True,
        )
        db.session.add(user)
        db.session.commit()
        print(f'Admin awal dibuat: {username}')

    return app
