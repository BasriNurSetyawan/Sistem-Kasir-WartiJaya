"""Lazy public exports for forecasting and retail algorithms.

Keeping package import light avoids loading NumPy and scikit-learn during Flask
startup when no prediction or clustering request has been made yet.
"""

from importlib import import_module

_EXPORTS = {
    'peramalkan_ses': ('algorithm.ses', 'peramalkan_ses'),
    'proyeksikan_permintaan': ('algorithm.ses', 'proyeksikan_permintaan'),
    'peramalkan_random_forest': ('algorithm.ml_forecast', 'peramalkan_random_forest'),
    'detect_sales_anomalies': ('algorithm.anomaly_detector', 'detect_sales_anomalies'),
    'detect_transaction_anomalies': ('algorithm.anomaly_detector', 'detect_transaction_anomalies'),
    'analyze_market_baskets': ('algorithm.market_basket', 'analyze_market_baskets'),
    'get_cross_sell_suggestions': ('algorithm.market_basket', 'get_cross_sell_suggestions'),
    'calculate_restock_priority': ('algorithm.retail_optimizer', 'calculate_restock_priority'),
    'cluster_products': ('algorithm.product_clustering', 'cluster_products'),
    'LocalNLUEngine': ('algorithm.local_nlu', 'LocalNLUEngine'),
    'get_local_nlu_engine': ('algorithm.local_nlu', 'get_local_nlu_engine'),
}


def __getattr__(name):
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}') from exc
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value

__all__ = [
    *_EXPORTS,
]
