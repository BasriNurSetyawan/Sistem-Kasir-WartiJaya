from flask import current_app, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from app.business_time import business_today
from app.routes import api_bp
from app.schemas import report_args
from app.services.rekap_service import daily_report

MAX_REPORT_DAYS = 366


@api_bp.route('/rekap/harian', methods=['GET'])
def rekap_harian():
    try:
        start, until = report_args(request.args, business_today(), MAX_REPORT_DAYS)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    try:
        result = daily_report(start, until)
    except SQLAlchemyError:
        current_app.logger.exception('Gagal membuat rekap penjualan')
        return jsonify({'error': 'Rekap penjualan gagal dimuat.'}), 500
    return jsonify(result), 200
