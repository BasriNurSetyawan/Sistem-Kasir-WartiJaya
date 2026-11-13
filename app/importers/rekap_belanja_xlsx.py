from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
from pathlib import Path
import posixpath
import re
from zipfile import ZipFile
from xml.etree import ElementTree as ET

NS = {
    'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    'rel': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}
DATE_PATTERN = re.compile(r'\b\d{2}-\d{2}-\d{4}\b')


def _string_table(archive):
    if 'xl/sharedStrings.xml' not in archive.namelist():
        return []
    root = ET.fromstring(archive.read('xl/sharedStrings.xml'))
    return [
        ''.join(text.text or '' for text in item.findall('.//main:t', NS))
        for item in root.findall('main:si', NS)
    ]


def _sheet_rows(archive, sheet_name, strings):
    workbook = ET.fromstring(archive.read('xl/workbook.xml'))
    relationships = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
    targets = {item.attrib['Id']: item.attrib['Target'] for item in relationships}
    for sheet in workbook.findall('main:sheets/main:sheet', NS):
        if sheet.attrib['name'] != sheet_name:
            continue
        target = targets[sheet.attrib[f"{{{NS['rel']}}}id"]]
        path = posixpath.normpath(target.lstrip('/') if target.startswith('/') else f'xl/{target}')
        root = ET.fromstring(archive.read(path))
        rows = []
        for row in root.findall('main:sheetData/main:row', NS):
            cells = {}
            for cell in row.findall('main:c', NS):
                column = ''.join(char for char in cell.attrib['r'] if char.isalpha())
                cell_type = cell.attrib.get('t')
                value_node = cell.find('main:v', NS)
                if cell_type == 'inlineStr':
                    value = ''.join(part.text or '' for part in cell.findall('.//main:t', NS))
                elif value_node is None:
                    value = ''
                elif cell_type == 's':
                    value = strings[int(value_node.text)]
                else:
                    value = value_node.text
                if cell.find('main:f', NS) is not None and value == '':
                    raise ValueError(f'Formula tanpa hasil tersimpan pada {sheet_name}!{cell.attrib["r"]}.')
                cells[column] = value
            rows.append((int(row.attrib['r']), cells))
        return rows
    raise ValueError(f'Sheet {sheet_name!r} tidak ditemukan.')


def _amount(value, location):
    try:
        amount = Decimal(str(value)).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f'Nilai uang tidak valid pada {location}: {value!r}.') from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError(f'Nilai uang harus finite dan tidak negatif pada {location}.')
    return amount


def _dates_and_scope(raw):
    matches = DATE_PATTERN.findall(raw)
    if not matches:
        raise ValueError(f'Tidak dapat membaca tanggal dari {raw!r}.')
    dates = [datetime.strptime(value, '%d-%m-%Y').date() for value in matches]
    note_match = re.search(r'\((.*?)\)', raw)
    note = note_match.group(1).strip() if note_match else ''
    lowered = note.lower()
    if len(dates) > 1:
        if '/' not in raw:
            raise ValueError(f'Rentang tanggal tidak dikenali: {raw!r}.')
        return dates[0], dates[1], 'rentang', note
    if any(term in lowered for term in ('rekap', 'mingguan', 'bulanan', 'oktober', 'total')):
        return dates[0], None, 'rekap_agregat', note
    return dates[0], dates[0], 'harian', note


def read_workbook(path):
    path = Path(path).resolve()
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    with ZipFile(path) as archive:
        strings = _string_table(archive)
        summary_rows = _sheet_rows(archive, 'Ringkasan', strings)
        detail_rows = _sheet_rows(archive, 'Detail Belanja', strings)

    if not summary_rows or [summary_rows[0][1].get(col) for col in 'ABCD'] != [
        'No', 'Nama Outlet / Keterangan', 'Tanggal', 'Total (Rp)'
    ]:
        raise ValueError('Header sheet Ringkasan tidak sesuai format yang dikenali.')
    if not detail_rows or [detail_rows[0][1].get(col) for col in 'ABCDE'] != [
        'Outlet', 'Tanggal', 'Nama Barang', 'Jumlah / Satuan', 'Harga / Total (Rp)'
    ]:
        raise ValueError('Header sheet Detail Belanja tidak sesuai format yang dikenali.')

    digest = source_hash
    source_file = path.name
    summaries = []
    for row_number, row in summary_rows[1:]:
        if not any(row.values()):
            continue
        start, end, scope, note = _dates_and_scope(str(row.get('C', '')))
        summaries.append({
            'outlet': str(row.get('B', '')).strip(),
            'tanggal_acuan': start,
            'tanggal_selesai': end,
            'cakupan': scope,
            'keterangan_tanggal': str(row.get('C', '')).strip(),
            'total': _amount(row.get('D'), f'Ringkasan!D{row_number}'),
            'source_file': source_file,
            'source_sha256': digest,
            'source_sheet': 'Ringkasan',
            'source_row': row_number,
        })

    parsed_details = []
    for row_number, row in detail_rows[1:]:
        if not any(row.values()):
            continue
        try:
            day = datetime.strptime(str(row.get('B', '')), '%Y-%m-%d').date()
        except ValueError as exc:
            raise ValueError(f'Tanggal tidak valid pada Detail Belanja!B{row_number}.') from exc
        parsed_details.append({
            'outlet': str(row.get('A', '')).strip(),
            'tanggal': day,
            'nama_barang': str(row.get('C', '')).strip(),
            'jumlah_asli': str(row.get('D', '')).strip(),
            'harga_total': _amount(row.get('E'), f'Detail Belanja!E{row_number}'),
            'source_file': source_file,
            'source_sha256': digest,
            'source_sheet': 'Detail Belanja',
            'source_row': row_number,
        })

    duplicate_counts = Counter(
        (row['outlet'], row['tanggal'], row['nama_barang'], row['jumlah_asli'], row['harga_total'])
        for row in parsed_details
    )
    seen = Counter()
    for row in parsed_details:
        key = (row['outlet'], row['tanggal'], row['nama_barang'], row['jumlah_asli'], row['harga_total'])
        seen[key] += 1
        row['kemungkinan_duplikat'] = seen[key] > 1 and duplicate_counts[key] > 1

    return summaries, parsed_details
