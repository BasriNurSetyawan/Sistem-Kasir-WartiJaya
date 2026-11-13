from decimal import Decimal, ROUND_CEILING


def proyeksikan_permintaan(penjualan_harian, jumlah_hari):
    """Project demand by extending the observed calendar-day average."""
    if (not isinstance(jumlah_hari, int) or isinstance(jumlah_hari, bool)
            or jumlah_hari <= 0):
        raise ValueError('jumlah_hari harus berupa bilangan bulat positif.')
    if not penjualan_harian:
        raise ValueError('Minimal satu hari histori penjualan diperlukan.')
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0
           for value in penjualan_harian):
        raise ValueError('Penjualan harian harus berupa bilangan bulat tidak negatif.')

    total = sum(penjualan_harian)
    rata_rata = Decimal(total) / Decimal(len(penjualan_harian))
    proyeksi = rata_rata * jumlah_hari
    return rata_rata, int(proyeksi.to_integral_value(rounding=ROUND_CEILING))
