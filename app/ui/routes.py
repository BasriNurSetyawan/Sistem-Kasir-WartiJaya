from decimal import Decimal, InvalidOperation
import hmac
import secrets
from functools import wraps

from flask import (
    abort, current_app, flash, g, redirect, render_template, request, session,
    url_for,
)
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.business_time import business_today
from app.repositories.transaksi_repository import InsufficientStock, ItemNotFound
from app.schemas import alpha_arg, integer, new_item, pagination_args, parse_date, report_args
from app.services import barang_service, belanja_service, rekap_service, transaksi_service
from app.services import pengguna_service
from app.repositories.pengguna_repository import get_by_id
from app.services.prediksi_service import (
    ForecastRangeTooLong,
    InsufficientHistory,
    ItemNotFound as ForecastItemNotFound,
    forecast,
)
from app.ui import ui_bp


def _csrf_token():
    token = session.get('_csrf_token')
    if token is None:
        token = secrets.token_urlsafe(32)
        session['_csrf_token'] = token
    return token


@ui_bp.before_request
def protect_ui():
    if request.method == 'POST':
        expected = session.get('_csrf_token', '')
        supplied = request.form.get('csrf_token', '')
        if not expected or not supplied or not hmac.compare_digest(expected, supplied):
            abort(400)
    if request.endpoint == 'ui.login':
        return None
    if not session.get('user_id'):
        return redirect(url_for('ui.login'))
    user = get_by_id(session['user_id'])
    if user is None or not user.aktif:
        session.clear()
        return redirect(url_for('ui.login'))
    g.current_user = user


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if getattr(g, 'current_user', None) is None or g.current_user.role != 'admin':
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@ui_bp.app_context_processor
def inject_ui_helpers():
    return {
        'csrf_token': _csrf_token,
        'today': business_today,
        'current_user': getattr(g, 'current_user', None),
    }


@ui_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = pengguna_service.authenticate(username, password)
        if user:
            session.clear()
            session['user_id'] = user.id
            session.permanent = True
            flash(f'Selamat datang, {user.username}.', 'success')
            return redirect(url_for('ui.dashboard'))
        flash('Nama pengguna atau kata sandi tidak cocok.', 'error')
    return render_template('login.html')


@ui_bp.post('/logout')
def logout():
    session.clear()
    return redirect(url_for('ui.login'))


@ui_bp.route('/')
def dashboard():
    current_day = business_today()
    try:
        report = rekap_service.daily_report(current_day, current_day)
        items = barang_service.list_items(1, 100)
        recent_sales = transaksi_service.latest_sales(7)
        purchase_summaries = belanja_service.list_summaries(1, 5)
    except SQLAlchemyError:
        current_app.logger.exception('Gagal memuat dashboard UI')
        flash('Dashboard gagal dimuat dari database.', 'error')
        report = {'total_transaksi': 0, 'jumlah_terjual': 0, 'total_penghasilan': '0.00', 'harian': []}
        items = None
        recent_sales = []
        purchase_summaries = None
    return render_template(
        'dashboard.html', report=report, item_count=items.total if items else 0,
        recent_sales=recent_sales,
        purchase_summaries=purchase_summaries.items if purchase_summaries else [],
    )


@ui_bp.route('/barang', methods=['GET', 'POST'])
def barang():
    if request.method == 'POST':
        if g.current_user.role != 'admin':
            abort(403)
        try:
            values = new_item({
                'nama_barang': request.form.get('nama_barang'),
                'stok': int(request.form.get('stok', '')),
                'harga': Decimal(request.form.get('harga', '')),
            })
            barang_service.create_item(values)
            flash('Barang berhasil ditambahkan.', 'success')
            return redirect(url_for('ui.barang'))
        except (ValueError, TypeError, InvalidOperation) as exc:
            flash(str(exc) or 'Periksa kembali data barang.', 'error')
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception('Gagal menyimpan barang melalui UI')
            flash('Barang gagal disimpan.', 'error')

    try:
        page, per_page = pagination_args(request.args)
        results = barang_service.list_items(page, per_page)
    except ValueError as exc:
        flash(str(exc), 'error')
        results = barang_service.list_items(1, 20)
    except SQLAlchemyError:
        current_app.logger.exception('Gagal memuat barang melalui UI')
        results = None
    return render_template('barang.html', results=results)


def _item_form_values():
    return new_item({
        'nama_barang': request.form.get('nama_barang'),
        'stok': integer(int(request.form.get('stok', '')), 'stok'),
        'harga': Decimal(request.form.get('harga', '')),
    })


@ui_bp.route('/barang/<int:item_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_barang(item_id):
    try:
        item = barang_service.get_item(item_id)
    except SQLAlchemyError:
        current_app.logger.exception('Gagal membaca barang untuk diedit')
        abort(500)
    if item is None:
        abort(404)
    if request.method == 'POST':
        try:
            barang_service.update_item(item_id, _item_form_values())
            flash('Barang berhasil diperbarui.', 'success')
            return redirect(url_for('ui.barang'))
        except (ValueError, TypeError, InvalidOperation) as exc:
            flash(str(exc) or 'Periksa kembali data barang.', 'error')
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception('Gagal memperbarui barang melalui UI')
            flash('Perubahan barang gagal disimpan.', 'error')
    return render_template('edit_barang.html', item=item)


@ui_bp.post('/barang/<int:item_id>/hapus')
@admin_required
def hapus_barang(item_id):
    try:
        deleted = barang_service.delete_item(item_id)
    except barang_service.ItemHasSales:
        flash('Barang memiliki riwayat penjualan dan tidak dapat dihapus.', 'error')
        return redirect(url_for('ui.barang'))
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception('Gagal menghapus barang melalui UI')
        flash('Barang gagal dihapus.', 'error')
        return redirect(url_for('ui.barang'))
    flash('Barang berhasil dihapus.' if deleted else 'Barang tidak ditemukan.', 'success' if deleted else 'error')
    return redirect(url_for('ui.barang'))


@ui_bp.route('/pengguna', methods=['GET', 'POST'])
@admin_required
def pengguna():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', '')
        if (len(username) < 3 or len(username) > 80
                or not all(char.isalnum() or char in '._-' for char in username)):
            flash('Username harus 3–80 karakter dan hanya berisi huruf, angka, titik, garis bawah, atau tanda hubung.', 'error')
        elif len(password) < 12:
            flash('Kata sandi harus minimal 12 karakter.', 'error')
        elif role not in ('admin', 'kasir'):
            flash('Pilih peran admin atau kasir.', 'error')
        else:
            try:
                pengguna_service.create_user(username, password, role)
                flash(f'Akun {username} berhasil dibuat.', 'success')
                return redirect(url_for('ui.pengguna'))
            except SQLAlchemyError:
                current_app.logger.exception('Gagal membuat akun')
                flash('Username sudah digunakan atau akun gagal disimpan.', 'error')
    try:
        users = pengguna_service.list_users()
    except SQLAlchemyError:
        current_app.logger.exception('Gagal memuat akun')
        users = []
    return render_template('pengguna.html', users=users)


@ui_bp.post('/pengguna/<int:user_id>/aktif')
@admin_required
def ubah_status_pengguna(user_id):
    active = request.form.get('aktif') == 'true'
    users = pengguna_service.list_users()
    target = next((user for user in users if user.id == user_id), None)
    if target is None:
        flash('Akun tidak ditemukan.', 'error')
        return redirect(url_for('ui.pengguna'))
    if not active and target.id == g.current_user.id:
        flash('Anda tidak dapat menonaktifkan akun sendiri.', 'error')
        return redirect(url_for('ui.pengguna'))
    if not active and target.role == 'admin' and sum(u.aktif and u.role == 'admin' for u in users) <= 1:
        flash('Sistem harus memiliki minimal satu admin aktif.', 'error')
        return redirect(url_for('ui.pengguna'))
    pengguna_service.set_active(user_id, active)
    flash('Status akun diperbarui.', 'success')
    return redirect(url_for('ui.pengguna'))


@ui_bp.post('/pengguna/<int:user_id>/peran')
@admin_required
def ubah_peran_pengguna(user_id):
    role = request.form.get('role')
    users = pengguna_service.list_users()
    target = next((user for user in users if user.id == user_id), None)
    if target is None:
        flash('Akun tidak ditemukan.', 'error')
    elif role not in ('admin', 'kasir'):
        flash('Peran tidak valid.', 'error')
    elif target.id == g.current_user.id and role != 'admin':
        flash('Anda tidak dapat mengubah peran akun sendiri.', 'error')
    elif target.role == 'admin' and role == 'kasir' and target.aktif and sum(u.aktif and u.role == 'admin' for u in users) <= 1:
        flash('Sistem harus memiliki minimal satu admin aktif.', 'error')
    else:
        pengguna_service.set_role(user_id, role)
        flash('Peran akun diperbarui.', 'success')
    return redirect(url_for('ui.pengguna'))


@ui_bp.route('/transaksi', methods=['GET', 'POST'])
def transaksi():
    if request.method == 'POST':
        try:
            item_id = integer(int(request.form.get('barang_id', '')), 'barang_id', minimum=1)
            quantity = integer(int(request.form.get('jumlah_terjual', '')), 'jumlah_terjual', minimum=1)
            sold_on = parse_date(request.form['tanggal'], 'tanggal') if request.form.get('tanggal') else business_today()
            if sold_on > business_today():
                raise ValueError('tanggal tidak boleh berada di masa depan.')
            remaining = transaksi_service.record_sale(item_id, quantity, sold_on)
            flash(f'Transaksi berhasil. Stok tersisa {remaining}.', 'success')
            return redirect(url_for('ui.transaksi'))
        except (ValueError, TypeError) as exc:
            flash(str(exc) or 'Data transaksi tidak valid.', 'error')
        except ItemNotFound:
            flash('Barang tidak ditemukan.', 'error')
        except InsufficientStock as exc:
            flash(f'Stok tidak mencukupi. Sisa stok: {exc.remaining}.', 'error')
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception('Gagal mencatat transaksi melalui UI')
            flash('Transaksi gagal disimpan.', 'error')

    try:
        items = barang_service.list_items(1, 100).items
        recent_sales = transaksi_service.latest_sales(12)
    except SQLAlchemyError:
        current_app.logger.exception('Gagal memuat transaksi melalui UI')
        items, recent_sales = [], []
    return render_template('transaksi.html', items=items, recent_sales=recent_sales)


@ui_bp.route('/rekap', methods=['GET'])
def rekap():
    try:
        end = parse_date(request.args['sampai'], 'sampai') if 'sampai' in request.args else business_today()
        start = parse_date(request.args['dari'], 'dari') if 'dari' in request.args else end
        start, end = report_args({'dari': start.isoformat(), 'sampai': end.isoformat()}, business_today(), 366)
        report = rekap_service.daily_report(start, end)
    except ValueError as exc:
        flash(str(exc), 'error')
        report = None
    except SQLAlchemyError:
        current_app.logger.exception('Gagal memuat rekap melalui UI')
        report = None
    return render_template('rekap.html', report=report)


@ui_bp.route('/belanja', methods=['GET'])
def belanja():
    try:
        page, per_page = pagination_args(request.args)
        summaries = belanja_service.list_summaries(page, per_page)
        details = belanja_service.list_details(page, per_page)
    except ValueError as exc:
        flash(str(exc), 'error')
        summaries = belanja_service.list_summaries(1, 20)
        details = belanja_service.list_details(1, 20)
    except SQLAlchemyError:
        current_app.logger.exception('Gagal memuat belanja melalui UI')
        summaries, details = None, None
    return render_template('belanja.html', summaries=summaries, details=details)


@ui_bp.route('/prediksi', methods=['GET', 'POST'])
def prediksi():
    result = None
    if request.method == 'POST':
        try:
            item_id = int(request.form.get('barang_id', ''))
            alpha = alpha_arg(request.form.get('alpha'))
            result = forecast(item_id, alpha, business_today())
        except (ValueError, TypeError) as exc:
            flash(str(exc) or 'Parameter prediksi tidak valid.', 'error')
        except ForecastItemNotFound:
            flash('Barang tidak ditemukan.', 'error')
        except InsufficientHistory:
            flash('Data historis belum cukup; diperlukan penjualan pada minimal dua hari berbeda.', 'error')
        except ForecastRangeTooLong:
            flash('Rentang data historis terlalu panjang untuk diprediksi.', 'error')
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception('Gagal menghitung prediksi melalui UI')
            flash('Prediksi gagal dihitung.', 'error')
    try:
        items = barang_service.list_items(1, 100).items
    except SQLAlchemyError:
        current_app.logger.exception('Gagal memuat pilihan barang untuk prediksi')
        items = []
    return render_template('prediksi.html', items=items, result=result)
