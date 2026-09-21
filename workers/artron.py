# -*- coding: utf-8 -*-
"""Воркер ARTRON — «Artron.xlsx», лист «Прайс Артрон» (спека ТЗ V2 «Artron»).

Структура: заголовок в строке 11, дальше иерархия по outline-уровням строк:
уровень 0 — группа номенклатуры («Офисные принтеры и МФУ»), уровень 1 —
производитель («Canon»), уровень 2 — товар. Наименование <- «Характеристики»;
Количество = СУММ(«Склад в наличии, шт.»; «Склад в резерве, шт.»);
Цена <- «Опт, руб.» (допускается текст «По запросу»); RUB.
"""
from __future__ import annotations

from pathlib import Path

from common.clean import clean
from common.numbers import fmt_number, number_or_text, parse_number
from common.reader import Sheet, cell
from common.result import ResultRow, ResultWriter

from ._base import Ctx, WorkerResult, result_of, run_cli

SHEET, HEADER_ROW, FIRST_DATA_ROW = "Прайс Артрон", 11, 12
SUPPLIER = "ARTRON"


def process(src_path: Path, out_path: Path, start_number: int, ctx: Ctx | None = None) -> WorkerResult:
    sh = Sheet(Path(src_path), SHEET, HEADER_ROW, need_outline=True)
    c_article = sh.col("Артикул")
    c_name = sh.col("Характеристики")
    c_price = sh.col("Опт, руб.")
    c_stock = sh.col("Склад в наличии, шт.")
    c_reserve = sh.col("Склад в резерве, шт.")

    writer = ResultWriter(Path(out_path), SUPPLIER, start_number)
    group = ""
    manufacturer = ""
    for rn, row in sh.data_rows(FIRST_DATA_ROW):
        first = clean(cell(row, c_article))
        name = clean(cell(row, c_name))
        if not first and not name:
            continue
        if not name:  # строка-группа: уровень по outline
            level = sh.outline.get(rn, 0)
            if level == 0:
                group = first
                manufacturer = ""
            else:
                manufacturer = first
            continue
        r = ResultRow()
        r.article = first
        r.name = name
        r.group = group
        r.manufacturer = manufacturer
        r.price = number_or_text(cell(row, c_price), clean)
        r.currency = "RUB"
        qty = (parse_number(cell(row, c_stock)) or 0) + (parse_number(cell(row, c_reserve)) or 0)
        r.quantity = fmt_number(qty)
        writer.add(r)

    writer.close()
    return result_of(writer)


if __name__ == "__main__":
    run_cli(process)
