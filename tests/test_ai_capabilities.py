import unittest
from unittest.mock import patch
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from app import create_app, db
from app.models import AIChatMessage, AIInsight, Barang, DetailTransaksi, Pengguna, TransaksiHeader
from algorithm.anomaly_detector import detect_sales_anomalies, detect_transaction_anomalies
from algorithm.local_nlu import LocalNLUEngine, get_local_nlu_engine
from algorithm.market_basket import analyze_market_baskets, get_cross_sell_suggestions
from algorithm.product_clustering import cluster_products
from algorithm.retail_optimizer import calculate_restock_priority
from algorithm.ses import peramalkan_ses
from algorithm.ml_forecast import peramalkan_random_forest
from app.services import ai_assistant_service, local_nlu_service
from app.services.ai_response import SYSTEM_INSTRUCTION, clean_response


class RetailAlgorithmsTestCase(unittest.TestCase):
    def test_anomaly_detector_rejects_nonpositive_lookback(self):
        with self.assertRaisesRegex(ValueError, 'lookback_days'):
            detect_sales_anomalies([], {}, date(2026, 11, 19), lookback_days=0)

    def test_anomaly_detector_identifies_stockout_and_dead_stock(self):
        today = date(2026, 11, 19)
        items = [
            {'id': 1, 'nama_barang': 'Kopi ABC', 'stok': 2, 'harga': Decimal('15000.00')},
            {'id': 2, 'nama_barang': 'Teh Celup', 'stok': 50, 'harga': Decimal('8000.00')},
            {'id': 3, 'nama_barang': 'Biskuit Kaleng', 'stok': 20, 'harga': Decimal('45000.00')},
        ]
        # Kopi ABC sells 4 units/day (stok 2 -> habis dalam 0.5 hari)
        daily_sales = {
            1: {today - timedelta(days=i): 4 for i in range(7)},
            2: {today - timedelta(days=i): 10 for i in range(7)},  # Spike
            3: {},  # Dead stock: stok 20, terjual 0
        }
        anomalies = detect_sales_anomalies(items, daily_sales, today)
        types = [a['tipe'] for a in anomalies]
        self.assertIn('rawan_habis', types)
        self.assertIn('dead_stock', types)

        rawan = next(a for a in anomalies if a['tipe'] == 'rawan_habis')
        self.assertEqual(rawan['barang_id'], 1)
        self.assertLessEqual(rawan['metrik']['sisa_hari'], 1.0)

        dead = next(a for a in anomalies if a['tipe'] == 'dead_stock')
        self.assertEqual(dead['barang_id'], 3)

    def test_isolation_forest_transaction_anomalies(self):
        # 10 regular transactions + 1 extreme bulk purchase anomaly
        transactions = [
            {'transaksi_id': f'TRX-{i}', 'tanggal': '2026-11-19', 'total_harga': 25000.0, 'total_item': 2, 'total_unit': 3}
            for i in range(1, 12)
        ]
        # Outlier
        transactions.append({
            'transaksi_id': 'TRX-OUTLIER',
            'tanggal': '2026-11-19',
            'total_harga': 2500000.0,
            'total_item': 20,
            'total_unit': 300,
        })
        anomalies = detect_transaction_anomalies(transactions)
        self.assertTrue(len(anomalies) > 0)
        outlier = next((a for a in anomalies if a['transaksi_id'] == 'TRX-OUTLIER'), None)
        self.assertIsNotNone(outlier)
        self.assertEqual(outlier['tipe'], 'transaksi_anomali_isolation_forest')

    def test_market_basket_and_cross_sell(self):
        # Receipts with Kopi (1) and Gula (2) frequently co-purchased
        receipts = [
            [1, 2], [1, 2], [1, 2], [1, 2],
            [1], [2], [3], [1, 3],
        ]
        names = {1: 'Kopi', 2: 'Gula', 3: 'Roti'}
        result = analyze_market_baskets(receipts, names, min_support_count=2)

        self.assertEqual(result['status'], 'analisis_tersedia')
        pairs = result['pasangan_populer']
        self.assertTrue(any(p['item_a_nama'] in ('Kopi', 'Gula') and p['item_b_nama'] in ('Kopi', 'Gula') for p in pairs))

        # Test cross sell suggestions for cart [1] (Kopi) -> should suggest Gula (2)
        suggestions = get_cross_sell_suggestions([1], result['aturan_asosiasi'])
        suggested_ids = [s['barang_id'] for s in suggestions]
        self.assertIn(2, suggested_ids)

    def test_product_clustering_kmeans(self):
        products = [
            {'barang_id': 1, 'nama_barang': 'Beras Super', 'stok': 10, 'harga': 75000, 'total_terjual_28h': 120},
            {'barang_id': 2, 'nama_barang': 'Minyak Goreng', 'stok': 15, 'harga': 34000, 'total_terjual_28h': 90},
            {'barang_id': 3, 'nama_barang': 'Gula Pasir', 'stok': 20, 'harga': 16000, 'total_terjual_28h': 40},
            {'barang_id': 4, 'nama_barang': 'Kecap Manis', 'stok': 25, 'harga': 12000, 'total_terjual_28h': 15},
            {'barang_id': 5, 'nama_barang': 'Piring Keramik', 'stok': 30, 'harga': 45000, 'total_terjual_28h': 0},
        ]
        res = cluster_products(products)
        self.assertEqual(res['status'], 'sukses_kmeans')
        self.assertEqual(res['total_produk'], 5)
        self.assertIn('FAST_MOVING', res['ringkasan_klaster'])
        self.assertIn('SLOW_MOVING', res['ringkasan_klaster'])

        # Dead stock item should be labeled
        piring = next(it for it in res['klaster'] if it['barang_id'] == 5)
        self.assertEqual(piring['klaster_tag'], 'DEAD_STOCK')

    def test_retail_optimizer_priority_and_budget(self):
        # Case 1: Stock 0 with active daily demand -> P1_KRITIS
        crit = calculate_restock_priority(stok=0, prediksi_harian=5.0, rekomendasi_restok=35, harga=10000, total_terjual_28h=140)
        self.assertEqual(crit['tier_prioritas'], 'P1_KRITIS')
        self.assertGreaterEqual(crit['skor_prioritas'], 90)
        self.assertEqual(crit['estimasi_modal_restok'], Decimal('350000.00'))

        # Case 2: Stock ample (50) for 1/day -> P4_CUKUP
        safe = calculate_restock_priority(stok=50, prediksi_harian=1.0, rekomendasi_restok=0, harga=5000, total_terjual_28h=28)
        self.assertEqual(safe['tier_prioritas'], 'P4_CUKUP')
        self.assertEqual(safe['estimasi_modal_restok'], Decimal('0.00'))

    def test_empirical_evaluation_metrics_forecast(self):
        # Test SES computes MAPE, MAE, and RMSE
        history = [5, 6, 7, 5, 6, 8, 7, 6, 5, 7, 8, 6, 7, 6, 5, 8, 7, 6, 7, 8, 6]
        res = peramalkan_ses(history, 7)
        self.assertIn('mape_persen', res)
        self.assertIn('mae', res)
        self.assertIn('rmse', res)
        self.assertIsNotNone(res['mape_persen'])
        self.assertIsNotNone(res['mae'])
        self.assertIsNotNone(res['rmse'])


class LocalNLUServiceAndAiTestCase(unittest.TestCase):
    def test_response_cleaner_removes_markdown_and_decorative_emoji(self):
        cleaned = clean_response('### Halo **Pak** 👋\n\n- Silakan lihat `stok` __hari ini__.')
        self.assertEqual(cleaned, 'Halo Pak\n\nSilakan lihat stok hari ini.')
        self.assertNotRegex(cleaned, r'[#*_`]|--')
        self.assertIn('bahasa Indonesia', SYSTEM_INSTRUCTION)

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(__file__).resolve().parents[1] / '.test_ai_tmp'
        cls.temp_dir.mkdir(exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.rmdir()

    def setUp(self):
        self.database_path = self.temp_dir / f'{self.id().split(".")[-1]}.db'
        self.app = create_app({
            'TESTING': True,
            'SECRET_KEY': 'test-ai-secret-key-for-regression-tests-only',
            'API_TOKEN': 'a' * 40,
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{self.database_path}',
        })
        with self.app.app_context():
            db.create_all()
            b1 = Barang(nama_barang='Beras Premium 5kg', stok=3, harga=Decimal('75000.00'))
            b2 = Barang(nama_barang='Minyak Goreng 2L', stok=20, harga=Decimal('34000.00'))
            db.session.add_all([b1, b2])
            db.session.commit()
            self.b1_id = b1.id
            self.b2_id = b2.id

        self.client = self.app.test_client()
        self.headers = {'Authorization': f'Bearer {"a" * 40}'}

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if self.database_path.exists():
            self.database_path.unlink()

    def test_local_nlu_classification_and_response(self):
        engine = get_local_nlu_engine()

        # Test intent classification
        intent_stock, score_stock = engine.classify_intent("Barang apa yang stoknya hampir habis?")
        self.assertEqual(intent_stock, 'stok_kritis')
        self.assertGreater(score_stock, 0.2)

        intent_omzet, score_omzet = engine.classify_intent("Berapa omzet transaksi kasir hari ini?")
        self.assertEqual(intent_omzet, 'omzet_hari_ini')
        self.assertGreater(score_omzet, 0.2)

        # Test entity extraction and response generation
        ctx = {
            'all_items': [{'nama_barang': 'Beras Premium 5kg', 'stok_saat_ini': 3, 'harga': 75000, 'total_terjual_28_hari': 45}],
            'penjualan_hari_ini_omzet': '350,000.00',
            'total_barang': 2,
        }
        resp = engine.generate_response("Bagaimana stok Beras Premium 5kg?", ctx)
        self.assertIn('Beras Premium 5kg', resp)
        self.assertIn('3 unit', resp)
        self.assertNotRegex(resp, r'[#*_`]|--')

    def test_ai_api_insights_restok_endpoint(self):
        response = self.client.get('/api/ai/insights/restok', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn('insight', response.json)
        self.assertEqual(response.json['sumber'], 'local_ml')
        self.assertNotRegex(response.json['insight'], r'[#*_`]|--')

    def test_ai_api_chat_endpoint(self):
        response = self.client.post('/api/ai/chat', headers=self.headers, json={
            'message': 'Barang apa yang stoknya paling sedikit?'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('reply', response.json)
        self.assertEqual(response.json['source'], 'local_nlu')
        self.assertNotRegex(response.json['reply'], r'[#*_`]|--')

        # Verify chat history endpoint returns stored message
        hist_resp = self.client.get('/api/ai/chat/history', headers=self.headers)
        self.assertEqual(hist_resp.status_code, 200)
        messages = hist_resp.json['messages']
        self.assertGreaterEqual(len(messages), 2)  # 1 user + 1 assistant

    def test_ai_chat_endpoint_sanitizes_provider_output(self):
        with patch(
            'app.routes.ai.ai_assistant_service.handle_chat_message',
            return_value={'reply': '### Halo **Pak** 👋\n\n- Cek `stok` __hari ini__.', 'source': 'local_nlu'},
        ):
            response = self.client.post('/api/ai/chat', headers=self.headers, json={'message': 'Halo'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['reply'], 'Halo Pak\n\nCek stok hari ini.')

    def test_ai_api_basket_and_anomali_endpoints(self):
        # Basket analysis
        basket_resp = self.client.get('/api/ai/basket-analysis', headers=self.headers)
        self.assertEqual(basket_resp.status_code, 200)
        self.assertIn('aturan_asosiasi', basket_resp.json)
        self.assertNotRegex(basket_resp.json['ai_rekomendasi_bundling'], r'[#*_`]|--')

        # Cross sell
        cs_resp = self.client.post('/api/ai/cross-sell', headers=self.headers, json={
            'cart_item_ids': [self.b1_id]
        })
        self.assertEqual(cs_resp.status_code, 200)
        self.assertIn('suggestions', cs_resp.json)

        # Anomali
        anom_resp = self.client.get('/api/ai/anomali', headers=self.headers)
        self.assertEqual(anom_resp.status_code, 200)
        self.assertIn('anomali', anom_resp.json)

    def test_ai_api_clustering_endpoint(self):
        clust_resp = self.client.get('/api/ai/clustering', headers=self.headers)
        self.assertEqual(clust_resp.status_code, 200)
        self.assertIn('klaster', clust_resp.json)
        self.assertIn('total_produk', clust_resp.json)


if __name__ == '__main__':
    unittest.main()
