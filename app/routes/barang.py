from flask import current_app, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.barang_repository import ItemHasSales
from app.routes import api_bp
from app.schemas import json_object, new_item, pagination_args
from app.services import barang_service


@api_bp.route('/barang', methods=['POST'])
def tambah_barang():
    try:
        values = new_item(json_object())
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    try:
        item = barang_service.create_item(values)
    except SQLAlchemyError:
        current_app.logger.exception('Gagal menyimpan barang')
        return jsonify({'error': 'Barang gagal disimpan.'}), 500
    return jsonify({'pesan': 'Barang berhasil ditambahkan', 'id': item.id}), 201


@api_bp.route('/barang', methods=['GET'])
def get_semua_barang():
    try:
        page, per_page = pagination_args(request.args)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    try:
        pagination = barang_service.list_items(page, per_page)
    except SQLAlchemyError:
        current_app.logger.exception('Gagal mengambil daftar barang')
        return jsonify({'error': 'Daftar barang gagal dimuat.'}), 500
    return jsonify({
        'items': [{
            'id': item.id,
            'nama': item.nama_barang,
            'stok': item.stok,
            'harga': f'{item.harga:.2f}',
        } for item in pagination.items],
        'page': pagination.page,
        'per_page': pagination.per_page,
        'total': pagination.total,
        'pages': pagination.pages,
    }), 200


@api_bp.route('/barang/<int:item_id>', methods=['PUT'])
def perbarui_barang(item_id):
    try:
        values = new_item(json_object())
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    try:
        item = barang_service.update_item(item_id, values)
    except SQLAlchemyError:
        current_app.logger.exception('Gagal memperbarui barang')
        return jsonify({'error': 'Barang gagal diperbarui.'}), 500
    if item is None:
        return jsonify({'error': 'Barang tidak ditemukan.'}), 404
    return jsonify({'pesan': 'Barang berhasil diperbarui.', 'id': item.id}), 200


@api_bp.route('/barang/<int:item_id>', methods=['DELETE'])
def hapus_barang(item_id):
    try:
        deleted = barang_service.delete_item(item_id)
    except ItemHasSales:
        return jsonify({'error': 'Barang memiliki riwayat penjualan dan tidak dapat dihapus.'}), 409
    except SQLAlchemyError:
        current_app.logger.exception('Gagal menghapus barang')
        return jsonify({'error': 'Barang gagal dihapus.'}), 500
    if not deleted:
        return jsonify({'error': 'Barang tidak ditemukan.'}), 404
    return jsonify({'pesan': 'Barang berhasil dihapus.'}), 200
