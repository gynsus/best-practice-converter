# -*- coding: utf-8 -*-
"""Воркер ABSOLUT TRADE — «ABSOLUT TRADE.xlsx», листы «Прайс-лист» и
«Некондиция» в один результат (спеки ТЗ V2 «ABSOLUT TRADE (новое)/(неконд)»).

Наименование = СЦЕПИТЬ(«Название и описание продукта»; «Дополнительная
информация»); габариты «..., м» -> см; объём/вес — инд. упаковки.
Состояние на листе «Некондиция» = ОТБОР(«Категории некондиции»; «LOT»):
по значению LOT («32-я категория») берётся описание с листа-справочника
«Категории некондиции» этого же файла.
"""
from __future__ import annotations

from pathlib import Path

from common.clean import clean
from common.numbers import number_or_text, parse_number
from common.reader import Sheet, SourceFormatError, cell
from common.result import ResultRow, ResultWriter, join_group

from ._base import Ctx, WorkerResult, result_of, run_cli

SUPPLIER = "ABSOLUT TRADE"
CURRENCY = "RUB"


def _m_to_cm(value) -> float | None:
    n = parse_number(value)
    return None if n is None else n * 100


def _load_lot_categories(src_path: Path) -> dict[str, str]:
    """Лист «Категории некондиции»: «32-я категория» -> описание."""
    sh = Sheet(src_path, "Категории некондиции", 1)
    out = {}
    for _rn, row in sh.data_rows(2):
        cat, descr = clean(cell(row, 0)), clean(cell(row, 1))
        if cat and descr:
            out[cat] = descr
    if not out:
        raise SourceFormatError(f"{src_path.name}: пуст справочник «Категории некондиции»")
    return out


def _one_sheet(src_path: Path, writer: ResultWriter, sheet_name: str, header_row: int,
               lot_map: dict[str, str] | None) -> None:
    sh = Sheet(src_path, sheet_name, header_row)
    c_code = sh.col("Код АБСОЛЮТ ТРЕЙД")
    c_article = sh.col("Part Number")
    c_name = sh.col("Название и описание продукта")
    c_info = sh.col("Дополнительная информация")
    c_manu = sh.col("Бренд")
    c_g1, c_g2 = sh.col("Категория"), sh.col("Подкатегория")
    c_price = sh.col("Цена")
    c_qty = sh.col("Склад Москва (шт.)")
    c_war = sh.col("Гарантия")
    c_len = sh.col("Длина, м")
    c_wid = sh.col("Ширина, м")
    c_hei = sh.col("Высота, м")
    c_vol = sh.col("Объем инд. упаковки, м3", "Объем инд.упаковки, м3")
    c_wt = sh.col("Вес инд. упаковки, кг", "Вес инд.упаковки, кг")
    c_lot = sh.col("LOT") if lot_map is not None else None

    for _rn, row in sh.data_rows(header_row + 1):
        name = clean(cell(row, c_name))
        if not name:
            continue  # строки-разделители категорий
        r = ResultRow()
        r.code = clean(cell(row, c_code))
        r.article = clean(cell(row, c_article))
        info = clean(cell(row, c_info))
        r.name = f"{name} {info}".strip()
        r.manufacturer = clean(cell(row, c_manu))
        r.group = join_group(clean(cell(row, c_g1)), clean(cell(row, c_g2)))
        r.price = number_or_text(cell(row, c_price), clean)
        r.currency = CURRENCY
        r.quantity = number_or_text(cell(row, c_qty), clean)
        r.warranty = clean(cell(row, c_war))
        r.depth_cm = _m_to_cm(cell(row, c_len))
        r.width_cm = _m_to_cm(cell(row, c_wid))
        r.height_cm = _m_to_cm(cell(row, c_hei))
        r.volume_m3 = parse_number(cell(row, c_vol))
        r.weight_kg = parse_number(cell(row, c_wt))
        if lot_map is not None:
            lot = clean(cell(row, c_lot))
            r.quality = lot_map.get(lot, "")
            if lot and not r.quality:
                r.add_error(f"LOT «{lot}» не найден в «Категориях некондиции»")
        writer.add(r)


def process(src_path: Path, out_path: Path, start_number: int, ctx: Ctx | None = None) -> WorkerResult:
    src_path = Path(src_path)
    lot_map = _load_lot_categories(src_path)
    writer = ResultWriter(Path(out_path), SUPPLIER, start_number,
                          extra_allowed=set(lot_map.values()))
    _one_sheet(src_path, writer, "Прайс-лист", 2, lot_map=None)
    _one_sheet(src_path, writer, "Некондиция", 3, lot_map=lot_map)
    writer.close()
    return result_of(writer)


if __name__ == "__main__":
    run_cli(process)
