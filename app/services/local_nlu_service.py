"""Local NLU and Offline AI Service for Toko Warti Jaya.

100% Local AI & Machine Learning without external API keys or cloud dependencies.
Provides:
1. Executive inventory, clustering, and restock insights.
2. Interactive conversational local Copilot powered by TF-IDF & Cosine Similarity.
3. Promotional bundling & merchandising strategies from market basket association rules.
"""

from decimal import Decimal
from algorithm.local_nlu import get_local_nlu_engine


def generate_executive_insights(metrics):
    """Generate executive business & restock insights from store metrics completely offline.

    Args:
        metrics (dict): Aggregated store statistics, restock plans, critical items.

    Returns:
        dict: {'insight': str, 'sumber': 'local_ml'}
    """
    critical = metrics.get('barang_kritis', [])
    restock_count = metrics.get('jumlah_barang_direstok', 0)
    budget = metrics.get('total_anggaran_restok_formatted', '0')
    dead_stock = metrics.get('barang_dead_stock', [])
    total_barang = metrics.get('total_barang', 0)
    total_unit = metrics.get('total_unit_restock', 0)
    mape = metrics.get('mape_gabungan')
    ml_models = metrics.get('jumlah_model_ml_digunakan', 0)

    lines = [
        "### 📊 Ringkasan Eksekutif Inventori & Pengadaan (Local AI & Machine Learning)",
        f"- **Kondisi Umum Katalog**: Terdaftar **{total_barang}** jenis barang. Sebanyak **{restock_count}** produk berada di bawah ambang target stok aman 7 hari ke depan dengan total kebutuhan pengadaan **{total_unit} unit**.",
    ]

    if critical:
        crit_names = ", ".join(
            f"**{b.get('nama_barang')}** (sisa {b.get('stok_saat_ini', b.get('stok', 0))} unit)"
            for b in critical[:5]
        )
        lines.append(
            f"- ⚠️ **Prioritas Kritis Segera (P1_KRITIS)**: {crit_names}. "
            f"Produk ini berisiko kehabisan persediaan dalam 1–2 hari kerja dan harus diutamakan dalam pembelanjaan modal."
        )
    else:
        lines.append("- ✅ **Kondisi Persediaan Kritis**: Nihil. Seluruh stok produk mencukupi kebutuhan operasional harian.")

    lines.append(
        f"- 💰 **Kebutuhan Anggaran Pembelanjaan**: Estimasi alokasi dana untuk memenuhi target stok seluruh barang adalah **Rp {budget}**."
    )

    if dead_stock:
        ds_names = ", ".join(
            f"**{b.get('nama_barang')}** ({b.get('stok_saat_ini', b.get('stok', 0))} unit)"
            for b in dead_stock[:3]
        )
        lines.append(
            f"- 📦 **Barang Mengendap (Dead Stock / Slow-Moving)**: {ds_names}. "
            f"Barang ini tidak mencatat transaksi dalam 28 hari. Disarankan membuat paket bundling atau penataan display ulang di dekat kasir."
        )

    if mape is not None:
        lines.append(
            f"- 📈 **Kualitas Model Cerdas**: Evaluasi peramalan gabungan mencatat MAPE **{mape}%** "
            f"dengan **{ml_models} produk** berhasil dioptimalkan oleh Random Forest Regressor melampaui baseline SES."
        )

    return {
        'insight': "\n\n".join(lines),
        'sumber': 'local_ml',
    }


def ask_copilot(query, conversation_history, store_context):
    """Answer user questions about store stock, sales, and operations using local NLU.

    Args:
        query (str): User's natural language question in Indonesian.
        conversation_history (list): Previous messages.
        store_context (dict): Current live database snapshot.

    Returns:
        dict: {'reply': str, 'sumber': 'local_nlu'}
    """
    engine = get_local_nlu_engine()
    reply_text = engine.generate_response(query, store_context)

    return {
        'reply': reply_text,
        'sumber': 'local_nlu',
    }


def generate_market_basket_advice(popular_pairs, association_rules):
    """Generate bundle strategy advice from market basket association rules locally.

    Args:
        popular_pairs (list): Frequently co-purchased item pairs.
        association_rules (list): Association rules with confidence and lift.

    Returns:
        dict: {'advice': str, 'sumber': 'local_ml'}
    """
    if not popular_pairs:
        return {
            'advice': (
                "Belum tersedia cukup data transaksi kasir multi-barang untuk membentuk paket bundling otomatis. "
                "Gunakan checkout form kasir dengan menambahkan beberapa item dalam satu struk untuk menghasilkan pola keranjang belanja."
            ),
            'sumber': 'local_ml',
        }

    top_pair = popular_pairs[0]
    name_a = top_pair.get('item_a_nama', 'Barang A')
    name_b = top_pair.get('item_b_nama', 'Barang B')
    freq = top_pair.get('frekuensi', 1)
    lift = top_pair.get('lift', 1.0)
    supp = top_pair.get('support_persen', 0.0)

    advice_text = (
        f"### 💡 Rekomendasi Paket Bundling & Penataan Kasir (Association Rule Mining)\n\n"
        f"1. **Paket Promo Duet:** Pasangkan **{name_a}** dan **{name_b}** "
        f"dalam satu paket hemat (dibeli bersamaan sebanyak **{freq} kali**, Support: **{supp}%**, Lift: **{lift}**).\n"
        f"2. **Penataan Display Rak:** Letakkan produk pendamping di dekat meja kasir atau bersebelahan pada rak display untuk memicu pembelian impulsif (*impulse buying*)."
    )

    return {
        'advice': advice_text,
        'sumber': 'local_ml',
    }
