from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import func, update
from sqlalchemy.exc import SQLAlchemyError
from app import db
from app.models import Barang, Transaksi
from app.services.prediksi_ses import hitung_ses_mape
from datetime import datetime
import math

api_bp = Blueprint('api', __name__)


def _integer(value, field, *, minimum=0):
    if (isinstance(value, bool) or not isinstance(value, int)
            or value < minimum or value > 9_223_372_036_854_775_807):
        raise ValueError(f"{field} harus berupa bilangan bulat antara {minimum} dan 9223372036854775807.")
    return value


def _json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("Body harus berupa objek JSON.")
    return data

# --- ENDPOINT 1: MANAJEMEN BARANG ---
@api_bp.route('/barang', methods=['POST'])
def tambah_barang():
    try:
        data = _json_body()
        nama = data.get('nama_barang')
        if not isinstance(nama, str) or not nama.strip() or len(nama.strip()) > 100:
            raise ValueError("nama_barang wajib berupa teks sepanjang 1 sampai 100 karakter.")
        stok = _integer(data.get('stok'), 'stok')
        harga = data.get('harga')
        if isinstance(harga, bool) or not isinstance(harga, (int, float)):
            raise ValueError("harga harus berupa angka finite dan tidak negatif.")
        try:
            harga = float(harga)
        except (OverflowError, ValueError):
            raise ValueError("harga harus berupa angka finite dan tidak negatif.")
        if not math.isfinite(harga) or harga < 0:
            raise ValueError("harga harus berupa angka finite dan tidak negatif.")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    barang_baru = Barang(nama_barang=nama.strip(), stok=stok, harga=harga)
    db.session.add(barang_baru)
    db.session.commit()
    return jsonify({"pesan": "Barang berhasil ditambahkan", "id": barang_baru.id}), 201

@api_bp.route('/barang', methods=['GET'])
def get_semua_barang():
    semua_barang = Barang.query.all()
    hasil = [{"id": b.id, "nama": b.nama_barang, "stok": b.stok, "harga": b.harga} for b in semua_barang]
    return jsonify(hasil), 200

# --- ENDPOINT 2: POINT OF SALES (KASIR) ---
@api_bp.route('/transaksi', methods=['POST'])
def catat_transaksi():
    try:
        data = _json_body()
        barang_id = _integer(data.get('barang_id'), 'barang_id', minimum=1)
        jumlah = _integer(data.get('jumlah_terjual'), 'jumlah_terjual', minimum=1)
        tanggal_str = data.get('tanggal')
        tanggal = datetime.utcnow().date()
        if tanggal_str is not None:
            if not isinstance(tanggal_str, str):
                raise ValueError("tanggal harus berformat YYYY-MM-DD.")
            try:
                tanggal = datetime.strptime(tanggal_str, '%Y-%m-%d').date()
                if tanggal.isoformat() != tanggal_str:
                    raise ValueError
            except ValueError:
                raise ValueError("tanggal harus berformat YYYY-MM-DD dan merupakan tanggal valid.")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    barang = db.session.get(Barang, barang_id)
    if not barang:
        return jsonify({"error": "Barang tidak ditemukan"}), 404

    try:
        # Conditional UPDATE is atomic: concurrent sales cannot oversell stock.
        result = db.session.execute(
            update(Barang).where(Barang.id == barang_id, Barang.stok >= jumlah)
            .values(stok=Barang.stok - jumlah)
        )
        if result.rowcount != 1:
            db.session.rollback()
            barang = db.session.get(Barang, barang_id)
            remaining = barang.stok if barang else 0
            return jsonify({"error": f"Stok tidak mencukupi. Sisa stok: {remaining}"}), 400

        db.session.add(Transaksi(barang_id=barang_id, jumlah_terjual=jumlah, tanggal=tanggal))
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Gagal menyimpan transaksi")
        return jsonify({"error": "Transaksi gagal disimpan."}), 500

    barang = db.session.get(Barang, barang_id)
    return jsonify({"pesan": "Transaksi berhasil", "sisa_stok": barang.stok}), 200

# --- ENDPOINT 3: PERAMALAN (FORECASTING) SES ---
@api_bp.route('/prediksi/<int:barang_id>', methods=['GET'])
def prediksi_stok(barang_id):
    try:
        alpha = float(request.args.get('alpha', 0.3))
        if not math.isfinite(alpha) or not 0 < alpha <= 1:
            raise ValueError
    except ValueError:
        return jsonify({"error": "alpha harus berupa angka antara 0 dan 1 (inklusif)."}), 400
    
    # Validasi keberadaan barang
    barang = Barang.query.get(barang_id)
    if not barang:
        return jsonify({"error": "Barang tidak ditemukan"}), 404

    # AGREGASI DATA HARIAN:
    # Menjumlahkan (SUM) total penjualan berdasarkan tanggal yang sama
    penjualan_harian = db.session.query(
        Transaksi.tanggal,
        func.sum(Transaksi.jumlah_terjual).label('total_harian')
    ).filter(Transaksi.barang_id == barang_id)\
     .group_by(Transaksi.tanggal)\
     .order_by(Transaksi.tanggal).all()
    
    if len(penjualan_harian) < 2:
        return jsonify({"error": "Data historis tidak mencukupi untuk peramalan deret waktu (minimal 2 hari aktif transaksi)."}), 400
        
    # Ekstraksi ke list numerik untuk dikirim ke fungsi algoritma
    # Construct a continuous daily series, including zero sales on quiet days.
    by_date = {p.tanggal: p.total_harian for p in penjualan_harian}
    first_day = penjualan_harian[0].tanggal
    last_day = max(penjualan_harian[-1].tanggal, datetime.utcnow().date())
    dates = [first_day.fromordinal(n) for n in range(first_day.toordinal(), last_day.toordinal() + 1)]
    data_aktual = [by_date.get(day, 0) for day in dates]
    tanggal_historis = [day.strftime('%Y-%m-%d') for day in dates]
    
    # Eksekusi Algoritma
    prediksi_next, mape = hitung_ses_mape(data_aktual, alpha)
    
    return jsonify({
        "barang_id": barang.id,
        "nama_barang": barang.nama_barang,
        "parameter_alpha": alpha,
        "total_hari_transaksi": len(penjualan_harian),
        "total_hari_periode": len(data_aktual),
        "data_aktual": data_aktual,
        "tanggal_historis": tanggal_historis,
        "prediksi_penjualan_besok": prediksi_next,
        "akurasi_mape": f"{mape}%"
    }), 200
