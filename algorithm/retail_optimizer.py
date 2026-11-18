"""Retail inventory restock prioritization and budget estimation optimizer.

Computes:
1. Days of Supply / Runout projection (hari_habis_stok).
2. Multi-factor Restock Priority Score (0-100) combining stockout urgency, velocity, and value.
3. Priority Tier: P1_KRITIS, P2_TINGGI, P3_SEDANG, P4_CUKUP, P5_DEAD_STOCK.
4. Capital budget estimation for replenishment.
"""

from decimal import Decimal


def calculate_restock_priority(stok, prediksi_harian, rekomendasi_restok, harga, total_terjual_28h):
    """Calculate multi-criteria inventory priority score and classification.

    Args:
        stok (int): Current stock.
        prediksi_harian (float or Decimal or None): Expected daily sales rate.
        rekomendasi_restok (int): Recommended restock quantity.
        harga (Decimal or float): Unit selling price.
        total_terjual_28h (int): Cumulative sales over last 28 days.

    Returns:
        dict: Priority score, runout days, tier, and budget requirement.
    """
    daily_rate = float(prediksi_harian) if prediksi_harian and float(prediksi_harian) > 0 else 0.0
    price_val = Decimal(str(harga)) if harga is not None else Decimal('0.00')

    # Runout days
    runout_days = round(stok / daily_rate, 1) if daily_rate > 0 else None

    # Priority determination
    if total_terjual_28h == 0 and stok > 0:
        tier = 'P5_DEAD_STOCK'
        label = 'Dead Stock (Mengendap)'
        score = 5
    elif stok == 0 and daily_rate > 0:
        tier = 'P1_KRITIS'
        label = 'Kritis (Stok Kosong)'
        score = 98
    elif runout_days is not None and runout_days <= 2.0:
        tier = 'P1_KRITIS'
        label = 'Kritis (Habis <= 2 Hari)'
        score = 90 + int(max(0, 2.0 - runout_days) * 4)
    elif runout_days is not None and runout_days <= 5.0:
        tier = 'P2_TINGGI'
        label = 'Tinggi (Habis 3-5 Hari)'
        score = 70 + int((5.0 - runout_days) * 5)
    elif rekomendasi_restok > 0:
        tier = 'P3_SEDANG'
        label = 'Sedang (Di Bawah Target)'
        score = 40 + min(25, int(rekomendasi_restok * 2))
    elif total_terjual_28h == 0:
        tier = 'P5_DEAD_STOCK'
        label = 'Tanpa Penjualan'
        score = 0
    else:
        tier = 'P4_CUKUP'
        label = 'Stok Cukup'
        score = 15

    # Budget needed for restock
    estimasi_modal = price_val * Decimal(rekomendasi_restok)

    return {
        'skor_prioritas': min(100, max(0, score)),
        'tier_prioritas': tier,
        'label_prioritas': label,
        'hari_habis_stok': runout_days,
        'estimasi_modal_restok': estimasi_modal,
    }
