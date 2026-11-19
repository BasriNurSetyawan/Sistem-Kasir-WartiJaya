"""Retail anomaly and inventory shrinkage/dead stock detector.

Analyzes sales trends and inventory levels to identify:
1. Lonjakan Penjualan (Sudden demand spikes)
2. Penjualan Anjlok (Abrupt sales drop for normally active goods)
3. Rawan Habis (Stockout risk within <= 2 days)
4. Dead Stock (Unsold items with idle inventory >= 30 days)
"""

from datetime import timedelta
from decimal import Decimal
import math


def detect_sales_anomalies(items, daily_sales_by_item, today, lookback_days=28):
    """Detect inventory anomalies across items.

    Args:
        items: List of Barang instances or dicts with id, nama_barang, stok, harga.
        daily_sales_by_item: Dict[item_id, Dict[date, int]] containing daily sales.
        today: Current date.
        lookback_days: Days of historical sales to evaluate (default 28).

    Returns:
        List[dict]: List of detected anomalies with severity, category, and explanation.
    """
    if (not isinstance(lookback_days, int) or isinstance(lookback_days, bool)
            or lookback_days < 1):
        raise ValueError('lookback_days harus berupa bilangan bulat positif.')

    anomalies = []
    recent_days = min(7, lookback_days)
    recent_start = today - timedelta(days=recent_days - 1)
    previous_days = lookback_days - recent_days
    history_start = today - timedelta(days=lookback_days - 1)

    for item in items:
        item_id = item.id if hasattr(item, 'id') else item['id']
        nama = item.nama_barang if hasattr(item, 'nama_barang') else item['nama_barang']
        stok = item.stok if hasattr(item, 'stok') else item['stok']
        sales_map = daily_sales_by_item.get(item_id, {})

        # Compare the recent week (or available shorter range) to the rest of
        # the configured lookback without assuming it is always 28 days.
        sales_last_7 = sum(
            qty for d, qty in sales_map.items()
            if recent_start <= d <= today
        )
        sales_total_28 = sum(
            qty for d, qty in sales_map.items()
            if history_start <= d <= today
        )
        sales_prev_21 = max(0, sales_total_28 - sales_last_7)

        avg_daily_7 = sales_last_7 / float(recent_days)
        avg_daily_prev = (
            sales_prev_21 / float(previous_days)
            if previous_days > 0 and sales_prev_21 > 0 else 0.0
        )
        avg_daily_28 = sales_total_28 / float(lookback_days)

        # 1. Rawan Habis (Stockout Risk <= 2 days)
        if avg_daily_7 > 0:
            days_left = stok / avg_daily_7
            if days_left <= 2.0:
                severity = 'tinggi' if days_left <= 1.0 or stok == 0 else 'sedang'
                anomalies.append({
                    'barang_id': item_id,
                    'nama_barang': nama,
                    'tipe': 'rawan_habis',
                    'keparahan': severity,
                    'pesan': (
                        f"Stok tinggal {stok} unit, diperkirakan habis dalam {days_left:.1f} hari "
                        f"berdasarkan laju penjualan {recent_days} hari terakhir ({sales_last_7} unit)."
                    ),
                    'metrik': {
                        'stok': stok,
                        'rata_rata_harian_7h': round(avg_daily_7, 2),
                        'sisa_hari': round(days_left, 1),
                    },
                })

        # 2. Sales spike: recent average > 2x previous baseline with >= 5 units.
        if sales_last_7 >= 5 and avg_daily_prev > 0 and (avg_daily_7 >= 2.0 * avg_daily_prev):
            increase_pct = ((avg_daily_7 - avg_daily_prev) / avg_daily_prev) * 100
            anomalies.append({
                'barang_id': item_id,
                'nama_barang': nama,
                'tipe': 'lonjakan_penjualan',
                'keparahan': 'info',
                'pesan': (
                    f"Terjadi lonjakan penjualan sebesar {increase_pct:.0f}% dalam {recent_days} hari terakhir "
                    f"({sales_last_7} unit vs rata-rata periode sebelumnya)."
                ),
                'metrik': {
                    'penjualan_7h': sales_last_7,
                    'rata_rata_7h': round(avg_daily_7, 2),
                    'rata_rata_sebelumnya': round(avg_daily_prev, 2),
                    'persentase_kenaikan': round(increase_pct, 1),
                },
            })

        # 3. Abrupt drop: previously active, but no sales in the recent period.
        if sales_prev_21 >= 10 and sales_last_7 == 0 and stok > 0:
            anomalies.append({
                'barang_id': item_id,
                'nama_barang': nama,
                'tipe': 'penjualan_anjlok',
                'keparahan': 'sedang',
                'pesan': (
                    f"Barang tidak terjual sama sekali dalam {recent_days} hari terakhir meskipun stok tersedia ({stok} unit), "
                    f"padahal periode sebelumnya terjual {sales_prev_21} unit. Periksa posisi display atau harga."
                ),
                'metrik': {
                    'stok': stok,
                    'penjualan_21h_lalu': sales_prev_21,
                    'penjualan_7h': 0,
                },
            })

        # 4. Dead stock (stock > 0 but zero sales during the lookback).
        if stok > 0 and sales_total_28 == 0:
            anomalies.append({
                'barang_id': item_id,
                'nama_barang': nama,
                'tipe': 'dead_stock',
                'keparahan': 'sedang' if stok > 10 else 'rendah',
                'pesan': (
                    f"Barang mengendap ({stok} unit) tanpa transaksi penjualan selama {lookback_days} hari. "
                    f"Pertimbangkan program bundling atau penyesuaian harga."
                ),
                'metrik': {
                    'stok': stok,
                    'hari_tanpa_transaksi': lookback_days,
                },
            })

    # Sort anomalies by severity: tinggi -> sedang -> info -> rendah
    severity_order = {'tinggi': 0, 'sedang': 1, 'info': 2, 'rendah': 3}
    anomalies.sort(key=lambda a: severity_order.get(a['keparahan'], 4))
    return anomalies


def detect_transaction_anomalies(transactions):
    """Detect unusual cashier transactions using Isolation Forest.

    Identifies transactions with abnormal total amounts, item counts, or units,
    such as unusually large bulk orders, extreme high-value transactions,
    or unexpected cashier input values.

    Args:
        transactions (list of dict): Each dict contains:
            - 'transaksi_id': int or str
            - 'tanggal': str or date
            - 'total_harga': float or Decimal
            - 'total_item': int (jumlah jenis barang)
            - 'total_unit': int (total kuantitas fisik)

    Returns:
        list of dict: Detected anomalous transactions with explanation and scores.
    """
    if len(transactions) < 5:
        return []

    import numpy as np
    from sklearn.ensemble import IsolationForest

    features = []
    for tx in transactions:
        nominal = float(tx.get('total_harga', 0.0))
        items_cnt = float(tx.get('total_item', 1))
        unit_cnt = float(tx.get('total_unit', 1))
        features.append([nominal, items_cnt, unit_cnt])

    X = np.array(features, dtype=float)

    # Contamination set to 0.05 (up to 5% potential outlier transactions)
    model = IsolationForest(
        n_estimators=50,
        contamination=0.05,
        random_state=42,
        n_jobs=1,
    )
    preds = model.fit_predict(X)
    scores = model.decision_function(X)

    # Compute baseline medians for human-readable explanation
    median_nominal = float(np.median(X[:, 0]))
    median_unit = float(np.median(X[:, 2]))

    anomalies = []
    for i, tx in enumerate(transactions):
        if preds[i] == -1:  # Outlier
            nominal = float(tx.get('total_harga', 0.0))
            units = float(tx.get('total_unit', 1))
            score = float(scores[i])

            reasons = []
            if median_nominal > 0 and nominal >= 3.0 * median_nominal:
                reasons.append(f"Nominal transaksi (Rp {nominal:,.0f}) jauh di atas median normal (Rp {median_nominal:,.0f})")
            if median_unit > 0 and units >= 3.0 * median_unit:
                reasons.append(f"Volume pembelian ({units:.0f} unit) mengindikasikan pembelian grosir/partai besar")
            if not reasons:
                reasons.append("Kombinasi nominal belanja dan kuantitas berada di luar klaster transaksi reguler toko")

            anomalies.append({
                'transaksi_id': tx.get('transaksi_id'),
                'tanggal': str(tx.get('tanggal')),
                'total_harga': nominal,
                'total_item': int(tx.get('total_item', 1)),
                'total_unit': int(tx.get('total_unit', 1)),
                'tipe': 'transaksi_anomali_isolation_forest',
                'keparahan': 'info' if nominal > 0 else 'sedang',
                'skor_anomali': round(score, 4),
                'penjelasan': "; ".join(reasons),
            })

    anomalies.sort(key=lambda a: a['skor_anomali'])
    return anomalies
