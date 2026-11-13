import unittest
import re
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from app import create_app, db
from app.business_time import business_today
from app.models import Barang, DetailBelanja, Pengguna, RekapBelanja
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
            'SECRET_KEY': 'test-secret-key',
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
            self.assertEqual(self.client.get(path).status_code, 200, path)
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
            'csrf_token': csrf, 'barang_id': str(item_id), 'jumlah_terjual': '1',
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


if __name__ == '__main__':
    unittest.main()
