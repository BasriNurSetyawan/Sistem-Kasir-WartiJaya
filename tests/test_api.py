import unittest
import re
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from app import create_app, db
from app.business_time import business_today
from app.models import (
    AIChatMessage, Barang, DetailBelanja, DetailTransaksi, Pengguna, RekapBelanja,
    Transaksi, TransaksiHeader,
)
from app.services.peramalan_penjualan import peramalkan_ses, proyeksikan_permintaan
from werkzeug.security import generate_password_hash


class ApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(__file__).resolve().parents[1] / '.test_tmp'
        cls.temp_dir.mkdir(exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.rmdir()

    def setUp(self):
        self.database_path = self.temp_dir / f'{self.id().split(".")[-1]}.db'
        self.app = create_app({
            'TESTING': True,
            'SECRET_KEY': 'test-secret-key-for-regression-tests-only',
            'API_TOKEN': 't' * 40,
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{self.database_path}',
        })
        with self.app.app_context():
            db.create_all()
            db.session.add_all([
                Pengguna(username='admin-test', password_hash=generate_password_hash('Admin-test-password-123!'), role='admin'),
                Pengguna(username='cashier-test', password_hash=generate_password_hash('Cashier-test-password-123!'), role='kasir'),
            ])
            db.session.commit()
        self.client = self.app.test_client()
        self.headers = {'Authorization': f'Bearer {"t" * 40}'}

    def test_health_check_reports_database_status(self):
        response = self.client.get('/healthz')
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json, {'status': 'ok', 'database': 'ok'})

    def test_create_app_rejects_short_secret_key(self):
        with self.assertRaisesRegex(RuntimeError, 'minimal 32 karakter'):
            create_app({'SECRET_KEY': 'weak', 'API_TOKEN': 't' * 40})

    def test_create_app_rejects_unknown_business_timezone(self):
        with self.assertRaisesRegex(RuntimeError, 'BUSINESS_TIMEZONE'):
            create_app({
                'SECRET_KEY': 'test-secret-key-for-regression-tests-only',
                'API_TOKEN': 't' * 40,
                'BUSINESS_TIMEZONE': 'Invalid/Not_A_Zone',
            })

    def test_integer_fields_follow_mysql_signed_integer_range(self):
        too_large = self.client.post('/api/barang', json={
            'nama_barang': 'Stok melebihi rentang MySQL',
            'stok': 2_147_483_648,
            'harga': 1,
        }, headers=self.headers)
        self.assertEqual(too_large.status_code, 400)

    def test_ui_rejects_non_string_csrf_token_without_server_error(self):
        response = self.client.post('/login', json={'csrf_token': [], 'username': 'x'})
        self.assertEqual(response.status_code, 400)

    def test_ai_chat_rejects_non_text_and_oversized_messages(self):
        for message in (None, 12, {'text': 'hello'}, 'x' * 2001):
            response = self.client.post('/api/ai/chat', json={'message': message}, headers=self.headers)
            self.assertEqual(response.status_code, 400)

    def test_cross_sell_rejects_invalid_cart_ids(self):
        for cart_item_ids in ([True], [[1]], [-1], [1] * 101):
            response = self.client.post(
                '/api/ai/cross-sell', json={'cart_item_ids': cart_item_ids}, headers=self.headers
            )
            self.assertEqual(response.status_code, 400)

    def test_cross_sell_ui_rejects_invalid_cart_ids(self):
        self.login_ui('admin-test', 'Admin-test-password-123!')
        page = self.client.get('/transaksi')
        csrf = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()
        response = self.client.post('/ai/cross-sell', json={'cart_item_ids': [[1]], 'csrf_token': csrf},
                                   headers={'X-CSRF-Token': csrf})
        self.assertEqual(response.status_code, 400)
        valid = self.client.post('/ai/cross-sell', json={'cart_item_ids': [1]},
                                 headers={'X-CSRF-Token': csrf})
        self.assertEqual(valid.status_code, 200, valid.json)

    def test_cross_sell_dom_rendering_uses_text_nodes(self):
        source = (Path(__file__).resolve().parents[1] / 'app' / 'static' / 'transaksi.js').read_text()
        self.assertNotIn('crossSellItems.innerHTML', source)
        self.assertIn('name.textContent = suggestion.nama_barang', source)
        self.assertIn('reason.textContent = suggestion.alasan', source)
        self.assertIn("'X-CSRF-Token': csrfToken", source)

    def test_legacy_sales_do_not_create_fake_same_day_baskets(self):
        from app.repositories.transaksi_repository import get_all_receipt_itemsets

        first_id = self.create_item(name='Satu')
        second_id = self.create_item(name='Dua')
        with self.app.app_context():
            db.session.add_all([
                Transaksi(barang_id=first_id, jumlah_terjual=1, harga_satuan=Decimal('1.00'), tanggal=business_today()),
                Transaksi(barang_id=second_id, jumlah_terjual=1, harga_satuan=Decimal('1.00'), tanggal=business_today()),
            ])
            db.session.commit()
            baskets = get_all_receipt_itemsets()
        self.assertIn({first_id}, baskets)
        self.assertIn({second_id}, baskets)
        self.assertFalse(any(len(basket) > 1 for basket in baskets))

    def test_legacy_sales_remain_in_basket_analysis_after_modern_receipts_exist(self):
        from app.repositories.transaksi_repository import get_all_receipt_itemsets

        first_id = self.create_item(name='Beras')
        second_id = self.create_item(name='Minyak')
        legacy_id = self.create_item(name='Teh')
        with self.app.app_context():
            for _ in range(5):
                header = TransaksiHeader(tanggal=business_today())
                db.session.add(header)
                db.session.flush()
                db.session.add_all([
                    DetailTransaksi(
                        transaksi_id=header.id, barang_id=item_id,
                        jumlah_terjual=1, harga_satuan=Decimal('1.00'),
                    )
                    for item_id in (first_id, second_id)
                ])
            db.session.add(Transaksi(
                barang_id=legacy_id, jumlah_terjual=1,
                harga_satuan=Decimal('1.00'), tanggal=business_today(),
            ))
            db.session.commit()
            baskets = get_all_receipt_itemsets()
        self.assertEqual(len(baskets), 6)
        self.assertIn({first_id, second_id}, baskets)
        self.assertIn({legacy_id}, baskets)

    def test_ui_chat_history_is_scoped_to_logged_in_user(self):
        self.login_ui('admin-test', 'Admin-test-password-123!')
        with self.app.app_context():
            admin = Pengguna.query.filter_by(username='admin-test').one()
            cashier = Pengguna.query.filter_by(username='cashier-test').one()
            db.session.add_all([
                AIChatMessage(
                    pengguna_id=admin.id, role='user', pesan='admin-private', sumber='user'
                ),
                AIChatMessage(
                    pengguna_id=cashier.id, role='user', pesan='cashier-private', sumber='user'
                ),
            ])
            db.session.commit()
        history = self.client.get('/ai/chat/history')
        self.assertEqual(history.status_code, 200)
        messages = history.json['messages']
        self.assertIn('admin-private', [message['pesan'] for message in messages])
        self.assertNotIn('cashier-private', [message['pesan'] for message in messages])

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if self.database_path.exists():
            self.database_path.unlink()

    def create_item(self, *, stock=10, price=12.50, name='Kopi'):
        response = self.client.post('/api/barang', json={
            'nama_barang': name,
            'stok': stock,
            'harga': price,
        }, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.json)
        return response.json['id']

    def login_ui(self, username, password):
        page = self.client.get('/login')
        token = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()
        response = self.client.post('/login', data={
            'csrf_token': token,
            'username': username,
            'password': password,
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        return response

    def test_token_is_required_for_all_routes(self):
        self.assertEqual(self.client.get('/api/barang').status_code, 401)
        response = self.client.get('/api/rekap/harian', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['dari'], business_today().isoformat())

    def test_daily_revenue_uses_sale_time_price_snapshot(self):
        item_id = self.create_item(stock=5, price=12.50)
        today = business_today()
        yesterday = today - timedelta(days=1)
        for quantity, day in ((1, yesterday), (2, today)):
            response = self.client.post('/api/transaksi', json={
                'barang_id': item_id,
                'jumlah_terjual': quantity,
                'tanggal': day.isoformat(),
            }, headers=self.headers)
            self.assertEqual(response.status_code, 201, response.json)

        with self.app.app_context():
            item = db.session.get(Barang, item_id)
            item.harga = Decimal('100.00')
            db.session.commit()

        report = self.client.get(
            f'/api/rekap/harian?dari={yesterday.isoformat()}&sampai={today.isoformat()}',
            headers=self.headers,
        )
        self.assertEqual(report.status_code, 200, report.json)
        self.assertEqual(report.json['jumlah_terjual'], 3)
        self.assertEqual(report.json['total_penghasilan'], '37.50')
        self.assertEqual(report.json['harian'][0]['total_penghasilan'], '12.50')
        self.assertEqual(report.json['harian'][1]['total_penghasilan'], '25.00')

    def test_inventory_is_paginated_and_price_has_two_decimal_places(self):
        self.create_item(name='A', price=1)
        self.create_item(name='B', price=2)
        self.create_item(name='C', price=3)
        response = self.client.get('/api/barang?page=2&per_page=2', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['total'], 3)
        self.assertEqual(len(response.json['items']), 1)
        self.assertEqual(response.json['items'][0]['harga'], '3.00')

        invalid_price = self.client.post('/api/barang', json={
            'nama_barang': 'Fractional price',
            'stok': 1,
            'harga': 1.005,
        }, headers=self.headers)
        self.assertEqual(invalid_price.status_code, 400)

    def test_sale_validation_and_stock_are_enforced(self):
        item_id = self.create_item(stock=1)
        invalid = self.client.post('/api/transaksi', json={
            'barang_id': item_id,
            'jumlah_terjual': 2,
        }, headers=self.headers)
        self.assertEqual(invalid.status_code, 400)

        future = self.client.post('/api/transaksi', json={
            'barang_id': item_id,
            'jumlah_terjual': 1,
            'tanggal': (business_today() + timedelta(days=1)).isoformat(),
        }, headers=self.headers)
        self.assertEqual(future.status_code, 400)

    def test_cart_sale_creates_header_and_details_atomically(self):
        first_id = self.create_item(stock=5, name='Beras')
        second_id = self.create_item(stock=2, name='Minyak')

        rejected = self.client.post('/api/transaksi/cart', json={
            'items': [
                {'barang_id': first_id, 'jumlah_terjual': 2},
                {'barang_id': second_id, 'jumlah_terjual': 3},
            ],
        }, headers=self.headers)
        self.assertEqual(rejected.status_code, 400)
        with self.app.app_context():
            self.assertEqual(db.session.get(Barang, first_id).stok, 5)
            self.assertEqual(db.session.get(Barang, second_id).stok, 2)
            self.assertEqual(TransaksiHeader.query.count(), 0)
            self.assertEqual(DetailTransaksi.query.count(), 0)

        saved = self.client.post('/api/transaksi/cart', json={
            'items': [
                {'barang_id': first_id, 'jumlah_terjual': 2},
                {'barang_id': second_id, 'jumlah_terjual': 1},
            ],
        }, headers=self.headers)
        self.assertEqual(saved.status_code, 201, saved.json)
        self.assertEqual(saved.json['jumlah_baris'], 2)
        self.assertEqual(saved.json['sisa_stok'][str(first_id)], 3)
        self.assertEqual(saved.json['sisa_stok'][str(second_id)], 1)
        with self.app.app_context():
            self.assertEqual(db.session.get(Barang, first_id).stok, 3)
            self.assertEqual(db.session.get(Barang, second_id).stok, 1)
            self.assertEqual(TransaksiHeader.query.count(), 1)
            self.assertEqual(DetailTransaksi.query.count(), 2)

        report = self.client.get('/api/rekap/harian', headers=self.headers)
        self.assertEqual(report.status_code, 200, report.json)
        self.assertEqual(report.json['total_transaksi'], 1)
        self.assertEqual(report.json['jumlah_terjual'], 3)

    def test_restock_forecast_uses_daily_history_and_current_stock(self):
        item_id = self.create_item(stock=50, name='Beras')
        today = business_today()
        for offset in range(6, -1, -1):
            response = self.client.post('/api/transaksi', json={
                'barang_id': item_id,
                'jumlah_terjual': 2,
                'tanggal': (today - timedelta(days=offset)).isoformat(),
            }, headers=self.headers)
            self.assertEqual(response.status_code, 201, response.json)
        with self.app.app_context():
            item = db.session.get(Barang, item_id)
            item.stok = 2
            db.session.commit()

        plan = self.client.get('/api/prediksi/restok', headers=self.headers)
        self.assertEqual(plan.status_code, 200, plan.json)
        self.assertEqual(plan.json['periode']['jumlah_hari'], 7)
        self.assertEqual(plan.json['periode']['mulai'], (today + timedelta(days=1)).isoformat())
        result = next(row for row in plan.json['barang'] if row['barang_id'] == item_id)
        self.assertEqual(result['total_terjual_28_hari'], 14)
        self.assertEqual(result['prediksi_penjualan'], 14)
        self.assertEqual(result['stok_saat_ini'], 2)
        self.assertEqual(result['rekomendasi_restock'], 12)
        self.assertEqual(result['status'], 'perlu_restock')
        self.assertIsNone(plan.json['mape_gabungan'])
        self.assertEqual(plan.json['jumlah_sampel_mape'], 0)
        self.assertNotIn('_mape_persen_raw', result)

        single = self.client.get(
            f'/api/prediksi/{item_id}', headers=self.headers
        )
        self.assertEqual(single.status_code, 200, single.json)
        self.assertEqual(single.json['prediksi_penjualan'], 14)
        self.assertEqual(single.json['metode_peramalan'], 'Single Exponential Smoothing (SES)')
        self.assertEqual(single.json['alpha'], '0.01')
        self.assertIsNone(single.json['mape_persen'])
        self.assertEqual(single.json['jumlah_data_uji'], 0)

        with self.app.app_context():
            db.session.get(Barang, item_id).stok = 20
            db.session.commit()
        enough_stock = self.client.get('/api/prediksi/restok', headers=self.headers)
        item = next(row for row in enough_stock.json['barang'] if row['barang_id'] == item_id)
        self.assertEqual(item['rekomendasi_restock'], 0)
        self.assertEqual(item['status'], 'stok_cukup')

    def test_restock_forecast_fills_days_without_transactions_with_zero(self):
        item_id = self.create_item(stock=2, name='Gula')
        today = business_today()
        sale = self.client.post('/api/transaksi', json={
            'barang_id': item_id,
            'jumlah_terjual': 2,
            'tanggal': (today - timedelta(days=2)).isoformat(),
        }, headers=self.headers)
        self.assertEqual(sale.status_code, 201, sale.json)
        plan = self.client.get('/api/prediksi/restok', headers=self.headers)
        item = next(row for row in plan.json['barang'] if row['barang_id'] == item_id)
        self.assertEqual(item['hari_histori'], 3)
        self.assertEqual(item['total_terjual_28_hari'], 2)
        self.assertEqual(item['rata_rata_harian'], '0.67')
        self.assertEqual(item['prediksi_penjualan'], 7)
        self.assertEqual(item['alpha'], '0.30')
        self.assertIsNone(item['mape_persen'])
        self.assertEqual(item['jumlah_data_uji'], 0)
        self.assertTrue(item['histori_terbatas'])

    def test_restock_plan_marks_items_without_recent_sales(self):
        item_id = self.create_item(stock=0, name='Produk baru')
        response = self.client.get('/api/prediksi/restok', headers=self.headers)
        self.assertEqual(response.status_code, 200, response.json)
        item = next(row for row in response.json['barang'] if row['barang_id'] == item_id)
        self.assertEqual(item['status'], 'tanpa_data_terbaru')
        self.assertIsNone(item['rekomendasi_restock'])
        self.assertEqual(response.json['jumlah_barang_direstok'], 0)

    def test_demand_projection_rounds_restock_need_up(self):
        average, forecast = proyeksikan_permintaan([1, 0, 2], 3)
        self.assertEqual(average, Decimal(1))
        self.assertEqual(forecast, 3)
        _, rounded_up = proyeksikan_permintaan([1, 0], 3)
        self.assertEqual(rounded_up, 2)
        with self.assertRaises(ValueError):
            proyeksikan_permintaan([], 7)

    def test_ses_uses_default_alpha_when_history_is_too_short_for_tuning(self):
        result = peramalkan_ses([10, 8, 12, 13], 7)
        self.assertEqual(result['alpha'], Decimal('0.30'))
        self.assertEqual(result['status_alpha'], 'default_histori_terbatas')
        self.assertEqual(result['jumlah_data_latih'], 4)
        self.assertEqual(result['jumlah_data_uji'], 0)
        self.assertIsNone(result['mape_persen'])
        self.assertEqual(result['prediksi_periode'], 78)

    def test_ses_backtest_uses_matching_seven_day_forecast_horizon(self):
        result = peramalkan_ses([5] * 15, 7)
        self.assertEqual(result['jumlah_data_uji'], 2)
        self.assertEqual(result['jumlah_data_uji_mape'], 2)
        self.assertEqual(result['mape_persen'], Decimal('0'))

    def test_ses_tunes_alpha_only_after_minimum_history_is_available(self):
        result = peramalkan_ses([10, 8, 12, 13, 11, 9, 12], 7)
        self.assertEqual(result['status_alpha'], 'terpilih_mape_data_latih')
        self.assertEqual(result['alpha'], Decimal('0.01'))

    def test_ses_counts_zero_total_backtest_windows_outside_mape(self):
        result = peramalkan_ses([2] * 7 + [0] * 7, 7)
        self.assertEqual(result['jumlah_data_uji'], 1)
        self.assertEqual(result['jumlah_data_uji_nol'], 1)
        self.assertIsNone(result['mape_persen'])

    def test_ses_rejects_nonpositive_backtest_window_limit(self):
        for limit in (0, -1, True):
            with self.subTest(limit=limit), self.assertRaisesRegex(ValueError, 'max_backtest_windows'):
                peramalkan_ses([1] * 20, 7, max_backtest_windows=limit)

    def test_api_reports_horizon_aligned_mape_for_complete_history(self):
        item_id = self.create_item(stock=100, name='Air Mineral')
        today = business_today()
        with self.app.app_context():
            db.session.add_all([
                Transaksi(
                    barang_id=item_id,
                    jumlah_terjual=3,
                    harga_satuan=Decimal('1500.00'),
                    tanggal=today - timedelta(days=offset),
                )
                for offset in range(28)
            ])
            db.session.commit()

        response = self.client.get('/api/prediksi/restok', headers=self.headers)
        self.assertEqual(response.status_code, 200, response.json)
        row = next(item for item in response.json['barang'] if item['barang_id'] == item_id)
        self.assertEqual(row['prediksi_penjualan'], 21)
        self.assertEqual(row['mape_persen'], '0.00')
        self.assertEqual(row['jumlah_data_uji'], 15)
        self.assertEqual(response.json['mape_gabungan'], '0.00')
        self.assertEqual(response.json['jumlah_sampel_mape'], 15)
        self.assertEqual(len(response.json['tren_penjualan']), 28)
        self.assertEqual(row['total_terjual_120_hari'], 84)
        self.assertEqual(row['buffer_adaptif'], 0)
        self.assertEqual(row['stok_target_7_hari'], 21)
        self.assertEqual(row['tingkat_risiko'], 'risiko_rendah')

    def test_ses_adapts_buffer_and_explains_stock_risk(self):
        result = peramalkan_ses(list(range(1, 29)), 7)
        self.assertEqual(result['alpha'], Decimal('1'))
        self.assertEqual(result['prediksi_periode'], 196)
        self.assertEqual(result['buffer_adaptif'], 28)
        self.assertEqual(result['status_buffer'], 'berbasis_persentil_galat_75')

        item_id = self.create_item(stock=190, name='Minyak Goreng')
        today = business_today()
        with self.app.app_context():
            db.session.add_all([
                Transaksi(
                    barang_id=item_id,
                    jumlah_terjual=quantity,
                    harga_satuan=Decimal('18000.00'),
                    tanggal=today - timedelta(days=27 - index),
                )
                for index, quantity in enumerate(range(1, 29))
            ])
            db.session.commit()

        response = self.client.get('/api/prediksi/restok', headers=self.headers)
        row = next(item for item in response.json['barang'] if item['barang_id'] == item_id)
        self.assertEqual(row['stok_target_7_hari'], 224)
        self.assertEqual(row['rekomendasi_restock'], 34)
        self.assertEqual(row['tingkat_risiko'], 'risiko_tinggi')
        self.assertIn('buffer adaptif 28 unit', row['alasan_rekomendasi'])

    def test_ses_keeps_zero_demand_in_model_but_excludes_it_from_mape(self):
        result = peramalkan_ses([2, 0, 0], 7)
        self.assertEqual(result['alpha'], Decimal('0.30'))
        self.assertIsNone(result['mape_persen'])
        self.assertEqual(result['jumlah_data_uji_mape'], 0)
        self.assertEqual(result['jumlah_data_uji'], 0)
        self.assertEqual(result['prediksi_periode'], 7)

    def test_api_product_crud_preserves_sales_history(self):
        item_id = self.create_item(stock=4)
        updated = self.client.put(f'/api/barang/{item_id}', json={
            'nama_barang': 'Kopi Baru', 'stok': 6, 'harga': 13500,
        }, headers=self.headers)
        self.assertEqual(updated.status_code, 200)
        sale = self.client.post('/api/transaksi', json={
            'barang_id': item_id, 'jumlah_terjual': 1,
        }, headers=self.headers)
        self.assertEqual(sale.status_code, 201)
        blocked_delete = self.client.delete(f'/api/barang/{item_id}', headers=self.headers)
        self.assertEqual(blocked_delete.status_code, 409)

    def test_purchase_ledgers_are_separate_and_readable(self):
        today = business_today()
        with self.app.app_context():
            db.session.add(RekapBelanja(
                outlet='Outlet A', tanggal_acuan=today, tanggal_selesai=today,
                cakupan='harian', keterangan_tanggal=today.strftime('%d-%m-%Y'),
                total=Decimal('100.00'), source_file='sample.xlsx',
                source_sha256='a' * 64, source_sheet='Ringkasan', source_row=2,
            ))
            db.session.add(DetailBelanja(
                outlet='Outlet A', tanggal=today, nama_barang='Tepung',
                jumlah_asli='2 kg', harga_total=Decimal('100.00'),
                kemungkinan_duplikat=False, source_file='sample.xlsx',
                source_sha256='a' * 64, source_sheet='Detail Belanja', source_row=2,
            ))
            db.session.commit()

        summary = self.client.get('/api/belanja/rekap', headers=self.headers)
        details = self.client.get('/api/belanja/detail', headers=self.headers)
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(details.status_code, 200)
        self.assertEqual(summary.json['total'], 1)
        self.assertEqual(details.json['items'][0]['nama_barang'], 'Tepung')
        self.assertEqual(details.json['items'][0]['kemungkinan_duplikat'], False)

    def test_admin_can_manage_products_and_cashier_is_limited_to_read_and_sales(self):
        self.assertEqual(self.client.get('/').status_code, 302)
        self.login_ui('admin-test', 'Admin-test-password-123!')
        for path in ('/', '/barang', '/transaksi', '/rekap', '/belanja', '/prediksi', '/pengguna'):
            page = self.client.get(path)
            self.assertEqual(page.status_code, 200, path)
            self.assertIn(b'Toko Warti Jaya', page.data, path)
        prediction_page = self.client.get('/prediksi').data
        self.assertNotIn(b'name="alpha"', prediction_page)
        self.assertNotIn(b'Executive AI Insights', prediction_page)
        self.assertNotIn(b'Ringkasan Eksekutif Inventori &amp; Pengadaan', prediction_page)
        self.assertNotIn(b'refresh_ai', prediction_page)
        self.assertIn(b'Selisih prediksi dalam persen (makin kecil makin akurat)', prediction_page)
        self.assertIn(b'Rata-rata melesetnya jumlah unit barang', prediction_page)
        self.assertIn(b'Tingkat penyimpangan saat terjadi selisih besar', prediction_page)
        self.assertNotIn(b'rerata galat persentase', prediction_page)
        self.assertNotIn(b'rerata galat absolut', prediction_page)
        self.assertNotIn(b'akar rerata kuadrat galat', prediction_page)
        token_match = re.search(rb'name="csrf_token" value="([^"]+)"', self.client.get('/barang').data)
        csrf = token_match.group(1).decode()
        created = self.client.post('/barang', data={
            'csrf_token': csrf,
            'nama_barang': 'Teh',
            'stok': '8',
            'harga': '2500.00',
        })
        self.assertEqual(created.status_code, 302)
        with self.app.app_context():
            item = Barang.query.order_by(Barang.id.desc()).first()
            item_id = item.id
        edit = self.client.get(f'/barang/{item_id}/edit')
        self.assertEqual(edit.status_code, 200)
        csrf = re.search(rb'name="csrf_token" value="([^"]+)"', edit.data).group(1).decode()
        self.client.post(f'/barang/{item_id}/edit', data={
            'csrf_token': csrf,
            'nama_barang': 'Teh Hijau',
            'stok': '7',
            'harga': '3000.00',
        })
        with self.app.app_context():
            self.assertEqual(db.session.get(Barang, item_id).nama_barang, 'Teh Hijau')
        csrf = re.search(rb'name="csrf_token" value="([^"]+)"', self.client.get('/barang').data).group(1).decode()
        deleted = self.client.post(f'/barang/{item_id}/hapus', data={'csrf_token': csrf})
        self.assertEqual(deleted.status_code, 302)
        with self.app.app_context():
            self.assertIsNone(db.session.get(Barang, item_id))

        item_id = self.create_item(stock=2, price=2500, name='Susu')
        self.client.post('/logout', data={'csrf_token': csrf})
        self.login_ui('cashier-test', 'Cashier-test-password-123!')
        page = self.client.get('/barang')
        self.assertEqual(page.status_code, 200)
        csrf = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()
        self.assertEqual(self.client.post('/barang', data={
            'csrf_token': csrf, 'nama_barang': 'Rahasia', 'stok': '1', 'harga': '10'
        }).status_code, 403)
        self.assertEqual(self.client.get('/pengguna').status_code, 403)
        self.assertEqual(self.client.get('/barang/1/edit').status_code, 403)
        sale = self.client.post('/transaksi', data={
            'csrf_token': csrf, 'barang_id': str(item_id), 'nama_barang': 'Susu', 'jumlah_terjual': '1',
            'tanggal': business_today().isoformat(),
        })
        self.assertEqual(sale.status_code, 302)

    def test_login_rejects_invalid_csrf_and_last_admin_cannot_be_demoted(self):
        self.assertEqual(self.client.post('/login', data={
            'username': 'admin-test', 'password': 'Admin-test-password-123!',
        }).status_code, 400)
        self.login_ui('admin-test', 'Admin-test-password-123!')
        page = self.client.get('/pengguna')
        csrf = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()
        with self.app.app_context():
            admin = Pengguna.query.filter_by(username='admin-test').one()
            admin2 = Pengguna(username='admin-second', password_hash=generate_password_hash('Admin-second-password-123!'), role='admin')
            db.session.add(admin2)
            db.session.commit()
            admin2_id = admin2.id
        self.assertEqual(self.client.post(f'/pengguna/{admin2_id}/peran', data={
            'csrf_token': csrf, 'role': 'kasir',
        }).status_code, 302)
        # The active administrator count stays at one after the guarded change.
        with self.app.app_context():
            self.assertEqual(Pengguna.query.filter_by(role='admin', aktif=True).count(), 1)
            admin_id = Pengguna.query.filter_by(username='admin-test').one().id
            from app.repositories.pengguna_repository import LastActiveAdminError
            from app.services import pengguna_service
            with self.assertRaises(LastActiveAdminError):
                pengguna_service.set_active(admin_id, False)
            with self.assertRaises(LastActiveAdminError):
                pengguna_service.set_role(admin_id, 'kasir')
            db.session.expire_all()
            self.assertTrue(db.session.get(Pengguna, admin_id).aktif)

    def test_transaction_product_suggestions_require_login_and_match_catalog(self):
        self.assertEqual(self.client.get('/transaksi/saran-barang?q=kopi').status_code, 302)
        self.login_ui('admin-test', 'Admin-test-password-123!')
        available_id = self.create_item(stock=4, name='Kopi Arabika')
        empty_id = self.create_item(stock=0, name='Kopi Robusta')

        response = self.client.get('/transaksi/saran-barang?q=kOpI')
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(
            [item['id'] for item in response.json['items']],
            [available_id, empty_id],
        )
        self.assertEqual(response.json['items'][1]['stok'], 0)

        literal_percent = self.client.get('/transaksi/saran-barang?q=%25')
        self.assertEqual(literal_percent.json['items'], [])

        page = self.client.get('/transaksi')
        self.assertIn(b'role="combobox"', page.data)
        self.assertIn(b'product-suggestions', page.data)

    def test_transaction_rejects_unselected_or_mismatched_product_name(self):
        item_id = self.create_item(stock=3, name='Teh Melati')
        self.login_ui('admin-test', 'Admin-test-password-123!')
        page = self.client.get('/transaksi')
        csrf = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()

        for data in (
            {'barang_id': '', 'nama_barang': 'Teh Melati'},
            {'barang_id': str(item_id), 'nama_barang': 'Teh Hijau'},
        ):
            response = self.client.post('/transaksi', data={
                'csrf_token': csrf,
                **data,
                'jumlah_terjual': '1',
                'tanggal': business_today().isoformat(),
            })
            self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(db.session.get(Barang, item_id).stok, 3)


if __name__ == '__main__':
    unittest.main()
