# -*- coding: utf-8 -*-
"""Воркер Marvel — «Marvel.xlsx», лист «Каталог_Марвел» (спека ТЗ V2 «Marvel»).

Особенность: файл поставщика приходит с битым styles.xml (Excel открывает,
стандартные библиотеки — нет) — читаем через починку стилей (repair=True).

Группа <- СЦЕПИТЬ(«Категория 1..4»); Производитель <- «Вендор»; Количество <-
ЧИСЛО(«Склад»); Цена <- «Цена»; Валюта <- «Валюта» (RUR -> RUB); Объём <-
«Объем м3»; Состояние <- «Упаковка» по справочнику некондиции Marvel
(ТЗ табл. 3: OK/вскрытая/мятая/с теста/из ремонта/некомплект).
"""
from __future__ import annotations

from pathlib import Path

from common.clean import clean
from common.dicts import MARVEL_NEKOND, map_currency, map_nekond
from common.numbers import number_or_text, parse_number
from common.reader import Sheet, cell
from common.result import ResultRow, ResultWriter, join_group

from ._base import Ctx, WorkerResult, result_of, run_cli

SHEET, HEADER_ROW, FIRST_DATA_ROW = "Каталог_Марвел", 1, 2
SUPPLIER = "Marvel"
DEFAULT_CURRENCY = "RUB"


def process(src_path: Path, out_path: Path, start_number: int, ctx: Ctx | None = None) -> WorkerResult:
    sh = Sheet(Path(src_path), SHEET, HEADER_ROW, repair=True)
    c_article = sh.col("Артикул")
    c_name = sh.col("Наименование")
    c_manu = sh.col("Вендор")
    c_groups = [sh.col(f"Категория {i}") for i in (1, 2, 3, 4)]
    c_pack = sh.col("Упаковка")
    c_price = sh.col("Цена")
    c_cur = sh.col("Валюта")
    c_qty = sh.col("Склад")
    c_vol = sh.col("Объем м3", "Объём м3")

    writer = ResultWriter(Path(out_path), SUPPLIER, start_number)
    for _rn, row in sh.data_rows(FIRST_DATA_ROW):
        name = clean(cell(row, c_name))
        if not name:
            continue
        r = ResultRow()
        r.article = clean(cell(row, c_article))
        r.name = name
        r.manufacturer = clean(cell(row, c_manu))
        r.group = join_group(*(clean(cell(row, c)) for c in c_groups))
        r.quality, err = map_nekond(clean(cell(row, c_pack)), MARVEL_NEKOND)
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
        r.volume_m3 = parse_number(cell(row, c_vol))
        writer.add(r)

    writer.close()
    return result_of(writer)


if __name__ == "__main__":
    run_cli(process)
