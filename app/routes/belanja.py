from flask import current_app, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from app.routes import api_bp
from app.schemas import pagination_args
from app.services.belanja_service import list_details, list_summaries


def _pagination():
    return pagination_args(request.args)


@api_bp.route('/belanja/rekap', methods=['GET'])
def daftar_rekap_belanja():
    try:
        page, per_page = _pagination()
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    try:
        result = list_summaries(page, per_page)
    except SQLAlchemyError:
        current_app.logger.exception('Gagal mengambil rekap belanja')
        return jsonify({'error': 'Rekap belanja gagal dimuat.'}), 500
    return jsonify({
        'items': [{
            'id': row.id,
            'outlet': row.outlet,
            'tanggal_acuan': row.tanggal_acuan.isoformat(),
            'tanggal_selesai': row.tanggal_selesai.isoformat() if row.tanggal_selesai else None,
            'cakupan': row.cakupan,
            'keterangan_tanggal': row.keterangan_tanggal,
            'total': f'{row.total:.2f}',
        } for row in result.items],
        'page': result.page,
        'per_page': result.per_page,
        'total': result.total,
        'pages': result.pages,
    }), 200


@api_bp.route('/belanja/detail', methods=['GET'])
def daftar_detail_belanja():
    try:
        page, per_page = _pagination()
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    try:
        result = list_details(page, per_page)
    except SQLAlchemyError:
        current_app.logger.exception('Gagal mengambil detail belanja')
        return jsonify({'error': 'Detail belanja gagal dimuat.'}), 500
    return jsonify({
        'items': [{
            'id': row.id,
            'outlet': row.outlet,
            'tanggal': row.tanggal.isoformat(),
            'nama_barang': row.nama_barang,
            'jumlah_asli': row.jumlah_asli,
            'harga_total': f'{row.harga_total:.2f}',
            'kemungkinan_duplikat': row.kemungkinan_duplikat,
        } for row in result.items],
        'page': result.page,
        'per_page': result.per_page,
        'total': result.total,
        'pages': result.pages,
    }), 200
