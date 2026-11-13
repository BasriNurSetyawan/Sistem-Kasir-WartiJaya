# Toko Xwarti API

API Flask sederhana untuk mengelola barang, mencatat transaksi, dan membuat prediksi penjualan harian dengan Single Exponential Smoothing (SES).

## Menjalankan secara lokal

Gunakan Python 3.10 atau lebih baru. Dari direktori akar proyek:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3 -m pip install -r requirements.txt
$env:SECRET_KEY = "ganti-dengan-nilai-acak-yang-panjang"
py -3 -m app.run
```

API tersedia di `http://localhost:7860/api`. `SECRET_KEY` harus disetel di environment sebelum menjalankan aplikasi. Jangan menyimpan nilai rahasia sebenarnya di Git.

## Menjalankan dengan Docker

Jalankan perintah berikut dari direktori akar proyek. `app/Dockerfile` mengharapkan build context akar proyek.

```powershell
Copy-Item .env.example .env
# Ubah SECRET_KEY di .env menjadi nilai acak yang panjang sebelum menjalankan container.
docker build -f app/Dockerfile -t toko-xwarti-api .
docker run --env-file .env -p 5000:5000 toko-xwarti-api
```

Database SQLite dibuat sebagai `toko_xwarti.db` di dalam container. Untuk mempertahankan data setelah container dihapus, mount volume ke `/app/toko_xwarti.db` atau gunakan database persisten terkelola.

## Endpoint

Semua endpoint memakai awalan `/api`.

| Metode | Path | Fungsi |
| --- | --- | --- |
| `GET` | `/barang` | Daftar barang |
| `POST` | `/barang` | Membuat barang (`nama_barang`, `stok`, `harga`) |
| `POST` | `/transaksi` | Mencatat penjualan (`barang_id`, `jumlah_terjual`, opsional `tanggal` berformat `YYYY-MM-DD`) |
| `GET` | `/prediksi/<barang_id>?alpha=0.3` | Prediksi penjualan untuk periode berikutnya |

Contoh membuat barang:

```json
{
  "nama_barang": "Kopi",
  "stok": 20,
  "harga": 15000
}
```

## Catatan konfigurasi

- `SECRET_KEY`: rahasia aplikasi yang wajib disediakan melalui environment.
- `PORT`: port server lokal; default `7860`.
- SQLite menggunakan file `toko_xwarti.db` di akar proyek. Skema tabel dibuat otomatis saat aplikasi dimulai.
- Prediksi SES mengisi hari tanpa penjualan sebagai nilai nol sampai tanggal sekarang; `alpha` harus lebih dari `0` dan paling tinggi `1`.
