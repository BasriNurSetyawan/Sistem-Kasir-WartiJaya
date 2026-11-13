# Toko Xwarti API

API Flask sederhana untuk mengelola barang, mencatat transaksi, dan membuat prediksi penjualan harian dengan Single Exponential Smoothing (SES).

## Menjalankan secara lokal

Gunakan Python 3.10 atau lebih baru. Dari direktori akar proyek:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
# Ganti SECRET_KEY, API_TOKEN, dan BOOTSTRAP_ADMIN_PASSWORD di .env dengan nilai acak yang kuat.
py -3 -m pip install -r requirements.txt
py -3 -m flask --app app.run db upgrade
py -3 -m app.run
```

API tersedia di `http://localhost:7860/api`. Semua endpoint memerlukan header `Authorization: Bearer <API_TOKEN>`. `SECRET_KEY` dan `API_TOKEN` wajib disetel melalui environment; jangan simpan rahasia sebenarnya di Git.

UI tersedia di `http://localhost:7860/` dan memakai login username/kata sandi. Akun admin awal dibuat dari `BOOTSTRAP_ADMIN_USERNAME` dan `BOOTSTRAP_ADMIN_PASSWORD` saat bootstrap; password hash disimpan di database dan kredensial awal lokal ada di `.env`. Admin dapat membuat atau menonaktifkan akun serta mengelola katalog. Kasir dapat melihat data dan mencatat transaksi, tetapi tidak dapat mengubah katalog atau akun.

## Struktur aplikasi

- `app/routes/`: endpoint HTTP dan respons API.
- `app/schemas.py`: validasi dan parsing data masuk.
- `app/services/`: aturan bisnis katalog, transaksi, rekap, dan prediksi.
- `app/repositories/`: query serta perubahan data database.
- `app/models.py`: model tabel dan constraint database.
- `app/services/prediksi_ses.py`: algoritma Single Exponential Smoothing dan MAPE.
- `app/importers/`: pembaca format workbook eksternal.
- `migrations/`: riwayat perubahan skema database.

## Menjalankan dengan Docker

Jalankan perintah berikut dari direktori akar proyek. `Dockerfile` menggunakan akar proyek sebagai build context.

```powershell
Copy-Item .env.example .env
# Ubah seluruh nilai rahasia di .env sebelum menjalankan container.
docker build -t toko-xwarti-api .
docker run --env-file .env -p 5000:5000 toko-xwarti-api
```

Database SQLite dibuat sebagai `toko_xwarti.db` di dalam container dan migrasi dijalankan saat container mulai. Untuk mempertahankan data setelah container dihapus, mount volume ke `/app/toko_xwarti.db` atau gunakan database persisten terkelola.

## Endpoint

Semua endpoint memakai awalan `/api`.

| Metode | Path | Fungsi |
| --- | --- | --- |
| `GET` | `/barang?page=1&per_page=20` | Daftar barang berpaginasi |
| `POST` | `/barang` | Membuat barang (`nama_barang`, `stok`, `harga`) |
| `PUT` | `/barang/<barang_id>` | Memperbarui barang |
| `DELETE` | `/barang/<barang_id>` | Menghapus barang tanpa riwayat transaksi |
| `POST` | `/transaksi` | Mencatat penjualan (`barang_id`, `jumlah_terjual`, opsional `tanggal` berformat `YYYY-MM-DD`) |
| `GET` | `/rekap/harian?dari=YYYY-MM-DD&sampai=YYYY-MM-DD` | Rekap jumlah transaksi, unit terjual, dan penghasilan per hari |
| `GET` | `/prediksi/<barang_id>?alpha=0.3` | Prediksi penjualan untuk periode berikutnya |
| `GET` | `/belanja/rekap?page=1&per_page=20` | Daftar baris rekap nota belanja |
| `GET` | `/belanja/detail?page=1&per_page=20` | Daftar rincian barang belanja dan penanda kemungkinan duplikat |

Harga dikirim sebagai angka dan disimpan dengan presisi dua desimal. Rekap penghasilan menghitung omzet kotor (harga jual × jumlah terjual), bukan laba setelah modal dan biaya. Rekap harian secara default hanya menampilkan hari ini; rentang maksimal 366 hari. Setiap transaksi menyimpan snapshot harga satuan, sehingga perubahan harga barang tidak mengubah penghasilan transaksi yang sudah tercatat.

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
- `API_TOKEN`: token Bearer minimal 32 karakter; diperlukan pada semua endpoint.
- `BOOTSTRAP_ADMIN_USERNAME` / `BOOTSTRAP_ADMIN_PASSWORD`: akun admin awal untuk UI; password minimal 12 karakter.
- `PORT`: port server; default `7860` untuk lokal dan `5000` di Docker.
- `BUSINESS_TIMEZONE`: zona waktu untuk tanggal transaksi, rekap, dan prediksi; default `Asia/Jakarta`.
- `DATABASE_URL`: URI database SQLAlchemy opsional; default SQLite di akar proyek.
- SQLite menggunakan file `toko_xwarti.db` di akar proyek. Perubahan skema dikelola dengan Flask-Migrate; jalankan `flask --app app.run db upgrade` setelah checkout versi baru.
- Prediksi SES mengisi hari tanpa penjualan sebagai nilai nol sampai tanggal sekarang; `alpha` harus lebih dari `0` dan paling tinggi `1`.
- Saat migrasi pertama, transaksi lama diberi snapshot harga barang yang berlaku sekarang. Karena harga historis belum tersimpan sebelumnya, penghasilan sebelum migrasi merupakan estimasi memakai harga barang saat migrasi, bukan rekonstruksi harga saat transaksi.

## Pengujian

Jalankan tes API dengan `py -3 -m unittest discover -s tests`.

Untuk memasukkan workbook nota belanja, jalankan `py -3 -m scripts.import_rekap_belanja "D:\metopen\Data\Rekap_Nota_Belanja_Gabungan-v9.xlsx"`. Migrasi membuat ledger belanja yang terpisah dari penjualan. Import mempertahankan baris sumber, termasuk baris yang ditandai kemungkinan duplikat, dan aman dijalankan ulang untuk file yang sama.
