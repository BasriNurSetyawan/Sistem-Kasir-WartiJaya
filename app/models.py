from app import db
from app.business_time import business_today
from datetime import datetime, timezone

class Barang(db.Model):
    __tablename__ = 'barang'
    id = db.Column(db.Integer, primary_key=True)
    nama_barang = db.Column(db.String(100), nullable=False)
    stok = db.Column(db.Integer, nullable=False, default=0)
    harga = db.Column(db.Numeric(14, 2), nullable=False)
    __table_args__ = (
        db.CheckConstraint('stok >= 0', name='ck_barang_stok_nonnegative'),
        db.CheckConstraint('harga >= 0', name='ck_barang_harga_nonnegative'),
    )
    
    # Relasi ke tabel transaksi
    transaksi = db.relationship('Transaksi', backref='barang', lazy=True)

class Transaksi(db.Model):
    __tablename__ = 'transaksi'
    id = db.Column(db.Integer, primary_key=True)
    barang_id = db.Column(db.Integer, db.ForeignKey('barang.id'), nullable=False)
    jumlah_terjual = db.Column(db.Integer, nullable=False)
    harga_satuan = db.Column(db.Numeric(14, 2), nullable=False)
    # Gunakan tanggal (date) murni tanpa jam untuk mempermudah agregasi deret waktu
    tanggal = db.Column(db.Date, nullable=False, default=business_today)
    __table_args__ = (
        db.CheckConstraint('jumlah_terjual > 0', name='ck_transaksi_jumlah_positive'),
        db.CheckConstraint('harga_satuan >= 0', name='ck_transaksi_harga_nonnegative'),
        db.Index('ix_transaksi_tanggal_barang', 'tanggal', 'barang_id'),
    )


class RekapBelanja(db.Model):
    __tablename__ = 'rekap_belanja'
    __table_args__ = (
        db.UniqueConstraint('source_sha256', 'source_sheet', 'source_row', name='uq_rekap_belanja_source_row'),
        db.CheckConstraint('total >= 0', name='ck_rekap_belanja_total_nonnegative'),
    )

    id = db.Column(db.Integer, primary_key=True)
    outlet = db.Column(db.String(150), nullable=False)
    tanggal_acuan = db.Column(db.Date, nullable=False)
    tanggal_selesai = db.Column(db.Date, nullable=True)
    cakupan = db.Column(db.String(30), nullable=False)
    keterangan_tanggal = db.Column(db.String(150), nullable=False)
    total = db.Column(db.Numeric(14, 2), nullable=False)
    source_file = db.Column(db.String(255), nullable=False)
    source_sha256 = db.Column(db.String(64), nullable=False)
    source_sheet = db.Column(db.String(100), nullable=False)
    source_row = db.Column(db.Integer, nullable=False)


class DetailBelanja(db.Model):
    __tablename__ = 'detail_belanja'
    __table_args__ = (
        db.UniqueConstraint('source_sha256', 'source_sheet', 'source_row', name='uq_detail_belanja_source_row'),
        db.CheckConstraint('harga_total >= 0', name='ck_detail_belanja_harga_nonnegative'),
    )

    id = db.Column(db.Integer, primary_key=True)
    outlet = db.Column(db.String(150), nullable=False)
    tanggal = db.Column(db.Date, nullable=False)
    nama_barang = db.Column(db.String(150), nullable=False)
    jumlah_asli = db.Column(db.String(100), nullable=False)
    harga_total = db.Column(db.Numeric(14, 2), nullable=False)
    kemungkinan_duplikat = db.Column(db.Boolean, nullable=False, default=False)
    source_file = db.Column(db.String(255), nullable=False)
    source_sha256 = db.Column(db.String(64), nullable=False)
    source_sheet = db.Column(db.String(100), nullable=False)
    source_row = db.Column(db.Integer, nullable=False)


class Pengguna(db.Model):
    __tablename__ = 'pengguna'
    __table_args__ = (
        db.CheckConstraint("role IN ('admin', 'kasir')", name='ck_pengguna_role_valid'),
    )

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    aktif = db.Column(db.Boolean, nullable=False, default=True)
    dibuat_pada = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
