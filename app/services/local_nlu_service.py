"""Local NLU and Offline AI Service for Toko Warti Jaya."""

from app.services.ai_response import SYSTEM_INSTRUCTION, clean_response


def generate_executive_insights(metrics):
    """Create a concise, conversational inventory summary without cloud services."""
    critical = metrics.get('barang_kritis', []) or []
    restock_count = metrics.get('jumlah_barang_direstok', 0)
    budget = metrics.get('total_anggaran_restok_formatted', '0')
    dead_stock = metrics.get('barang_dead_stock', []) or []
    total_barang = metrics.get('total_barang', 0)
    total_unit = metrics.get('total_unit_restock', 0)
    mape = metrics.get('mape_gabungan')
    ml_models = metrics.get('jumlah_model_ml_digunakan', 0)

    paragraphs = [
        f"Saat ini ada {total_barang} jenis barang. Sebanyak {restock_count} jenis perlu direstok, dengan kebutuhan total {total_unit} unit untuk mencapai target stok tujuh hari."
    ]
    if critical:
        names = ', '.join(
            f"{item.get('nama_barang', 'barang')} dengan sisa {item.get('stok_saat_ini', item.get('stok', 0))} unit"
            for item in critical[:5]
        )
        paragraphs.append(f"Yang perlu diprioritaskan adalah {names}, karena stoknya berisiko segera habis.")
    else:
        paragraphs.append('Belum ada barang dengan kondisi stok kritis.')
    paragraphs.append(f'Perkiraan anggaran pengadaan adalah Rp {budget}.')
    if dead_stock:
        names = ', '.join(
            f"{item.get('nama_barang', 'barang')} sebanyak {item.get('stok_saat_ini', item.get('stok', 0))} unit"
            for item in dead_stock[:3]
        )
        paragraphs.append(f"{names} belum terjual dalam 28 hari terakhir. Anda bisa meninjau harga, penempatan, atau membuat promosi untuk barang tersebut.")
    if mape is not None:
        paragraphs.append(f'Evaluasi peramalan mencatat MAPE {mape} persen pada {ml_models} produk.')
    return {'insight': clean_response('\n\n'.join(paragraphs)), 'sumber': 'local_ml'}


def ask_copilot(query, conversation_history, store_context, system_instruction=SYSTEM_INSTRUCTION):
    """Answer a store question using the local natural-language engine."""
    from algorithm.local_nlu import get_local_nlu_engine

    # The deterministic local response builders follow this same style contract.
    _ = system_instruction
    engine = get_local_nlu_engine()
    reply_text = clean_response(engine.generate_response(query, store_context))
    return {'reply': reply_text, 'sumber': 'local_nlu'}


def generate_market_basket_advice(popular_pairs, association_rules):
    """Create a conversational bundle suggestion from local basket analysis."""
    if not popular_pairs:
        advice = (
            'Belum tersedia cukup data transaksi beberapa barang dalam satu struk untuk melihat pola belanja bersama. '
            'Data tersebut akan membantu menentukan pasangan barang yang cocok ditawarkan sebagai paket.'
        )
    else:
        pair = popular_pairs[0]
        name_a = pair.get('item_a_nama', 'barang pertama')
        name_b = pair.get('item_b_nama', 'barang kedua')
        frequency = pair.get('frekuensi', 1)
        lift = pair.get('lift', 1.0)
        support = pair.get('support_persen', 0.0)
        advice = (
            f'{name_a} dan {name_b} tercatat dibeli bersama sebanyak {frequency} kali, '
            f'dengan support {support} persen dan lift {lift}. Anda bisa mencoba menawarkan '
            'keduanya sebagai paket hemat atau menempatkannya berdekatan.'
        )
    return {'advice': clean_response(advice), 'sumber': 'local_ml'}
