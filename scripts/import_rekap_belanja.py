import argparse

from app import create_app
from app.services.impor_belanja_service import import_workbook


def main():
    parser = argparse.ArgumentParser(description='Import rekap dan detail nota belanja ke ledger belanja.')
    parser.add_argument('workbook', help='Path ke file XLSX rekap belanja.')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        result = import_workbook(args.workbook)
    if result['imported']:
        state = 'diimpor'
    else:
        state = 'sudah pernah diimpor; tidak ada baris baru'
    print(f"Workbook {state}.")
    print(f"Baris ringkasan: {result['summary_rows']}")
    print(f"Baris detail: {result['detail_rows']}")
    print(f"Baris detail yang ditandai kemungkinan duplikat: {result['possible_duplicate_details']}")
    print(f"Jumlah nilai ringkasan (baris agregat tidak dideduplikasi): Rp {result['summary_total']:,.2f}")
    print(f"Jumlah detail belanja (baris mentah termasuk kemungkinan duplikat): Rp {result['detail_total']:,.2f}")


if __name__ == '__main__':
    main()
