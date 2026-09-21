# -*- coding: utf-8 -*-
"""Воркер iDistribute — «iDistribute.xls» (legacy XLS), лист «Лист_1»
(спека ТЗ V2 «iDistribute»).

Заголовок в строке 5 (двухуровневый: «Скидка от прайса поставщика 28%» в
строке 4, «руб.» в строке 5). Группы — иерархия по outline-уровням строк
(строка-группа: пустая «Номенклатура»). Количество <- ЧИСЛО(«В наличии»);
Цена <- колонка «руб.»; RUB.
"""
from __future__ import annotations

from pathlib import Path

from common.clean import clean
from common.numbers import fmt_number, number_or_text, parse_number
from common.reader import Sheet, cell
from common.result import GROUP_SEP, ResultRow, ResultWriter

from ._base import Ctx, WorkerResult, result_of, run_cli

SHEET, HEADER_ROW, FIRST_DATA_ROW = "Лист_1", 5, 6
SUPPLIER = "iDistribute"


def process(src_path: Path, out_path: Path, start_number: int, ctx: Ctx | None = None) -> WorkerResult:
    sh = Sheet(Path(src_path), SHEET, HEADER_ROW)
    c_article = sh.col("Артикул")
    c_name = sh.col("Номенклатура")
    c_unit = sh.col("Ед. изм.")
    c_manu = sh.col("Номенклатура.Производитель")
    c_qty = sh.col("В наличии")
    c_price = sh.col("руб.")

    writer = ResultWriter(Path(out_path), SUPPLIER, start_number)
    levels: dict[int, str] = {}
    for rn, row in sh.data_rows(FIRST_DATA_ROW):
        name = clean(cell(row, c_name))
        first = clean(cell(row, c_article))
        if not name:
            if first:  # строка-группа, уровень по outline
                level = sh.outline.get(rn, 0)
                levels[level] = first
                for k in [k for k in levels if k > level]:
                    del levels[k]
            continue
        r = ResultRow()
        r.article = first
        r.name = name
        r.group = GROUP_SEP.join(levels[k] for k in sorted(levels))
        r.unit = clean(cell(row, c_unit))
        r.manufacturer = clean(cell(row, c_manu))
        qty = parse_number(cell(row, c_qty))
        r.quantity = fmt_number(qty)
        r.price = number_or_text(cell(row, c_price), clean)
        r.currency = "RUB"
        writer.add(r)

    writer.close()
    return result_of(writer)


if __name__ == "__main__":
    run_cli(process)
