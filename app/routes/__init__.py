from flask import Blueprint

api_bp = Blueprint('api', __name__)

from app.routes import ai, belanja, barang, prediksi, rekap, security, transaksi  # noqa: E402,F401
