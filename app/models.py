from app import db
from datetime import datetime

class Barang(db.Model):
    __tablename__ = 'barang'
    id = db.Column(db.Integer, primary_key=True)
    nama_barang = db.Column(db.String(100), nullable=False)
    stok = db.Column(db.Integer, default=0)
    harga = db.Column(db.Float, nullable=False)
    
    # Relasi ke tabel transaksi
    transaksi = db.relationship('Transaksi', backref='barang', lazy=True)

class Transaksi(db.Model):
    __tablename__ = 'transaksi'
    id = db.Column(db.Integer, primary_key=True)
    barang_id = db.Column(db.Integer, db.ForeignKey('barang.id'), nullable=False)
    jumlah_terjual = db.Column(db.Integer, nullable=False)
    # Gunakan tanggal (date) murni tanpa jam untuk mempermudah agregasi deret waktu
    tanggal = db.Column(db.Date, default=lambda: datetime.utcnow().date())
