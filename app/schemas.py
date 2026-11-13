from datetime import date
from decimal import Decimal, InvalidOperation

from flask import request

MAX_INTEGER = 9_223_372_036_854_775_807
MAX_PRICE = Decimal('999999999999.99')


def json_object():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError('Body harus berupa objek JSON.')
    return data


def integer(value, field, *, minimum=0):
    if (isinstance(value, bool) or not isinstance(value, int)
            or value < minimum or value > MAX_INTEGER):
        raise ValueError(f'{field} harus berupa bilangan bulat >= {minimum}.')
    return value


def parse_date(value, field):
    if not isinstance(value, str):
        raise ValueError(f'{field} harus berformat YYYY-MM-DD.')
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f'{field} harus berformat YYYY-MM-DD yang valid.') from exc
    if parsed.isoformat() != value:
        raise ValueError(f'{field} harus berformat YYYY-MM-DD yang valid.')
    return parsed


def price(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError('harga harus berupa angka finite yang tidak negatif.')
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > MAX_PRICE:
            raise ValueError
        rounded = amount.quantize(Decimal('0.01'))
        if rounded != amount or rounded > MAX_PRICE:
            raise ValueError
        return rounded
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('harga harus berupa angka finite dengan maksimal 2 desimal.') from exc


def new_item(data):
    name = data.get('nama_barang')
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
        raise ValueError('nama_barang wajib berupa teks sepanjang 1 sampai 100 karakter.')
    return {
        'nama_barang': name.strip(),
        'stok': integer(data.get('stok'), 'stok'),
        'harga': price(data.get('harga')),
    }


def pagination_args(args):
    try:
        page = integer(int(args.get('page', '1')), 'page', minimum=1)
        per_page = integer(int(args.get('per_page', '20')), 'per_page', minimum=1)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    if per_page > 100:
        raise ValueError('per_page maksimal 100.')
    return page, per_page


def sale_args(data, today):
    item_id = integer(data.get('barang_id'), 'barang_id', minimum=1)
    quantity = integer(data.get('jumlah_terjual'), 'jumlah_terjual', minimum=1)
    sold_on = parse_date(data['tanggal'], 'tanggal') if 'tanggal' in data else today
    if sold_on > today:
        raise ValueError('tanggal tidak boleh berada di masa depan.')
    return item_id, quantity, sold_on


def report_args(args, today, max_days):
    until = parse_date(args['sampai'], 'sampai') if 'sampai' in args else today
    start = parse_date(args['dari'], 'dari') if 'dari' in args else until
    if start > until:
        raise ValueError('dari tidak boleh melewati sampai.')
    if until > today:
        raise ValueError('tanggal rekap tidak boleh berada di masa depan.')
    if (until - start).days + 1 > max_days:
        raise ValueError(f'Rentang rekap maksimal {max_days} hari.')
    return start, until


def alpha_arg(value):
    try:
        alpha = float(value if value is not None else 0.3)
    except (ValueError, TypeError) as exc:
        raise ValueError('alpha harus berupa angka antara 0 dan 1 (inklusif).') from exc
    if alpha != alpha or alpha in (float('inf'), float('-inf')) or not 0 < alpha <= 1:
        raise ValueError('alpha harus berupa angka antara 0 dan 1 (inklusif).')
    return alpha
