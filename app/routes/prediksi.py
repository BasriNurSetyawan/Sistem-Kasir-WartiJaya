from flask import current_app, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from app.business_time import business_today
from app.routes import api_bp
from app.schemas import alpha_arg
from app.services.prediksi_service import (
    ForecastRangeTooLong,
    InsufficientHistory,
    ItemNotFound,
    forecast,
)


@api_bp.route('/prediksi/<int:barang_id>', methods=['GET'])
def prediksi_stok(barang_id):
    try:
        alpha = alpha_arg(request.args.get('alpha'))
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    try:
        result = forecast(barang_id, alpha, business_today())
    except ItemNotFound:
        return jsonify({'error': 'Barang tidak ditemukan.'}), 404
    except InsufficientHistory:
        return jsonify({
            'error': 'Data historis tidak mencukupi (minimal 2 hari aktif transaksi).'
        }), 400
    except ForecastRangeTooLong:
        return jsonify({'error': 'Rentang data historis terlalu panjang untuk diprediksi.'}), 400
    except SQLAlchemyError:
        current_app.logger.exception('Gagal membuat prediksi penjualan')
        return jsonify({'error': 'Prediksi penjualan gagal dibuat.'}), 500
    return jsonify(result), 200
