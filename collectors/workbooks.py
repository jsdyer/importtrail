"""Read ISED's single-sheet exports, including the inline rich text in its 2024 binary workbooks."""
from pathlib import Path
from struct import unpack_from
from zipfile import ZipFile
import csv


def unsigned(stream, limit):
    value = 0
    for shift in range(0, 7 * limit, 7):
        byte = stream.read(1)
        if not byte and shift == 0:
            return None
        if not byte:
            break
        value |= (byte[0] & 127) << shift
        if byte[0] < 128:
            return value
    raise ValueError("Invalid XLSB record header")


def binary_rows(stream):
    """Decode the cell types in the publisher's 2024 BrtBeginSheetData block."""
    in_data = False
    row = None
    while (record := unsigned(stream, 2)) is not None:
        size = unsigned(stream, 4)
        if size is None or size > 16_000_000:
            raise ValueError("Invalid XLSB record length")
        raw = stream.read(size)
        if len(raw) != size:
            raise ValueError("Truncated XLSB record")
        if record == 0x91:
            in_data = True
            continue
        if not in_data:
            continue
        if record in (0, 0x92):  # BrtRowHdr / BrtEndSheetData
            if row is not None:
                yield row
            if record == 0x92:
                return
            row = []
            continue
        if row is None:
            raise ValueError("Missing workbook row")
        column = unpack_from('<I', raw)[0]
        if column > 100 or column < len(row):
            raise ValueError("Unexpected workbook column")
        if record in (0x3e, 6):  # BrtCellRString / BrtCellSt
            offset = 9 if record == 0x3e else 8
            length = unpack_from('<I', raw, offset)[0] * 2
            start = offset + 4
            if len(raw) < start + length:
                raise ValueError("Truncated workbook text")
            value = raw[start:start + length].decode('utf-16le')
        elif record == 5:  # BrtCellReal
            value = unpack_from('<d', raw, 8)[0]
        elif record == 1:  # BrtCellBlank
            value = ''
        else:
            raise ValueError(f"Unrecognized XLSB cell record {record}")
        row.extend([''] * (column - len(row)))
        row.append(value)
    raise ValueError("Missing end of XLSB sheet")


def rows(path):
    path = Path(path)
    if path.suffix.lower() == '.csv':
        with path.open(encoding='utf-8-sig', newline='') as source:
            yield from csv.reader(source)
        return
    with ZipFile(path) as archive:
        if 'xl/worksheets/sheet1.bin' in archive.namelist():
            with archive.open('xl/worksheets/sheet1.bin') as sheet:
                yield from binary_rows(sheet)
            return
    from openpyxl import load_workbook
    with path.open('rb') as stream:
        book = load_workbook(stream, read_only=True, data_only=True)
        try:
            yield from book.worksheets[0].values
        finally:
            book.close()
