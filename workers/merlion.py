# -*- coding: utf-8 -*-
"""Воркер Merlion — «Merlion_2.xlsm», лист «Price List» (спека ТЗ V2 «Merlion»).

Заголовок в строке 11. Строки-«шапки» групп (без номера/наименования)
пропускаются — группы 1..3 присутствуют в каждой товарной строке.
Код <- «Номер»; Артикул <- «Код производителя»; Цена <- ЧИСЛО(«Цена(руб)»)
с валютой RUB (по спеке V2 — рублёвая колонка, а не долларовая);
Количество <- «Доступно» (градации «+/++/+++» копируются как есть);
Объём <- «Объем»; Вес <- «Вес»; Гарантия <- «Гарантия».
"""
from __future__ import annotations

from pathlib import Path

from common.clean import clean
from common.numbers import number_or_text, parse_number
from common.reader import Sheet, cell
from common.result import ResultRow, ResultWriter, join_group

from ._base import Ctx, WorkerResult, result_of, run_cli

SHEET, HEADER_ROW, FIRST_DATA_ROW = "Price List", 11, 12
SUPPLIER = "Merlion"


def process(src_path: Path, out_path: Path, start_number: int, ctx: Ctx | None = None) -> WorkerResult:
    sh = Sheet(Path(src_path), SHEET, HEADER_ROW)
    c_code = sh.col("Номер")
    c_article = sh.col("Код производителя")
    c_name = sh.col("Наименование")
    c_manu = sh.col("Бренд")
    c_g1, c_g2, c_g3 = sh.col("Группа 1"), sh.col("Группа 2"), sh.col("Группа 3")
    c_price = sh.col("Цена(руб)")
    c_qty = sh.col("Доступно")
    c_vol = sh.col("Объем", "Объём")
    c_wt = sh.col("Вес")
    c_war = sh.col("Гарантия")

    writer = ResultWriter(Path(out_path), SUPPLIER, start_number)
    for _rn, row in sh.data_rows(FIRST_DATA_ROW):
        name = clean(cell(row, c_name))
        if not name or not clean(cell(row, c_code)):
            continue  # строка-шапка группы
        r = ResultRow()
        r.code = clean(cell(row, c_code))
        r.article = clean(cell(row, c_article))
        r.name = name
        r.manufacturer = clean(cell(row, c_manu))
        r.group = join_group(clean(cell(row, c_g1)), clean(cell(row, c_g2)), clean(cell(row, c_g3)))
        r.price = number_or_text(cell(row, c_price), clean)
        r.currency = "RUB"
        r.quantity = clean(cell(row, c_qty))
        r.warranty = clean(cell(row, c_war))
        r.volume_m3 = parse_number(cell(row, c_vol))
        r.weight_kg = parse_number(cell(row, c_wt))
        writer.add(r)

    writer.close()
    return result_of(writer)


if __name__ == "__main__":
    run_cli(process)
