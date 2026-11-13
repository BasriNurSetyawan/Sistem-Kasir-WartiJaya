from flask import current_app, jsonify
from sqlalchemy.exc import SQLAlchemyError

from app.business_time import business_today
from app.repositories.transaksi_repository import InsufficientStock, ItemNotFound
from app.routes import api_bp
from app.schemas import json_object, sale_args
from app.services.transaksi_service import record_sale


@api_bp.route('/transaksi', methods=['POST'])
def catat_transaksi():
    try:
        item_id, quantity, sold_on = sale_args(json_object(), business_today())
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    try:
        remaining = record_sale(item_id, quantity, sold_on)
    except ItemNotFound:
        return jsonify({'error': 'Barang tidak ditemukan.'}), 404
    except InsufficientStock as exc:
        return jsonify({'error': f'Stok tidak mencukupi. Sisa stok: {exc.remaining}'}), 400
    except SQLAlchemyError:
        current_app.logger.exception('Gagal menyimpan transaksi')
        return jsonify({'error': 'Transaksi gagal disimpan.'}), 500
    return jsonify({'pesan': 'Transaksi berhasil', 'sisa_stok': remaining}), 201
