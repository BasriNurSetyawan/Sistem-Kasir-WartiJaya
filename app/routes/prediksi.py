from flask import current_app, jsonify
from sqlalchemy.exc import SQLAlchemyError

from app.business_time import business_today
from app.routes import api_bp
from app.services.prediksi_service import (
    ItemNotFound,
    forecast,
    restock_plan,
)


@api_bp.route('/prediksi/restok', methods=['GET'])
def rekomendasi_restock():
    try:
        return jsonify(restock_plan(business_today())), 200
    except SQLAlchemyError:
        current_app.logger.exception('Gagal membuat rekomendasi restok')
        return jsonify({'error': 'Rekomendasi restok gagal dibuat.'}), 500


@api_bp.route('/prediksi/<int:barang_id>', methods=['GET'])
def prediksi_stok(barang_id):
    try:
        result = forecast(barang_id, business_today())
    except ItemNotFound:
        return jsonify({'error': 'Barang tidak ditemukan.'}), 404
    except SQLAlchemyError:
        current_app.logger.exception('Gagal membuat prediksi penjualan')
        return jsonify({'error': 'Prediksi penjualan gagal dibuat.'}), 500
    return jsonify(result), 200
