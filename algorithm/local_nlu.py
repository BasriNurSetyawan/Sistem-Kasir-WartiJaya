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
        name = item.get('nama_barang', 'produk ini')
        stock = item.get('stok_saat_ini', item.get('stok', 0))
        price = item.get('harga', 0)
        sold = item.get('total_terjual_28_hari', item.get('terjual', 0))
        forecast = item.get('prediksi_penjualan', '-')
        restock = item.get('rekomendasi_restock', 0)
        runout = item.get('hari_habis_stok')
        model = item.get('metode_peramalan', 'model lokal')

        if isinstance(price, (int, float, Decimal)):
            price_text = f'Rp {price:,.2f}'
        else:
            price_text = f'Rp {price}'
        answer = (
            f'{name} saat ini memiliki stok {stock} unit dengan harga jual {price_text}. '
            f'Dalam 28 hari terakhir, barang ini terjual {sold} unit dan perkiraan penjualan '
            f'untuk tujuh hari ke depan adalah {forecast} unit berdasarkan {model}.'
        )
        if runout is not None:
            answer += f' Dengan laju penjualan sekarang, stok diperkirakan bertahan sekitar {runout} hari.'
        if restock and int(restock) > 0:
            cost = item.get('estimasi_modal_restok', '0.00')
            answer += f' Saya sarankan menambah {restock} unit dengan perkiraan biaya Rp {cost}.'
        else:
            answer += ' Stoknya masih cukup untuk target operasional saat ini.'
        return answer

    def _build_critical_stock_response(self, ctx):
        critical = ctx.get('barang_kritis', [])
        if not critical:
            return 'Untuk saat ini stok barang masih cukup. Belum ada barang yang diperkirakan habis dalam dua hari.'

        names = []
        for item in critical[:4]:
            name = item.get('nama_barang', 'barang')
            stock = item.get('stok_saat_ini', item.get('stok', 0))
            days = item.get('hari_habis_stok')
            detail = f'{name} dengan sisa {stock} unit'
            if days is not None:
                detail += f', diperkirakan habis dalam {days} hari'
            names.append(detail)
        answer = f'Ada {len(critical)} barang yang perlu segera diperhatikan: {"; ".join(names)}.'
        if len(critical) > len(names):
            answer += f' Masih ada {len(critical) - len(names)} barang kritis lainnya.'
        budget = ctx.get('estimasi_biaya_restok')
        if budget:
            answer += f' Perkiraan biaya untuk memenuhi kebutuhan restok adalah Rp {budget}.'
        return answer

    def _build_today_sales_response(self, ctx):
        date_text = ctx.get('tanggal', 'hari ini')
        transactions = ctx.get('penjualan_hari_ini_transaksi', 0)
        units = ctx.get('penjualan_hari_ini_unit', 0)
        revenue = ctx.get('penjualan_hari_ini_omzet', '0')
        return (
            f'Pada {date_text}, toko mencatat {transactions} transaksi dengan total {units} unit terjual. '
            f'Omzet kotornya Rp {revenue}.'
        )

    def _build_top_seller_response(self, ctx):
        top_items = ctx.get('top_seller', [])
        if not top_items:
            return 'Belum ada penjualan yang tercatat dalam 28 hari terakhir, jadi saya belum bisa menentukan barang terlaris.'
        names = [
            f"{item.get('nama_barang', 'barang')} sebanyak {item.get('terjual', 0)} unit"
            for item in top_items[:4]
        ]
        return f"Barang yang paling banyak terjual dalam 28 hari terakhir adalah {', '.join(names)}."

    def _build_dead_stock_response(self, ctx):
        dead_items = ctx.get('barang_dead_stock', [])
        if not dead_items:
            return 'Tidak ada barang bersisa stok yang terdeteksi tanpa penjualan selama 28 hari terakhir.'
        names = [
            f"{item.get('nama_barang', 'barang')} dengan stok {item.get('stok_saat_ini', item.get('stok', 0))} unit"
            for item in dead_items[:4]
        ]
        answer = f"Beberapa barang belum terjual selama 28 hari terakhir: {', '.join(names)}."
        answer += ' Coba evaluasi harga, penempatan barang, atau tawarkan bersama barang yang lebih laris.'
        return answer

    def _build_bundling_response(self, ctx):
        pairs = ctx.get('popular_pairs', [])
        if not pairs:
            return 'Belum ada cukup transaksi beberapa barang dalam satu struk untuk melihat pola belanja bersama.'
        pair = pairs[0]
        name_a = pair.get('item_a_nama', 'barang pertama')
        name_b = pair.get('item_b_nama', 'barang kedua')
        frequency = pair.get('frekuensi', 0)
        return (
            f'{name_a} dan {name_b} paling sering tercatat bersama, sebanyak {frequency} kali. '
            'Keduanya bisa dipertimbangkan untuk ditawarkan sebagai paket atau ditempatkan berdekatan.'
        )

    def _build_clustering_response(self, ctx):
        info = ctx.get('clustering_info', {})
        if not info or info.get('status') == 'data_kosong':
            return 'Belum ada data barang yang cukup untuk mengelompokkan produk berdasarkan pergerakan penjualannya.'
        summary = info.get('ringkasan_klaster', {})
        fast = summary.get('FAST_MOVING', {}).get('jumlah_produk', 0)
        stable = summary.get('STABIL', {}).get('jumlah_produk', 0)
        slow = summary.get('SLOW_MOVING', {}).get('jumlah_produk', 0)
        dead = summary.get('DEAD_STOCK', {}).get('jumlah_produk', 0)
        answer = f'Pengelompokan saat ini mencatat {fast} barang laris, {stable} barang dengan penjualan stabil, dan {slow} barang lambat terjual.'
        if dead:
            answer += f' Ada juga {dead} barang tanpa penjualan yang perlu ditinjau.'
        return answer

    def _build_evaluation_metrics_response(self, ctx):
        mape = ctx.get('mape_gabungan')
        mae = ctx.get('mae_gabungan')
        rmse = ctx.get('rmse_gabungan')
        if mape is None and mae is None and rmse is None:
            return 'Data penjualan saat ini belum cukup untuk menghitung hasil evaluasi model peramalan.'
        details = []
        if mape is not None:
            details.append(f'MAPE {mape} persen')
        if mae is not None:
            details.append(f'MAE {mae} unit')
        if rmse is not None:
            details.append(f'RMSE {rmse} unit')
        return f'Hasil evaluasi peramalan yang tersedia adalah {", ".join(details)}.'

    def _build_budget_response(self, ctx):
        budget = ctx.get('estimasi_biaya_restok', '0')
        restock_count = ctx.get('total_barang_restok', 0)
        critical_count = len(ctx.get('barang_kritis', []))
        return (
            f'Perkiraan modal restok saat ini Rp {budget} untuk {restock_count} jenis barang. '
            f'Dari jumlah itu, {critical_count} barang masuk prioritas kritis.'
        )

    def _build_anomaly_response(self, ctx):
        anomalies = ctx.get('anomalies', [])
        if not anomalies:
            return 'Saya belum menemukan perubahan stok atau transaksi yang perlu diperiksa saat ini.'
        descriptions = [
            f"{item.get('nama_barang', 'transaksi')} ({item.get('keparahan', 'informasi')}): {item.get('pesan', 'perlu diperiksa')}"
            for item in anomalies[:3]
        ]
        answer = f'Ada {len(anomalies)} temuan yang perlu diperhatikan. ' + ' '.join(descriptions)
        if len(anomalies) > len(descriptions):
            answer += f' Masih ada {len(anomalies) - len(descriptions)} temuan lainnya.'
        return answer

    def _build_help_response(self, ctx):
        count = ctx.get('total_barang', 0)
        revenue = ctx.get('penjualan_hari_ini_omzet', '0')
        return (
            f'Halo, saya bisa membantu memeriksa stok dari {count} jenis barang dan omzet hari ini sebesar Rp {revenue}. '
            'Silakan tanyakan stok barang tertentu, penjualan hari ini, barang terlaris, kebutuhan restok, atau pola belanja pelanggan.'
        )


# Global singleton instance
_nlu_engine = None


def get_local_nlu_engine():
    global _nlu_engine
    if _nlu_engine is None:
        _nlu_engine = LocalNLUEngine()
    return _nlu_engine
