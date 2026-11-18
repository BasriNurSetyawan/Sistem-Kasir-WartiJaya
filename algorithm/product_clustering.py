"""Product Behavior Clustering using K-Means.

Clusters retail products based on behavioral metrics:
1. Sales Velocity (unit terjual / hari dalam 28 hari)
2. Inventory Turnover Ratio (kecepatan perputaran stok)
3. Revenue Contribution (kontribusi omzet = unit terjual * harga)

Assigns actionable business tiers:
- Fast-Moving (Pilar omzet, perputaran cepat, prioritas stok pengaman)
- Stabil (Perputaran reguler, restok berkala terencana)
- Slow-Moving / Dead Stock (Perputaran lambat, perlu promosi bundling atau evaluasi)
"""

from decimal import Decimal
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


def cluster_products(products_data):
    """Cluster store products based on sales velocity, turnover, and revenue.

    Args:
        products_data (list of dict): Each dict contains:
            - 'barang_id': int
            - 'nama_barang': str
            - 'stok': int
            - 'harga': Decimal or float
            - 'total_terjual_28h': int

    Returns:
        dict: {
            'status': str,
            'total_produk': int,
            'klaster': list of dict (product list with cluster tags),
            'ringkasan_klaster': dict of cluster profiles,
        }
    """
    total_items = len(products_data)
    if total_items == 0:
        return {
            'status': 'data_kosong',
            'total_produk': 0,
            'klaster': [],
            'ringkasan_klaster': {},
        }

    # Extract feature matrix
    items = []
    features = []

    for p in products_data:
        stok = max(0, int(p.get('stok', 0)))
        terjual = max(0, int(p.get('total_terjual_28h', 0)))
        harga = float(p.get('harga', 0.0))

        # Velocity: units sold per day
        velocity = terjual / 28.0
        # Turnover: ratio of sold units to stock
        turnover = terjual / float(max(1, stok))
        # Revenue in 28 days
        revenue = float(Decimal(str(terjual)) * Decimal(str(harga)))

        features.append([velocity, turnover, revenue])
        items.append({
            'barang_id': p.get('barang_id', p.get('id')),
            'nama_barang': p.get('nama_barang', ''),
            'stok': stok,
            'harga': harga,
            'terjual_28h': terjual,
            'velocity': round(velocity, 2),
            'turnover': round(turnover, 2),
            'revenue_28h': round(revenue, 2),
        })

    # If items < 3, assign rules directly without KMeans
    if total_items < 3:
        for it in items:
            if it['terjual_28h'] >= 10:
                tag, label = 'FAST_MOVING', 'Fast-Moving (Perputaran Cepat)'
                advice = 'Pertahankan stok pengaman agar tidak kehilangan potensi penjualan.'
            elif it['terjual_28h'] > 0:
                tag, label = 'STABIL', 'Stabil (Perputaran Reguler)'
                advice = 'Lakukan restok rutin sesuai kebutuhan mingguan.'
            else:
                tag, label = 'SLOW_MOVING', 'Slow-Moving / Dead Stock'
                advice = 'Gunakan strategi promosi bundling atau evaluasi harga jual.'
            it['klaster_id'] = 0
            it['klaster_tag'] = tag
            it['klaster_label'] = label
            it['rekomendasi_tindakan'] = advice

        return {
            'status': 'klaster_berbasis_aturan_sampel_kecil',
            'total_produk': total_items,
            'klaster': items,
            'ringkasan_klaster': {
                'jumlah_klaster': 1,
                'metode': 'Heuristik Sampel Terbatas (< 3 produk)',
            },
        }

    X = np.array(features, dtype=float)

    # Standardize features (Z-score normalization)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Number of clusters: k = 3
    k = 3
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)

    # Calculate mean score for each cluster (weighted by velocity + revenue) to rank them
    cluster_scores = {}
    for c_id in range(k):
        c_mask = (labels == c_id)
        if np.any(c_mask):
            mean_vel = np.mean(X[c_mask, 0])
            mean_rev = np.mean(X[c_mask, 2])
            cluster_scores[c_id] = (mean_vel, mean_rev)
        else:
            cluster_scores[c_id] = (0.0, 0.0)

    # Rank clusters: 0 = Fast-Moving (highest), 1 = Stabil, 2 = Slow-Moving
    ranked_clusters = sorted(
        cluster_scores.keys(),
        key=lambda cid: (cluster_scores[cid][0], cluster_scores[cid][1]),
        reverse=True,
    )
    cluster_mapping = {
        ranked_clusters[0]: (
            'FAST_MOVING',
            'Fast-Moving (Produk Unggulan)',
            'Pilar penjualan toko dengan perputaran tinggi. Pastikan stok selalu tersedia dengan buffer pengaman.',
        ),
        ranked_clusters[1]: (
            'STABIL',
            'Stabil (Perputaran Sedang)',
            'Penjualan stabil dan teratur. Jadwalkan restok berkala mingguan.',
        ),
        ranked_clusters[2]: (
            'SLOW_MOVING',
            'Slow-Moving (Perputaran Rendah)',
            'Penjualan rendah atau mengendap. Buat paket bundling dengan produk Fast-Moving atau terapkan diskon cuci gudang.',
        ),
    }

    # Assign metadata to items
    for i, it in enumerate(items):
        raw_cluster = int(labels[i])
        tag, label_name, advice = cluster_mapping[raw_cluster]

        # Specific dead-stock override if 0 sales and stock > 0
        if it['terjual_28h'] == 0 and it['stok'] > 0:
            tag = 'DEAD_STOCK'
            label_name = 'Dead Stock (Mengendap)'
            advice = 'Barang mengendap tanpa penjualan selama 28 hari. Terapkan bundling promo atau diskon cuci gudang.'

        it['klaster_id'] = raw_cluster
        it['klaster_tag'] = tag
        it['klaster_label'] = label_name
        it['rekomendasi_tindakan'] = advice

    # Summary by cluster
    summary = {}
    for cid in range(k):
        tag, label_name, advice = cluster_mapping[cid]
        c_items = [it for it in items if it['klaster_id'] == cid]
        summary[tag] = {
            'nama_klaster': label_name,
            'jumlah_produk': len(c_items),
            'rata_rata_unit_28h': round(float(np.mean([it['terjual_28h'] for it in c_items])), 1) if c_items else 0,
            'rata_rata_omzet_28h': round(float(np.mean([it['revenue_28h'] for it in c_items])), 2) if c_items else 0,
            'rekomendasi_strategis': advice,
        }

    return {
        'status': 'sukses_kmeans',
        'metode': 'K-Means Clustering (StandardScaler, k=3)',
        'total_produk': total_items,
        'klaster': items,
        'ringkasan_klaster': summary,
    }
