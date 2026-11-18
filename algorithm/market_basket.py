"""Market basket analysis and retail association rule mining.

Analyzes receipt itemsets from POS checkouts to discover:
1. Product affinities (which items are frequently bought together).
2. Dynamic cross-sell recommendations for active cashier carts.
3. Bundle promo opportunities with Support, Confidence, and Lift metrics.
"""

from collections import Counter, defaultdict
from itertools import combinations


def analyze_market_baskets(receipts, item_names_map, min_support_count=1):
    """Analyze baskets of items bought together in the same transactions.

    Args:
        receipts: List of sets/lists containing item_ids for each checkout.
        item_names_map: Dict[item_id, item_name]
        min_support_count: Minimum transaction occurrences for an item pair.

    Returns:
        dict: Summary of rules, frequent pairs, and total receipts analyzed.
    """
    total_receipts = len(receipts)
    if total_receipts < 2:
        return {
            'total_transaksi': total_receipts,
            'aturan_asosiasi': [],
            'pasangan_populer': [],
            'status': 'data_transaksi_terbatas',
        }

    item_counts = Counter()
    pair_counts = Counter()

    for receipt in receipts:
        unique_items = sorted(set(receipt))
        for item in unique_items:
            item_counts[item] += 1
        for pair in combinations(unique_items, 2):
            pair_counts[pair] += 1

    rules = []
    popular_pairs = []

    for (item_a, item_b), pair_count in pair_counts.items():
        if pair_count < min_support_count:
            continue

        support = pair_count / total_receipts
        prob_a = item_counts[item_a] / total_receipts
        prob_b = item_counts[item_b] / total_receipts

        # Rule A -> B
        conf_a_b = pair_count / item_counts[item_a]
        lift_a_b = support / (prob_a * prob_b) if (prob_a * prob_b) > 0 else 1.0

        # Rule B -> A
        conf_b_a = pair_count / item_counts[item_b]
        lift_b_a = support / (prob_a * prob_b) if (prob_a * prob_b) > 0 else 1.0

        name_a = item_names_map.get(item_a, f"Barang #{item_a}")
        name_b = item_names_map.get(item_b, f"Barang #{item_b}")

        popular_pairs.append({
            'item_a_id': item_a,
            'item_a_nama': name_a,
            'item_b_id': item_b,
            'item_b_nama': name_b,
            'frekuensi': pair_count,
            'support_persen': round(support * 100, 1),
            'lift': round(lift_a_b, 2),
        })

        if lift_a_b >= 1.0:
            rules.append({
                'jika_beli_id': item_a,
                'jika_beli_nama': name_a,
                'sarankan_id': item_b,
                'sarankan_nama': name_b,
                'frekuensi_bersama': pair_count,
                'confidence_persen': round(conf_a_b * 100, 1),
                'lift': round(lift_a_b, 2),
            })
        if lift_b_a >= 1.0:
            rules.append({
                'jika_beli_id': item_b,
                'jika_beli_nama': name_b,
                'sarankan_id': item_a,
                'sarankan_nama': name_a,
                'frekuensi_bersama': pair_count,
                'confidence_persen': round(conf_b_a * 100, 1),
                'lift': round(lift_b_a, 2),
            })

    popular_pairs.sort(key=lambda p: (p['frekuensi'], p['lift']), reverse=True)
    rules.sort(key=lambda r: (r['lift'], r['confidence_persen']), reverse=True)

    return {
        'total_transaksi': total_receipts,
        'aturan_asosiasi': rules[:20],
        'pasangan_populer': popular_pairs[:10],
        'status': 'analisis_tersedia' if popular_pairs else 'belum_ada_pola',
    }


def get_cross_sell_suggestions(cart_item_ids, association_rules, limit=3):
    """Given item IDs currently in a cashier cart, return recommended complimentary items.

    Args:
        cart_item_ids: List[int] of item IDs already in cart.
        association_rules: List[dict] from analyze_market_baskets.
        limit: Max recommendations to return.

    Returns:
        List[dict]: Suggested items with reason, confidence, and lift.
    """
    cart_set = set(cart_item_ids)
    candidates = {}

    for rule in association_rules:
        if rule['jika_beli_id'] in cart_set and rule['sarankan_id'] not in cart_set:
            target_id = rule['sarankan_id']
            # If already present, keep the highest lift rule
            if target_id not in candidates or rule['lift'] > candidates[target_id]['lift']:
                candidates[target_id] = {
                    'barang_id': target_id,
                    'nama_barang': rule['sarankan_nama'],
                    'alasan': f"Sering dibeli bersama {rule['jika_beli_nama']} (Confidence {rule['confidence_persen']}%, Lift {rule['lift']})",
                    'lift': rule['lift'],
                    'confidence_persen': rule['confidence_persen'],
                }

    ranked = sorted(candidates.values(), key=lambda c: (c['lift'], c['confidence_persen']), reverse=True)
    return ranked[:limit]
