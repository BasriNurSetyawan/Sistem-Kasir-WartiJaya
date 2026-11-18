"""Orchestration service combining database repositories, ML algorithms, and Local NLU AI."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import logging

from app import db
from app.business_time import business_today
from app.models import AIChatMessage, AIInsight, Barang
from app.repositories import barang_repository, belanja_repository, transaksi_repository
from app.services import local_nlu_service, prediksi_service, rekap_service
from algorithm.anomaly_detector import detect_sales_anomalies, detect_transaction_anomalies
from algorithm.market_basket import analyze_market_baskets, get_cross_sell_suggestions
from algorithm.product_clustering import cluster_products

logger = logging.getLogger(__name__)


def get_product_clustering_data():
    """Cluster store products based on sales velocity, turnover, and revenue using K-Means."""
    today = business_today()
    plan = prediksi_service.restock_plan(today)
    all_items_map = {item.id: float(item.harga) for item in barang_repository.list_all_items()}

    items_for_clustering = [
        {
            'barang_id': b['barang_id'],
            'nama_barang': b['nama_barang'],
            'stok': b['stok_saat_ini'],
            'harga': all_items_map.get(b['barang_id'], 0.0),
            'total_terjual_28h': b.get('total_terjual_28_hari', 0),
        }
        for b in plan.get('barang', [])
    ]

    return cluster_products(items_for_clustering)


def get_live_store_context():
    """Aggregate a comprehensive context snapshot of Toko Warti Jaya."""
    today = business_today()
    all_items = barang_repository.list_all_items()
    report_today = rekap_service.daily_report(today, today)

    # Restock plan with empirical accuracy metrics
    plan = prediksi_service.restock_plan(today)

    # Top sellers over last 28 days
    top_items = sorted(
        plan.get('barang', []),
        key=lambda b: b.get('total_terjual_28_hari', 0),
        reverse=True,
    )

    # Clustering information
    clustering_data = get_product_clustering_data()

    # Popular pairs
    receipts = transaksi_repository.get_all_receipt_itemsets()
    item_names = {item.id: item.nama_barang for item in all_items}
    basket_results = analyze_market_baskets(receipts, item_names)

    return {
        'tanggal': today.isoformat(),
        'total_barang': len(all_items),
        'penjualan_hari_ini_transaksi': report_today.get('total_transaksi', 0),
        'penjualan_hari_ini_unit': report_today.get('jumlah_terjual', 0),
        'penjualan_hari_ini_omzet': report_today.get('total_penghasilan', '0.00'),
        'total_barang_restok': plan.get('jumlah_barang_direstok', 0),
        'estimasi_biaya_restok': plan.get('total_anggaran_restok_formatted', '0.00'),
        'barang_kritis': plan.get('barang_kritis', [])[:10],
        'barang_dead_stock': plan.get('barang_dead_stock', [])[:10],
        'mape_gabungan': plan.get('mape_gabungan'),
        'mae_gabungan': plan.get('mae_gabungan'),
        'rmse_gabungan': plan.get('rmse_gabungan'),
        'jumlah_model_ml_digunakan': plan.get('jumlah_model_ml_digunakan', 0),
        'jumlah_fallback_ses': plan.get('jumlah_fallback_ses', 0),
        'clustering_info': clustering_data,
        'popular_pairs': basket_results.get('pasangan_populer', []),
        'all_items': plan.get('barang', []),
        'top_seller': [
            {
                'nama_barang': item['nama_barang'],
                'terjual': item['total_terjual_28_hari'],
                'stok': item['stok_saat_ini'],
            }
            for item in top_items[:8] if item.get('total_terjual_28_hari', 0) > 0
        ],
    }


def get_or_generate_inventory_insight(force_refresh=False):
    """Retrieve the latest AI inventory insight or generate a new one using local ML."""
    today = business_today()

    # Check for recent cached insight (within 4 hours) unless forced
    if not force_refresh:
        four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=4)
        recent = (
            db.session.query(AIInsight)
            .filter(AIInsight.tipe == 'restok', AIInsight.dibuat_pada >= four_hours_ago)
            .order_by(AIInsight.dibuat_pada.desc())
            .first()
        )
        if recent:
            return {
                'insight': recent.konten,
                'sumber': recent.sumber,
                'dibuat_pada': recent.dibuat_pada.isoformat(),
            }

    plan = prediksi_service.restock_plan(today)
    metrics = {
        'total_barang': len(plan.get('barang', [])),
        'jumlah_barang_direstok': plan.get('jumlah_barang_direstok', 0),
        'total_unit_restock': plan.get('total_unit_restock', 0),
        'total_anggaran_restok_formatted': plan.get('total_anggaran_restok_formatted', '0'),
        'barang_kritis': plan.get('barang_kritis', []),
        'barang_dead_stock': plan.get('barang_dead_stock', []),
        'mape_gabungan': plan.get('mape_gabungan'),
        'jumlah_model_ml_digunakan': plan.get('jumlah_model_ml_digunakan', 0),
        'ringkasan_omzet': f"Penjualan 28 hari: {sum(p['unit'] for p in plan.get('tren_penjualan', []))} unit terjual",
    }

    result = local_nlu_service.generate_executive_insights(metrics)

    # Persist insight
    insight_record = AIInsight(
        tipe='restok',
        konten=result['insight'],
        sumber=result['sumber'],
    )
    db.session.add(insight_record)
    db.session.commit()

    return {
        'insight': insight_record.konten,
        'sumber': insight_record.sumber,
        'dibuat_pada': insight_record.dibuat_pada.isoformat(),
    }


def handle_chat_message(user_id, message_text):
    """Process a chat question from the user with context and store the exchange."""
    clean_text = message_text.strip()
    if not clean_text:
        return {'error': 'Pesan tidak boleh kosong.'}

    # Save user message
    user_msg = AIChatMessage(
        pengguna_id=user_id,
        role='user',
        pesan=clean_text,
        sumber='user',
    )
    db.session.add(user_msg)
    db.session.commit()

    # Load recent conversation history (last 8 messages)
    history_records = (
        db.session.query(AIChatMessage)
        .filter(AIChatMessage.pengguna_id == user_id)
        .order_by(AIChatMessage.dibuat_pada.desc())
        .limit(8)
        .all()
    )
    history_records.reverse()
    history = [{'role': m.role, 'pesan': m.pesan} for m in history_records if m.id != user_msg.id]

    # Gather live context
    store_context = get_live_store_context()

    # Query Local NLU engine
    ai_resp = local_nlu_service.ask_copilot(clean_text, history, store_context)

    # Save assistant response
    assistant_msg = AIChatMessage(
        pengguna_id=user_id,
        role='assistant',
        pesan=ai_resp['reply'],
        sumber=ai_resp['sumber'],
    )
    db.session.add(assistant_msg)
    db.session.commit()

    return {
        'reply': assistant_msg.pesan,
        'source': assistant_msg.sumber,
        'created_at': assistant_msg.dibuat_pada.isoformat(),
    }


def get_chat_history(limit=20, user_id=None):
    """Retrieve chat history for the Copilot interface."""
    records = (
        db.session.query(AIChatMessage)
        .filter(AIChatMessage.pengguna_id == user_id)
        .order_by(AIChatMessage.dibuat_pada.desc())
        .limit(limit)
        .all()
    )
    records.reverse()
    return [
        {
            'id': r.id,
            'role': r.role,
            'pesan': r.pesan,
            'sumber': r.sumber,
            'dibuat_pada': r.dibuat_pada.isoformat(),
        }
        for r in records
    ]


def get_market_basket_data():
    """Run market basket analysis and generate bundle promotion advice."""
    receipts = transaksi_repository.get_all_receipt_itemsets()
    all_items = barang_repository.list_all_items()
    item_names = {item.id: item.nama_barang for item in all_items}

    basket_results = analyze_market_baskets(receipts, item_names)
    advice_info = local_nlu_service.generate_market_basket_advice(
        basket_results['pasangan_populer'],
        basket_results['aturan_asosiasi'],
    )

    return {
        **basket_results,
        'ai_rekomendasi_bundling': advice_info['advice'],
        'sumber_ai': advice_info['sumber'],
    }


def get_cross_sell_for_cart(cart_item_ids):
    """Get complimentary product recommendations for current cart items."""
    if not cart_item_ids:
        return []
    receipts = transaksi_repository.get_all_receipt_itemsets()
    all_items = barang_repository.list_all_items()
    item_names = {item.id: item.nama_barang for item in all_items}
    basket_results = analyze_market_baskets(receipts, item_names)
    return get_cross_sell_suggestions(cart_item_ids, basket_results['aturan_asosiasi'])


def get_store_anomalies():
    """Detect inventory and sales anomalies using rules and Isolation Forest."""
    today = business_today()
    all_items = barang_repository.list_all_items()
    history_start = today - timedelta(days=28)
    sales = transaksi_repository.daily_sales_for_period(history_start, today)

    daily_sales = {}
    for row in sales:
        daily_sales.setdefault(row.barang_id, {})[row.tanggal] = int(row.total_harian)

    inventory_anomalies = detect_sales_anomalies(all_items, daily_sales, today)

    # Detect cashier transaction anomalies using Isolation Forest
    recent_transactions = transaksi_repository.get_recent_transactions_for_anomaly_detection(limit=100)
    tx_anomalies = detect_transaction_anomalies(recent_transactions)

    return inventory_anomalies + tx_anomalies
