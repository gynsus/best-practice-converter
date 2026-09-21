# -*- coding: utf-8 -*-
"""Воркер VVP — «VVP_Group.xlsx», лист «Лист_1» (спека ТЗ V2 «VVP»).

Наименование <- «Номенклатура»; Группа <- СЦЕПИТЬ(«Категория»;
«Подкатегория») — в спеке названы «Подраздел 1/2», в файле — «Подкатегория»;
Количество = СУММАПОЛЕЙ(«Ожидается» .. «Уценка 50% Чашниково ЦД») — сумма
всех складских/уценочных колонок между «Предоплата, Цена с НДС» и «Описание»;
Цена <- «Предоплата, Цена с НДС»; RUB. Гарантия <- «Гарантия» (в спеке поле
пусто, но колонка в файле есть и содержит реальные условия — копируем).
"""
from __future__ import annotations

from pathlib import Path

from common.clean import clean
from common.numbers import fmt_number, number_or_text, parse_number
from common.reader import Sheet, cell
from common.result import ResultRow, ResultWriter, join_group

from ._base import Ctx, WorkerResult, result_of, run_cli

SHEET, HEADER_ROW, FIRST_DATA_ROW = "Лист_1", 1, 2
SUPPLIER = "VVP"
QTY_FIRST, QTY_LAST_PREFIX = "Ожидается", "Уценка 50%"


def process(src_path: Path, out_path: Path, start_number: int, ctx: Ctx | None = None) -> WorkerResult:
    sh = Sheet(Path(src_path), SHEET, HEADER_ROW)
    c_name = sh.col("Номенклатура")
    c_ean = sh.col("EAN")
    c_article = sh.col("Артикул")
    c_g1 = sh.col("Категория")
    c_g2 = sh.col("Подкатегория", "Подраздел 1")
    c_manu = sh.col("Бренд")
    c_price = sh.col("Предоплата, Цена с НДС")
    c_war = sh.col("Гарантия")
    c_descr = sh.col("Описание")

    # СУММАПОЛЕЙ: все колонки от «Ожидается» до «Описания» (не включая его)
    c_qty_first = sh.col(QTY_FIRST)
    qty_cols = list(range(c_qty_first, c_descr))
    if not qty_cols:
        raise RuntimeError(f"{Path(src_path).name}: не найден диапазон складских колонок")

    writer = ResultWriter(Path(out_path), SUPPLIER, start_number)
    for _rn, row in sh.data_rows(FIRST_DATA_ROW):
        name = clean(cell(row, c_name))
        if not name:
            continue
        r = ResultRow()
        r.code = clean(cell(row, c_ean))
        r.article = clean(cell(row, c_article))
        r.name = name
        r.manufacturer = clean(cell(row, c_manu))
        r.group = join_group(clean(cell(row, c_g1)), clean(cell(row, c_g2)))
        total = 0.0
        for qc in qty_cols:
            total += parse_number(cell(row, qc)) or 0
        r.quantity = fmt_number(total)
        r.price = number_or_text(cell(row, c_price), clean)
        r.currency = "RUB"
        r.warranty = clean(cell(row, c_war))
        writer.add(r)

    writer.close()
    return result_of(writer)


if __name__ == "__main__":
    run_cli(process)
