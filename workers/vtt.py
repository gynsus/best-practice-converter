# -*- coding: utf-8 -*-
"""Воркер VTT — «vtt.main.price.rub.xls» / «vtt.main.price.usd.xls»
(legacy XLS), лист «Price» (спека ТЗ V2 «VTT»).

Заголовок в строке 5. Группы — иерархия по outline-уровням строк: строка без
артикула задаёт уровень группы («Вид товара»), товары — строки с артикулом.
Код <- «Артикул»; Артикул <- «Ориг. номер»; Наименование <- «Название»;
Производитель <- «Производитель»; Количество <- «Наличие»;
Цена <- «Опт.4, руб.». Валюта — по имени файла: *.usd.* -> USD, иначе RUB.
"""
from __future__ import annotations

from pathlib import Path

from common.clean import clean
from common.numbers import number_or_text
from common.reader import Sheet, cell
from common.result import GROUP_SEP, ResultRow, ResultWriter

from ._base import Ctx, WorkerResult, result_of, run_cli

SHEET, HEADER_ROW, FIRST_DATA_ROW = "Price", 5, 6
SUPPLIER = "VTT"


def process(src_path: Path, out_path: Path, start_number: int, ctx: Ctx | None = None) -> WorkerResult:
    src_path = Path(src_path)
    currency = "USD" if ".usd." in src_path.name.casefold() else "RUB"
    sh = Sheet(src_path, SHEET, HEADER_ROW)
    c_code = sh.col("Артикул")
    c_kind = sh.col("Вид товара")
    c_name = sh.col("Название")
    c_manu = sh.col("Производитель")
    c_orig = sh.col("Ориг. номер")
    try:
        c_catalog = sh.col("Каталожный номер")   # запасной источник артикула
    except Exception:
        c_catalog = None
    c_qty = sh.col("Наличие")
    c_price = sh.col("Опт.4, руб.", "Опт.4, USD", "Опт.4")

    writer = ResultWriter(Path(out_path), SUPPLIER, start_number)
    levels: dict[int, str] = {}
    for rn, row in sh.data_rows(FIRST_DATA_ROW):
        code = clean(cell(row, c_code))
        kind = clean(cell(row, c_kind))
        if not code:
            if kind:  # строка-группа
                level = sh.outline.get(rn, 0)
                levels[level] = kind
                for k in [k for k in levels if k > level]:
                    del levels[k]
            continue
        name = clean(cell(row, c_name))
        if not name:
            continue
        r = ResultRow()
        r.code = code
        # Артикул: «Ориг. номер» (спека V2); у большинства строк он пуст —
        # тогда «Каталожный номер», иначе код поставщика (артикул обязателен)
        catalog = clean(cell(row, c_catalog)) if c_catalog is not None else ""
        r.article = clean(cell(row, c_orig)) or catalog or code
        r.name = name
        r.manufacturer = clean(cell(row, c_manu))
        r.group = GROUP_SEP.join(levels[k] for k in sorted(levels))
        r.quantity = number_or_text(cell(row, c_qty), clean)
        r.price = number_or_text(cell(row, c_price), clean)
        r.currency = currency
        writer.add(r)

    writer.close()
    return result_of(writer)


if __name__ == "__main__":
    run_cli(process)
