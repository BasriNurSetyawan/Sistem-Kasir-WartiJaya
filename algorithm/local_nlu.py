"""Local NLU (Natural Language Understanding) Retail Engine.

Uses TF-IDF Vectorization and Cosine Similarity to classify user intents
and extract product entities from natural language queries in Indonesian,
synthesizing rich data-driven analytical responses without external API keys.
"""

import re
from decimal import Decimal
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


INTENT_KNOWLEDGE_BASE = {
    'stok_kritis': [
        "stok apa yang hampir habis",
        "barang rawan habis",
        "stok kritis yang harus segera dibeli",
        "barang apa yang perlu direstok sekarang",
        "apakah ada barang yang kehabisan stok",
        "rekomendasi barang belanja restok darurat",
        "produk dengan sisa stok sedikit",
        "daftar barang kritis hari ini",
    ],
    'omzet_hari_ini': [
        "berapa penjualan hari ini",
        "rekap omzet transaksi kasir hari ini",
        "berapa pemasukan dan total pendapatan hari ini",
        "laporan kasir dan transaksi hari ini",
        "omzet toko hari ini dapat berapa",
        "berapa uang masuk hari ini",
        "ringkasan transaksi harian kasir",
    ],
    'produk_terlaris': [
        "apa produk paling laris di toko",
        "barang terlaris 28 hari terakhir",
        "top seller toko warti jaya",
        "produk favorit yang paling banyak dibeli pelanggan",
        "barang apa yang penjualannya paling kencang",
        "daftar 5 produk paling laku",
        "peringkat barang terlaris",
    ],
    'dead_stock': [
        "barang apa yang tidak laku",
        "produk mengendap atau dead stock",
        "barang yang lama tidak terjual",
        "stok macet yang menumpuk di gudang",
        "barang tanpa transaksi selama sebulan",
        "produk slow moving yang perlu diobral",
        "daftar barang dead stock",
    ],
    'bundling_promo': [
        "ada saran paket promo atau diskon",
        "rekomendasi paket bundling belanja",
        "barang apa yang sering dibeli bersamaan",
        "analisis keranjang belanja kasir market basket",
        "ide promosi paket hemat untuk warung",
        "pasangan produk yang cocok dijual bersama",
    ],
    'clustering_produk': [
        "bagaimana hasil pengelompokan produk k-means",
        "klaster produk fast moving dan slow moving",
        "segmentasi perilaku penjualan barang",
        "kategori produk berdasarkan perputaran stok",
        "tampilkan klaster barang toko",
    ],
    'evaluasi_model': [
        "berapa akurasi model peramalan",
        "nilai mape mae rmse prediksi penjualan",
        "bagaimana performa random forest vs ses",
        "evaluasi akurasi peramalan untuk skripsi",
        "metrik evaluasi akurasi sistem cerdas",
    ],
    'estimasi_anggaran': [
        "berapa modal belanja restok yang dibutuhkan",
        "estimasi biaya pengadaan barang minggu ini",
        "anggaran uang untuk beli stok baru",
        "berapa total uang yang harus disiapkan untuk restok",
        "kebutuhan dana pembelian barang",
    ],
    'anomali_toko': [
        "apakah ada transaksi anomali atau mencurigakan",
        "deteksi kejanggalan stok atau penjualan",
        "laporan anomali toko dan lonjakan penjualan",
        "apakah ada data transaksi yang tidak wajar",
        "penjualan anjlok atau lonjakan drastis",
    ],
    'sapaan_bantuan': [
        "halo",
        "hai",
        "selamat pagi",
        "kamu bisa bantu apa saja",
        "menu bantuan asisten cerdas",
        "apa fitur kecerdasan ai di sistem ini",
        "siapa kamu",
    ],
}


class LocalNLUEngine:
    """Offline NLP Classifier and Analytical Response Generator."""

    def __init__(self):
        self.intent_labels = []
        self.corpus = []
        for intent, examples in INTENT_KNOWLEDGE_BASE.items():
            for ex in examples:
                self.intent_labels.append(intent)
                self.corpus.append(ex.lower())

        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            token_pattern=r'(?u)\b\w+\b',
        )
        self.X_tfidf = self.vectorizer.fit_transform(self.corpus)

    def classify_intent(self, user_query):
        """Classify user query into predefined retail intents using Cosine Similarity.

        Returns:
            tuple: (top_intent, similarity_score)
        """
        clean_q = user_query.strip().lower()
        if not clean_q:
            return 'sapaan_bantuan', 0.0

        q_vec = self.vectorizer.transform([clean_q])
        similarities = cosine_similarity(q_vec, self.X_tfidf)[0]

        best_idx = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])
        top_intent = self.intent_labels[best_idx]

        return top_intent, best_score

    def find_mentioned_product(self, user_query, catalog_items):
        """Extract product entity from query by fuzzy token matching against catalog."""
        clean_q = user_query.lower()
        best_match = None
        best_len = 0

        for item in catalog_items:
            name = (item.get('nama_barang') or '').lower()
            if not name:
                continue

            # Exact substring match
            if name in clean_q and len(name) > best_len:
                best_match = item
                best_len = len(name)
                continue

            # Word tokens overlap
            tokens = [t for t in re.split(r'\W+', name) if len(t) >= 3]
            if tokens and all(t in clean_q for t in tokens) and len(name) > best_len:
                best_match = item
                best_len = len(name)

        return best_match

    def generate_response(self, user_query, store_context):
        """Synthesize natural, data-grounded Indonesian response locally."""
        catalog = store_context.get('all_items', []) or store_context.get('barang_kritis', [])
        mentioned_product = self.find_mentioned_product(user_query, catalog)

        # If a specific product was mentioned, provide its dedicated analytical dossier
        if mentioned_product:
            return self._build_product_dossier_response(mentioned_product, store_context)

        # Otherwise classify intent
        intent, score = self.classify_intent(user_query)

        # Fallback to general assistance if match confidence is too low
        if score < 0.18 and not any(k in user_query.lower() for k in ('halo', 'bantu', 'stok', 'omzet', 'laku', 'restok', 'beli')):
            return self._build_help_response(store_context)

        if intent == 'stok_kritis':
            return self._build_critical_stock_response(store_context)
        elif intent == 'omzet_hari_ini':
            return self._build_today_sales_response(store_context)
        elif intent == 'produk_terlaris':
            return self._build_top_seller_response(store_context)
        elif intent == 'dead_stock':
            return self._build_dead_stock_response(store_context)
        elif intent == 'bundling_promo':
            return self._build_bundling_response(store_context)
        elif intent == 'clustering_produk':
            return self._build_clustering_response(store_context)
        elif intent == 'evaluasi_model':
            return self._build_evaluation_metrics_response(store_context)
        elif intent == 'estimasi_anggaran':
            return self._build_budget_response(store_context)
        elif intent == 'anomali_toko':
            return self._build_anomaly_response(store_context)
        else:
            return self._build_help_response(store_context)

    # -------------------------------------------------------------------------
    # Intent Response Builders (Grounded in Database Context)
    # -------------------------------------------------------------------------

    def _build_product_dossier_response(self, item, ctx):
        nama = item.get('nama_barang', 'Produk')
        stok = item.get('stok_saat_ini', item.get('stok', 0))
        harga = item.get('harga', 0)
        terjual_28 = item.get('total_terjual_28_hari', item.get('terjual', 0))
        prediksi_7 = item.get('prediksi_penjualan', '-')
        rekomendasi = item.get('rekomendasi_restock', 0)
        sisa_hari = item.get('hari_habis_stok')
        tier = item.get('label_prioritas', item.get('tier_prioritas', 'Stok Terpantau'))
        metode = item.get('metode_peramalan', 'Random Forest / SES')

        lines = [
            f"### 📦 Profil Analisis Produk: **{nama}**",
            f"- **Stok Saat Ini**: **{stok} unit**",
            f"- **Harga Jual Satuan**: Rp {harga:,.2f}" if isinstance(harga, (int, float, Decimal)) else f"- **Harga Satuan**: Rp {harga}",
            f"- **Realisasi Penjualan (28 Hari)**: **{terjual_28} unit**",
            f"- **Prediksi Permintaan (7 Hari ke Depan)**: **{prediksi_7} unit** *(Metode: {metode})*",
        ]

        if sisa_hari is not None:
            lines.append(f"- **Ketahanan Stok**: Diperkirakan bertahan sekitar **{sisa_hari} hari** ke depan.")
        if rekomendasi and int(rekomendasi) > 0:
            modal = item.get('estimasi_modal_restok', '0.00')
            lines.append(f"- ⚠️ **Saran Restok**: Disarankan memesan **{rekomendasi} unit** (Estimasi modal: Rp {modal}). Status: **{tier}**.")
        else:
            lines.append(f"- ✅ **Status Stok**: Stok saat ini mencukupi target kebutuhan operasional.")

        return "\n".join(lines)

    def _build_critical_stock_response(self, ctx):
        kritis = ctx.get('barang_kritis', [])
        total_restok = ctx.get('total_barang_restok', len(kritis))
        anggaran = ctx.get('estimasi_biaya_restok', '0')

        if not kritis:
            return (
                "### ✅ Kondisi Stok Aman\n\n"
                "Seluruh produk dalam katalog saat ini memiliki stok yang mencukupi untuk kebutuhan operasional beberapa hari ke depan. "
                "Tidak ada produk dengan status rawan habis (kehabisan stok <= 2 hari)."
            )

        items_formatted = []
        for b in kritis[:8]:
            nama = b.get('nama_barang', 'Barang')
            stok = b.get('stok_saat_ini', b.get('stok', 0))
            hari = b.get('hari_habis_stok', '< 2')
            butuh = b.get('rekomendasi_restock', '-')
            items_formatted.append(f"- 🔴 **{nama}**: Sisa **{stok} unit** (habis dalam ~{hari} hari). Saran restok: **{butuh} unit**.")

        return (
            f"### ⚠️ Peringatan Stok Kritis ({len(kritis)} Produk)\n\n"
            f"Sistem mendeteksi **{len(kritis)} produk** yang berisiko habis dalam 1–2 hari ke depan dan harus diprioritaskan pembelanjaannya:\n\n"
            + "\n".join(items_formatted) +
            f"\n\n💰 **Estimasi Kebutuhan Modal Restok**: **Rp {anggaran}** untuk mengembalikan persediaan ke level aman 7 hari."
        )

    def _build_today_sales_response(self, ctx):
        tx_cnt = ctx.get('penjualan_hari_ini_transaksi', 0)
        unit_cnt = ctx.get('penjualan_hari_ini_unit', 0)
        omzet = ctx.get('penjualan_hari_ini_omzet', '0')
        tgl = ctx.get('tanggal', 'Hari ini')

        return (
            f"### 📊 Ringkasan Penjualan Hari Ini ({tgl})\n\n"
            f"- **Jumlah Transaksi Struk**: **{tx_cnt} transaksi**\n"
            f"- **Total Unit Barang Terjual**: **{unit_cnt} item/unit**\n"
            f"- **Total Omzet Kotor Terkumpul**: **Rp {omzet}**\n\n"
            f"💡 *Catatan: Data diperbarui secara real-time dari tabel transaksi kasir POS.*"
        )

    def _build_top_seller_response(self, ctx):
        top = ctx.get('top_seller', [])
        if not top:
            return "Belum ada rekaman transaksi penjualan yang mencukupi dalam 28 hari terakhir untuk menampilkan produk terlaris."

        rows = []
        for i, b in enumerate(top[:7]):
            nama = b.get('nama_barang', '')
            qty = b.get('terjual', 0)
            rows.append(f"{i+1}. 🏆 **{nama}** — **{qty} unit terjual**")

        return (
            f"### ⭐ Produk Terlaris (28 Hari Terakhir)\n\n"
            + "\n".join(rows) +
            f"\n\n💡 *Rekomendasi:* Pertahankan ketersediaan barang-barang ini dengan buffer stok yang cukup karena merupakan kontributor utama perputaran kas."
        )

    def _build_dead_stock_response(self, ctx):
        dead = ctx.get('barang_dead_stock', [])
        if not dead:
            return (
                "### 📦 Status Stok Mengendap (Dead Stock)\n\n"
                "Kabar baik! Tidak ditemukan produk mati/mengendap tanpa transaksi dalam 28 hari terakhir. "
                "Perputaran barang berjalan dengan baik."
            )

        items_str = "\n".join(
            f"- **{b.get('nama_barang')}**: stok mengendap **{b.get('stok_saat_ini', b.get('stok', 0))} unit**"
            for b in dead[:6]
        )
        return (
            f"### 📦 Evaluasi Barang Mengendap ({len(dead)} Produk)\n\n"
            f"Berikut produk yang memiliki stok tetapi tidak mencatat transaksi penjualan selama 28 hari terakhir:\n\n"
            f"{items_str}\n\n"
            f"💡 *Saran Tindakan:* Pertimbangkan membuat paket hemat/bundling dengan produk fast-moving atau memberikan diskon cuci gudang agar modal tidak macet."
        )

    def _build_bundling_response(self, ctx):
        popular_pairs = ctx.get('popular_pairs', [])
        if not popular_pairs:
            return (
                "### 💡 Analisis Keranjang Belanja (Market Basket)\n\n"
                "Belum cukup data transaksi multi-barang di POS untuk membentuk aturan asosiasi belanja. "
                "Gunakan form kasir dengan menambahkan beberapa barang sekaligus per transaksi struk untuk mengaktifkan fitur ini."
            )

        top_pair = popular_pairs[0]
        a_nama = top_pair.get('item_a_nama')
        b_nama = top_pair.get('item_b_nama')
        freq = top_pair.get('frekuensi')
        lift = top_pair.get('lift')

        return (
            f"### 💡 Rekomendasi Paket Bundling & Penempatan Kasir\n\n"
            f"Berdasarkan algoritma *Association Rule Mining* pada struk kasir:\n\n"
            f"1. **Paket Promo Duet:** Pasangkan **{a_nama}** + **{b_nama}** "
            f"(dibeli bersamaan sebanyak **{freq} kali**, skor Lift: **{lift}**).\n"
            f"2. **Strategi Tata Letak:** Letakkan produk pendamping di samping barang utama pada etalase kasir untuk memicu *impulse buying*."
        )

    def _build_clustering_response(self, ctx):
        cluster_info = ctx.get('clustering_info', {})
        if not cluster_info or cluster_info.get('status') == 'data_kosong':
            return (
                "### 🧩 Segmentasi Produk K-Means\n\n"
                "Sistem mengelompokkan katalog menjadi 3 segmen: **Fast-Moving**, **Stabil**, dan **Slow-Moving** "
                "berdasarkan kecepatan penjualan, rasio perputaran persediaan, dan kontribusi pendapatan 28 hari."
            )

        summary = cluster_info.get('ringkasan_klaster', {})
        fm = summary.get('FAST_MOVING', {})
        stb = summary.get('STABIL', {})
        sm = summary.get('SLOW_MOVING', {})

        return (
            f"### 🧩 Hasil Segmentasi Produk (K-Means Clustering)\n\n"
            f"- 🚀 **Fast-Moving ({fm.get('jumlah_produk', 0)} Produk)**: Produk perputaran cepat & omzet tertinggi. *Strategi:* Jaga persediaan pengaman.\n"
            f"- ⚖️ **Stabil ({stb.get('jumlah_produk', 0)} Produk)**: Penjualan reguler konsisten. *Strategi:* Restok berkala terjadwal.\n"
            f"- 🐌 **Slow-Moving ({sm.get('jumlah_produk', 0)} Produk)**: Perputaran rendah. *Strategi:* Bundling promo & evaluasi kuantitas pengadaan."
        )

    def _build_evaluation_metrics_response(self, ctx):
        mape = ctx.get('mape_gabungan', '-')
        mae = ctx.get('mae_gabungan', '-')
        rmse = ctx.get('rmse_gabungan', '-')
        ml_count = ctx.get('jumlah_model_ml_digunakan', 0)
        ses_count = ctx.get('jumlah_fallback_ses', 0)

        return (
            f"### 📈 Bukti Evaluasi Empiris Model Peramalan (Bab IV Skripsi)\n\n"
            f"- **Mean Absolute Percentage Error (MAPE)**: **{mape}%**\n"
            f"- **Mean Absolute Error (MAE)**: **{mae} unit**\n"
            f"- **Root Mean Squared Error (RMSE)**: **{rmse} unit**\n\n"
            f"**Komposisi Model Terpilih:**\n"
            f"- Random Forest Regressor (unggul atas baseline): **{ml_count} produk**\n"
            f"- Single Exponential Smoothing (SES baseline): **{ses_count} produk**\n\n"
            f"Evaluasi dihitung secara ketat melalui metode *rolling-origin backtest* dan *chronological cross-validation* tanpa pengacakan waktu."
        )

    def _build_budget_response(self, ctx):
        anggaran = ctx.get('estimasi_biaya_restok', '0')
        kritis = len(ctx.get('barang_kritis', []))
        total_restok = ctx.get('total_barang_restok', 0)

        return (
            f"### 💰 Alokasi Anggaran Belanja Restok\n\n"
            f"- **Total Kebutuhan Modal Restok**: **Rp {anggaran}**\n"
            f"- **Jumlah Barang Perlu Restok**: **{total_restok} jenis**\n"
            f"- **Prioritas Kritis Mendesak**: **{kritis} jenis barang**\n\n"
            f"💡 *Saran Finansial:* Alokasikan anggaran terlebih dahulu pada barang dengan prioritas **P1_KRITIS** "
            f"agar modal operasional berputar optimal dan tidak terjadi kehilangan omzet harian."
        )

    def _build_anomaly_response(self, ctx):
        anomalies = ctx.get('anomalies', [])
        if not anomalies:
            return (
                "### 🔍 Status Deteksi Anomali\n\n"
                "Sistem tidak mendeteksi anomali kritis pada pergerakan stok maupun transaksi kasir saat ini. "
                "Operasional toko berjalan dalam batas variasi normal."
            )

        items_str = "\n".join(
            f"- [{a.get('keparahan', 'info').upper()}] **{a.get('nama_barang', 'Produk')}**: {a.get('pesan')}"
            for a in anomalies[:5]
        )
        return (
            f"### 🔍 Laporan Deteksi Anomali Toko ({len(anomalies)} Temuan)\n\n"
            f"{items_str}\n\n"
            f"💡 *Deteksi didukung oleh Heuristik Lonjakan Penjualan, Kehabisan Stok, dan Isolation Forest.*"
        )

    def _build_help_response(self, ctx):
        total_barang = ctx.get('total_barang', 0)
        omzet = ctx.get('penjualan_hari_ini_omzet', '0')

        return (
            f"Halo! Saya Asisten AI Cerdas Toko Warti Jaya (100% Local Machine Learning & NLU).\n\n"
            f"Saat ini terdaftar **{total_barang} produk** dalam katalog toko dengan omzet hari ini **Rp {omzet}**.\n\n"
            f"Anda dapat menanyakan hal-hal seputar operasional toko kepada saya, seperti:\n"
            f"- *'Barang apa yang stoknya hampir habis?'*\n"
            f"- *'Berapa penjualan dan omzet hari ini?'*\n"
            f"- *'Apa saja produk paling laris?'*\n"
            f"- *'Barang apa yang termasuk dead stock?'*\n"
            f"- *'Ada rekomendasi paket bundling promo?'*\n"
            f"- *'Bagaimana hasil pengelompokan produk K-Means?'*\n"
            f"- *'Berapa akurasi model MAPE, MAE, dan RMSE?'*\n"
            f"- *'Cek stok [Nama Barang]'* (misal: *Cek stok Beras*)"
        )


# Global singleton instance
_nlu_engine = None


def get_local_nlu_engine():
    global _nlu_engine
    if _nlu_engine is None:
        _nlu_engine = LocalNLUEngine()
    return _nlu_engine
