from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

# Inisialisasi ekstensi
db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    if not app.config.get('SECRET_KEY'):
        raise RuntimeError('SECRET_KEY wajib disetel melalui environment sebelum aplikasi dijalankan.')

    db.init_app(app)

    # Registrasi Blueprint untuk Routes
    from app.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    # Buat tabel otomatis jika belum ada
    with app.app_context():
        db.create_all()

    return app
