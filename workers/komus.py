# -*- coding: utf-8 -*-
"""Воркер Komus — «komus_2.xlsx», листы «Опт прайс-лист» (заголовок в строке 4)
и «Распродажа» (заголовок в строке 1) в один результат (спеки ТЗ V2 «Komus»,
«Komus (распродажа)»).

Код <- «Артикул»; Артикул <- «Код производителя»; Цена <- «8-я колонка ОПЛ»;
НДС <- «НДС»; Количество <- ЧИСЛО(«Наличие на складе»); Ед.изм. <- «Ед.изм»;
Состояние <- «Статус товара» (словарь: «Регулярный» -> Стандарт, «Поставки
прекращены» -> Распродажа); Вес <- «Вес, кг»; Объём <- «Объем, л» / 1000.
"""
from __future__ import annotations

from pathlib import Path

from common.clean import clean
from common.dicts import KOMUS_STATUS, QUALITY_STANDARD
from common.numbers import fmt_number, number_or_text, parse_number
from common.reader import Sheet, cell
from common.result import ResultRow, ResultWriter, join_group

from ._base import Ctx, WorkerResult, result_of, run_cli

SUPPLIER = "Komus"
SHEETS = [("Опт прайс-лист", 4), ("Распродажа", 1)]


def _one_sheet(src_path: Path, writer: ResultWriter, sheet_name: str, header_row: int) -> None:
    sh = Sheet(src_path, sheet_name, header_row)
    c_code = sh.col("Артикул")
    c_article = sh.col("Код производителя")
    c_name = sh.col("Наименование товара")
    c_manu = sh.col("Торговая марка")
    c_g1, c_g2 = sh.col("Товарная категория"), sh.col("Товарная группа")
    c_price = sh.col("8-я колонка ОПЛ")
    c_vat = sh.col("НДС")
    c_qty = sh.col("Наличие на складе")
    c_unit = sh.col("Ед.изм", "Ед.изм.")
    c_status = sh.col("Статус товара")
    c_wt = sh.col("Вес, кг")
    c_vol = sh.col("Объем, л", "Объём, л")

    for _rn, row in sh.data_rows(header_row + 1):
        name = clean(cell(row, c_name))
        if not name:
            continue
        r = ResultRow()
        r.code = clean(cell(row, c_code))
        r.article = clean(cell(row, c_article))
        r.name = name
        r.manufacturer = clean(cell(row, c_manu))
        r.group = join_group(clean(cell(row, c_g1)), clean(cell(row, c_g2)))
        r.price = number_or_text(cell(row, c_price), clean)
        r.currency = "RUB"
        vat = parse_number(cell(row, c_vat))
        r.vat = fmt_number(vat)
        r.quantity = number_or_text(cell(row, c_qty), clean)
        r.unit = clean(cell(row, c_unit))
        status = clean(cell(row, c_status))
        if status:
            r.quality = KOMUS_STATUS.get(status, QUALITY_STANDARD)
            if status not in KOMUS_STATUS:
                r.add_error(f"неизвестный статус товара: {status}")
        r.weight_kg = parse_number(cell(row, c_wt))
        vol_l = parse_number(cell(row, c_vol))
        r.volume_m3 = None if vol_l is None else vol_l / 1000
        writer.add(r)


def process(src_path: Path, out_path: Path, start_number: int, ctx: Ctx | None = None) -> WorkerResult:
    src_path = Path(src_path)
    writer = ResultWriter(Path(out_path), SUPPLIER, start_number)
    for sheet_name, header_row in SHEETS:
        _one_sheet(src_path, writer, sheet_name, header_row)
    writer.close()
    return result_of(writer)


if __name__ == "__main__":
    run_cli(process)
