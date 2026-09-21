# -*- coding: utf-8 -*-
"""Воркер 3LOGIC — «3logic_2.xlsx», лист «Прайс» (спека ТЗ V2 «3LOGIC»).

Примечания к спеке:
- цена берётся из колонки «Руб.» с валютой RUB (константа по ТЗ V2) —
  старый конвертер v112 выгружал долларовую колонку, расхождение согласовано
  спецификацией;
- к гарантии дописывается « мес» (в исходнике голое число, единица — в имени
  колонки «Гарантия, мес»);
- колонок габаритов в текущем формате прайса нет — поля пустые.
"""
from __future__ import annotations

from pathlib import Path

from common.clean import clean
from common.numbers import number_or_text, parse_number
from common.reader import Sheet, cell
from common.result import ResultRow, ResultWriter, join_group

from ._base import Ctx, WorkerResult, result_of, run_cli

SHEET, HEADER_ROW, FIRST_DATA_ROW = "Прайс", 3, 4
SUPPLIER = "3LOGIC"


def process(src_path: Path, out_path: Path, start_number: int, ctx: Ctx | None = None) -> WorkerResult:
    sh = Sheet(Path(src_path), SHEET, HEADER_ROW)
    c_code = sh.col("Артикул")
    c_article = sh.col("Partnumber")
    c_title = sh.col("Категория")
    c_name = sh.col("Наименование")
    c_manu = sh.col("Бренд")
    c_g1, c_g2, c_g3 = sh.col("Раздел"), sh.col("Подраздел 1"), sh.col("Подраздел 2")
    c_price = sh.col("Руб.")
    c_qty = sh.col("Наличие")
    c_war = sh.col("Гарантия, мес")
    c_vol = sh.col("Объем за шт.", "Объём за шт.")
    c_wt = sh.col("Брутто")

    writer = ResultWriter(Path(out_path), SUPPLIER, start_number)
    for _rn, row in sh.data_rows(FIRST_DATA_ROW):
        name = clean(cell(row, c_name))
        if not name:
            continue
        r = ResultRow()
        r.code = clean(cell(row, c_code))
        r.article = clean(cell(row, c_article))
        r.title = clean(cell(row, c_title))
        r.name = name
        r.manufacturer = clean(cell(row, c_manu))
        r.group = join_group(clean(cell(row, c_g1)), clean(cell(row, c_g2)), clean(cell(row, c_g3)))
        r.quantity = number_or_text(cell(row, c_qty), clean)
        r.price = number_or_text(cell(row, c_price), clean)
        r.currency = "RUB"
        war = clean(cell(row, c_war))
        r.warranty = f"{war} мес" if war else ""
        r.volume_m3 = parse_number(cell(row, c_vol))
        r.weight_kg = parse_number(cell(row, c_wt))
        writer.add(r)

    writer.close()
    return result_of(writer)


if __name__ == "__main__":
    run_cli(process)
