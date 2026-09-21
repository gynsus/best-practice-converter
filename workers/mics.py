# -*- coding: utf-8 -*-
"""Воркер MICS — «MICS.xlsx», лист «Worksheet» (спека ТЗ V2 «MICS»).

Заголовок в строке 2. Группы — «вычисляемые по структуре»: строка-группа не
содержит наименования, уровень определяется номером заполненной колонки
(колонка 1 -> уровень 1, колонка 2 -> уровень 2).
Код <- «ID SAP»; Артикул <- «Partnumber»; Производитель <- «Вендор»;
Количество <- «Наличие Микс-Москва»; Цена <- «Цена Микс-Москва»;
Валюта <- «Валюта»; Состояние <- «Вид оценки» (словарь MICS).
"""
from __future__ import annotations

from pathlib import Path

from common.clean import clean
from common.dicts import MICS_NEKOND, map_currency, map_nekond
from common.numbers import number_or_text
from common.reader import Sheet, cell
from common.result import GROUP_SEP, ResultRow, ResultWriter

from ._base import Ctx, WorkerResult, result_of, run_cli

SHEET, HEADER_ROW, FIRST_DATA_ROW = "Worksheet", 2, 3
SUPPLIER = "MICS"
DEFAULT_CURRENCY = "RUB"


def process(src_path: Path, out_path: Path, start_number: int, ctx: Ctx | None = None) -> WorkerResult:
    sh = Sheet(Path(src_path), SHEET, HEADER_ROW)
    c_code = sh.col("ID SAP")
    c_article = sh.col("Partnumber")
    c_name = sh.col("Наименование")
    c_manu = sh.col("Вендор")
    c_grade = sh.col("Вид оценки")
    c_price = sh.col("Цена Микс-Москва")
    c_cur = sh.col("Валюта")
    c_qty = sh.col("Наличие Микс-Москва")

    writer = ResultWriter(Path(out_path), SUPPLIER, start_number)
    levels: dict[int, str] = {}
    for _rn, row in sh.data_rows(FIRST_DATA_ROW):
        name = clean(cell(row, c_name))
        if not name:
            # строка-группа: уровень = номер первой заполненной колонки
            for idx in range(len(row)):
                text = clean(cell(row, idx))
                if text:
                    level = idx + 1
                    levels[level] = text
                    for k in [k for k in levels if k > level]:
                        del levels[k]
                    break
            continue
        r = ResultRow()
        r.code = clean(cell(row, c_code))
        r.article = clean(cell(row, c_article))
        r.name = name
        r.manufacturer = clean(cell(row, c_manu))
        r.group = GROUP_SEP.join(levels[k] for k in sorted(levels))
        r.quality, err = map_nekond(clean(cell(row, c_grade)), MICS_NEKOND)
        r.add_error(err)
        r.price = number_or_text(cell(row, c_price), clean)
        cur = map_currency(cell(row, c_cur))
        if cur is None:
            raw = clean(cell(row, c_cur))
            if raw:
                r.add_error(f"неизвестная валюта: {raw}")
            cur = DEFAULT_CURRENCY
        r.currency = cur
        r.quantity = number_or_text(cell(row, c_qty), clean)
        writer.add(r)

    writer.close()
    return result_of(writer)


if __name__ == "__main__":
    run_cli(process)
