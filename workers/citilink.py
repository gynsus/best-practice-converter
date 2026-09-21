# -*- coding: utf-8 -*-
"""Воркер Citilink — «CitilinkPrice.xlsx», лист «Лист1» (спека ТЗ V2 «Citilink»).

Код <- «Номер»; Артикул <- «Код производителя»; Группа <- СЦЕПИТЬ(«Группа»;
«Подгруппа»); Цена <- «Цена Опт» (RUB); Количество <- «Склад» (звёздочки/«Нет»
копируются как есть); Вес <- «Вес» (кг); Объём <- «Объем» (м³ — в исходнике
встречается экспоненциальная запись, парсер обязан её понимать).
"""
from __future__ import annotations

from pathlib import Path

from common.clean import clean
from common.numbers import number_or_text, parse_number
from common.reader import Sheet, cell
from common.result import ResultRow, ResultWriter, join_group

from ._base import Ctx, WorkerResult, result_of, run_cli

SHEET, HEADER_ROW, FIRST_DATA_ROW = "Лист1", 6, 7
SUPPLIER = "Citilink"


def process(src_path: Path, out_path: Path, start_number: int, ctx: Ctx | None = None) -> WorkerResult:
    sh = Sheet(Path(src_path), SHEET, HEADER_ROW)
    c_code = sh.col("Номер")
    c_article = sh.col("Код производителя")
    c_name = sh.col("Наименование")
    c_manu = sh.col("Бренд")
    c_g1, c_g2 = sh.col("Группа"), sh.col("Подгруппа")
    c_price = sh.col("Цена Опт")
    c_qty = sh.col("Склад")
    c_vol = sh.col("Объем", "Объём")
    c_wt = sh.col("Вес")
    c_war = sh.col("Гарантия")

    writer = ResultWriter(Path(out_path), SUPPLIER, start_number)
    for _rn, row in sh.data_rows(FIRST_DATA_ROW):
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
        r.quantity = clean(cell(row, c_qty))
        r.warranty = clean(cell(row, c_war))
        r.volume_m3 = parse_number(cell(row, c_vol))
        r.weight_kg = parse_number(cell(row, c_wt))
        writer.add(r)

    writer.close()
    return result_of(writer)


if __name__ == "__main__":
    run_cli(process)
