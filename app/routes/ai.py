"""REST API routes for AI insights, Copilot chat, and market basket analysis."""

from flask import current_app, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from app.routes import api_bp
from app.schemas import json_object
from app.services import ai_assistant_service
from app.services.ai_response import clean_response


@api_bp.route('/ai/insights/restok', methods=['GET'])
def ai_insight_restok():
    force_refresh = request.args.get('refresh', '').lower() in ('true', '1')
    try:
        data = ai_assistant_service.get_or_generate_inventory_insight(force_refresh=force_refresh)
        data['insight'] = clean_response(data.get('insight'))
        return jsonify(data), 200
    except SQLAlchemyError:
        current_app.logger.exception('Gagal memuat AI insight restok')
        return jsonify({'error': 'Insight AI gagal dimuat.'}), 500


@api_bp.route('/ai/chat', methods=['POST'])
def ai_chat():
    try:
        body = json_object()
        message = body.get('message')
        if not isinstance(message, str) or not message.strip():
            return jsonify({'error': 'message wajib berupa teks dan tidak boleh kosong.'}), 400
        message = message.strip()
        if len(message) > 2000:
            return jsonify({'error': 'message maksimal 2000 karakter.'}), 400
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    try:
        response = ai_assistant_service.handle_chat_message(user_id=None, message_text=message)
        if response.get('reply'):
            response['reply'] = clean_response(response['reply'])
        return jsonify(response), 200
    except SQLAlchemyError:
        current_app.logger.exception('Gagal memproses pesan AI chat')
        return jsonify({'error': 'Percakapan AI gagal diproses.'}), 500


@api_bp.route('/ai/chat/history', methods=['GET'])
def ai_chat_history():
    try:
        history = ai_assistant_service.get_chat_history()
        for message in history:
            if message.get('role') == 'assistant':
                message['pesan'] = clean_response(message.get('pesan'))
        return jsonify({'messages': history}), 200
    except SQLAlchemyError:
        current_app.logger.exception('Gagal memuat riwayat AI chat')
        return jsonify({'error': 'Riwayat chat gagal dimuat.'}), 500


@api_bp.route('/ai/basket-analysis', methods=['GET'])
def ai_basket_analysis():
    try:
        data = ai_assistant_service.get_market_basket_data()
        data['ai_rekomendasi_bundling'] = clean_response(data.get('ai_rekomendasi_bundling'))
        return jsonify(data), 200
    except SQLAlchemyError:
        current_app.logger.exception('Gagal memuat analisis keranjang belanja')
        return jsonify({'error': 'Analisis keranjang belanja gagal dimuat.'}), 500


@api_bp.route('/ai/cross-sell', methods=['POST'])
def ai_cross_sell():
    try:
        body = json_object()
        cart_item_ids = body.get('cart_item_ids', [])
        if (not isinstance(cart_item_ids, list) or len(cart_item_ids) > 100
                or any(isinstance(item_id, bool) or not isinstance(item_id, int) or item_id < 1
                       for item_id in cart_item_ids)):
            return jsonify({'error': 'cart_item_ids harus berisi maksimal 100 ID bilangan bulat positif.'}), 400
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    try:
        suggestions = ai_assistant_service.get_cross_sell_for_cart(cart_item_ids)
        return jsonify({'suggestions': suggestions}), 200
    except SQLAlchemyError:
        current_app.logger.exception('Gagal memuat saran cross-sell')
        return jsonify({'error': 'Saran cross-sell gagal dimuat.'}), 500


@api_bp.route('/ai/anomali', methods=['GET'])
def ai_anomali():
    try:
        anomalies = ai_assistant_service.get_store_anomalies()
        return jsonify({'anomali': anomalies, 'total': len(anomalies)}), 200
    except SQLAlchemyError:
        current_app.logger.exception('Gagal mendeteksi anomali inventori')
        return jsonify({'error': 'Deteksi anomali gagal dimuat.'}), 500


@api_bp.route('/ai/clustering', methods=['GET'])
def ai_clustering():
    try:
        clustering_data = ai_assistant_service.get_product_clustering_data()
        return jsonify(clustering_data), 200
    except SQLAlchemyError:
        current_app.logger.exception('Gagal memuat segmentasi produk K-Means')
        return jsonify({'error': 'Segmentasi produk gagal dimuat.'}), 500
