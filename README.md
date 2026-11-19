---
sdk: docker
app_port: 7860
title: Sistem Kasir Cerdas Warti Jaya
emoji: 🏪
colorFrom: green
colorTo: teal
pinned: false
---

# Sistem Kasir Toko Warti Jaya

Sistem kasir berbasis Flask untuk mengelola barang, mencatat transaksi, menyajikan rekap penjualan, dan membantu perencanaan restok berdasarkan histori penjualan harian.

## Menjalankan secara lokal

Gunakan Python 3.10 atau lebih baru. Dari direktori akar proyek:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
py -3 -m pip install -r requirements.txt
py -3 -m flask --app app.run db upgrade
py -3 -m app.run
```

## Struktur aplikasi

- `app/routes/`: endpoint HTTP dan respons API.
- `app/schemas.py`: validasi dan parsing data masuk.
- `app/services/`: aturan bisnis katalog, transaksi, rekap, dan prediksi.
- `app/repositories/`: query serta perubahan data database.
- `app/models.py`: model tabel dan constraint database.
- `app/models.py` mempertahankan tabel `transaksi` lama sebagai histori baris tunggal; checkout baru menggunakan `transaksi_header` dan `detail_transaksi`, sehingga satu struk dapat memuat beberapa barang tanpa menghapus histori lama.
- `app/__init__.py` menyediakan application factory Flask dan `app/run.py` menjadi entry point `app.run:app`.
- Template setara: `base.html`, `transaksi.html` (POS), `barang.html` (inventori), dan `prediksi.html` (forecast).
- `algorithm/ses.py`: SES, pemilihan alpha, MAPE rolling-origin, dan buffer galat.
- `algorithm/ml_forecast.py`: Random Forest berbasis fitur lag, validasi mingguan kronologis, dan fallback konservatif ke SES.
- `app/services/prediksi_service.py`: membandingkan kandidat ML dengan SES dan menghitung saran stok.
- Form transaksi menyediakan pencarian barang dengan saran nama, stok, dan harga; kasir dapat menambah beberapa baris barang sebelum checkout. Stok semua barang divalidasi atomik; jika satu baris kekurangan stok, seluruh checkout dibatalkan.
- `app/importers/`: pembaca format workbook eksternal.
- `migrations/`: riwayat perubahan skema database.

## Menjalankan dengan Docker

Jalankan perintah berikut dari direktori akar proyek. `Dockerfile` menggunakan akar proyek sebagai build context dan memakai SQLite persisten di `/data` sebagai default. Untuk deployment melalui HTTPS, ubah `SESSION_COOKIE_SECURE=true`.

```powershell
Copy-Item .env.example .env
# Ubah seluruh nilai rahasia di .env sebelum menjalankan container.
docker build -t toko-warti-jaya .
docker run --env-file .env --mount source=warti-data,target=/data -p 7860:7860 toko-warti-jaya
```

Container berjalan sebagai pengguna non-root, memiliki health check di `/healthz`, menjalankan migrasi saat startup, lalu melayani aplikasi dengan Waitress. Volume bernama `warti-data` menjaga file SQLite `/data/toko_warti_jaya.db` saat container dibuat ulang. Startup migration dirancang untuk satu instance aplikasi; jalankan migrasi sebagai satu pekerjaan terpisah sebelum scale-out multi-instance.

Untuk MySQL, isi `DATABASE_URL` di `.env` dengan URI SQLAlchemy, misalnya `mysql+pymysql://user:password@db-host:3306/warti_jaya?charset=utf8mb4` (URL-encode karakter khusus pada username/password). Driver PyMySQL sudah disertakan. Pastikan database tersedia sebelum aplikasi mulai; gunakan layanan database terkelola dan backup rutin untuk deployment produksi.

## Endpoint

Semua endpoint memakai awalan `/api`.

| Metode | Path | Fungsi |
| --- | --- | --- |
| `GET` | `/barang?page=1&per_page=20` | Daftar barang berpaginasi |
| `POST` | `/barang` | Membuat barang (`nama_barang`, `stok`, `harga`) |
| `PUT` | `/barang/<barang_id>` | Memperbarui barang |
| `DELETE` | `/barang/<barang_id>` | Menghapus barang tanpa riwayat transaksi |
| `POST` | `/transaksi` | Mencatat penjualan (`barang_id`, `jumlah_terjual`, opsional `tanggal` berformat `YYYY-MM-DD`) |
| `POST` | `/transaksi/cart` | Mencatat satu struk berisi beberapa detail (`items: [{barang_id, jumlah_terjual}]`, opsional `tanggal`) secara atomik |
| `GET` | `/rekap/harian?dari=YYYY-MM-DD&sampai=YYYY-MM-DD` | Rekap jumlah transaksi, unit terjual, dan penghasilan per hari |
| `GET` | `/prediksi/restok` | Rekomendasi restok semua barang untuk 7 hari berikutnya |
| `GET` | `/prediksi/<barang_id>` | Prediksi dan rekomendasi restok untuk satu barang |
| `GET` | `/belanja/rekap?page=1&per_page=20` | Daftar baris rekap nota belanja |
| `GET` | `/belanja/detail?page=1&per_page=20` | Daftar rincian barang belanja dan penanda kemungkinan duplikat |

Harga dikirim sebagai angka dan disimpan dengan presisi dua desimal. Rekap penghasilan menghitung omzet kotor (harga jual × jumlah terjual), bukan laba setelah modal dan biaya. Rekap harian secara default hanya menampilkan hari ini; rentang maksimal 366 hari. Setiap transaksi menyimpan snapshot harga satuan, sehingga perubahan harga barang tidak mengubah penghasilan transaksi yang sudah tercatat.

## Catatan konfigurasi

- `SECRET_KEY`: rahasia aplikasi minimal 32 karakter, wajib disediakan melalui environment.
- `API_TOKEN`: token Bearer minimal 32 karakter; diperlukan pada semua endpoint.
- `BOOTSTRAP_ADMIN_USERNAME` / `BOOTSTRAP_ADMIN_PASSWORD`: akun admin awal untuk UI; password minimal 12 karakter.
- `PORT`: port server; default `7860` untuk lokal dan `5000` di Docker.
- `BUSINESS_TIMEZONE`: zona waktu untuk tanggal transaksi, rekap, dan prediksi; default `Asia/Jakarta`.
- `DATABASE_URL`: URI database SQLAlchemy opsional; default SQLite di akar proyek.
- MySQL didukung melalui `mysql+pymysql://user:password@host:3306/database?charset=utf8mb4`.
- SQLite menggunakan file `toko_warti_jaya.db` di akar proyek. Perubahan skema dikelola dengan Flask-Migrate; jalankan `flask --app app.run db upgrade` setelah checkout versi baru.
- Mesin keputusan membaca histori transaksi hingga 120 hari kalender; halaman tetap menampilkan total penjualan 28 hari terkini sebagai ringkasan.
- Random Forest Regressor menggunakan penjualan lag 1, 2, 3, 7, 14, 21, 28 hari dan rerata bergerak 7, 14, 28 hari. Model ML memerlukan setidaknya 77 hari deret harian dan tiga jendela validasi mingguan kronologis dengan aktual positif. Model dibandingkan dengan SES pada jendela yang sama dan hanya digunakan jika MAPE lebih rendah. Belum ada pengacakan data karena urutan waktu harus dijaga. Histori yang belum memenuhi syarat atau ML yang tidak mengungguli SES akan memakai fallback SES.
- SES memilih alpha dari kandidat 0,01 sampai 1,00 dengan MAPE one-step terkecil pada histori latih; nilai lebih kecil dipilih jika skornya sama. Nilai bawaan 0,30 dipakai sebelum tersedia tujuh hari histori latih atau bila seluruh histori latih nol. Evaluasi SES memakai maksimal 15 titik rolling-origin terbaru dengan horizon 7 hari; jendela aktual total nol dihitung terpisah dan tidak masuk penyebut MAPE.
- Target stok adalah ramalan tujuh hari + buffer galat underforecast model terpilih jika sedikitnya tujuh jendela tersedia. Saran restok = maksimum(0, target stok − stok saat ini). Buffer merupakan heuristik, bukan jaminan service level.
- Lapisan keputusan menghitung buffer adaptif dari persentil ke-75 galat underforecast pada tujuh jendela backtest terbaru; buffer aktif setelah tersedia minimal tujuh jendela. Target stok adalah ramalan tujuh hari ditambah buffer, dan jumlah restok adalah maksimum nol dari target dikurangi stok saat ini. Risiko tinggi berarti stok di bawah ramalan; sedang berarti stok berada antara ramalan dan target; rendah berarti stok memenuhi target. Aturan ini merupakan heuristik berbasis data, bukan jaminan service level. Kasus dengan histori tidak memadai diberi penanda untuk tinjauan manual.
- Prediksi tidak memperhitungkan waktu tunggu pemasok, promosi, hari toko tutup, atau permintaan yang tidak tercatat ketika stok habis. Barang tanpa transaksi dalam 120 hari terakhir ditandai untuk evaluasi manual. Data pembelian yang diimpor tersimpan pada ledger terpisah dan tidak otomatis menambah stok katalog. Hasil ML perlu divalidasi pada histori operasional; keberadaan estimator tidak menjamin prediksi selalu lebih baik.
- Saat migrasi pertama, transaksi lama diberi snapshot harga barang yang berlaku sekarang. Karena harga historis belum tersimpan sebelumnya, penghasilan sebelum migrasi merupakan estimasi memakai harga barang saat migrasi, bukan rekonstruksi harga saat transaksi.
