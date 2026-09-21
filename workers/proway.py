# -*- coding: utf-8 -*-
"""Воркер ProWay — «ProWay.xlsx», листы «Stock&Price» и «SUPER SALE» в один
результат (спеки ТЗ V2 «ProWay (новое)/(неконд)»).

Stock&Price: заголовок в строке 5, подзаголовки складов в строке 6
(«МСК»/«СПБ» под «Свободно на складе»); Количество = ВЫБОР(ЧИСЛО(МСК);
ЧИСЛО(СПБ)); Цена <- «Цена, USD», валюта USD; Группа = «Группа\\Класс»
с заменой «\\» на « -> ».
SUPER SALE: заголовок в строке 3; Количество <- ЧИСЛО(«Кол-во общее»);
Цена <- «Цена», Валюта <- «Валюта»; Состояние = «Распродажа» (в спеке V2
не задано; лист — распродажа по определению, поведение прежнего конвертера
сохранено).
"""
from __future__ import annotations

from pathlib import Path

from common.clean import clean
from common.dicts import map_currency
from common.numbers import fmt_number, number_or_text, parse_number
from common.reader import Sheet, cell, norm_header
from common.result import GROUP_SEP, ResultRow, ResultWriter

from ._base import Ctx, WorkerResult, result_of, run_cli

SUPPLIER = "ProWay"


def _group(value: str) -> str:
    return GROUP_SEP.join(p.strip() for p in value.split("\\") if p.strip())


def _main_sheet(src_path: Path, writer: ResultWriter) -> None:
    sh = Sheet(src_path, "Stock&Price", 5)
    c_article = sh.col("PartNumber")
    c_name = sh.col("Название")
    c_manu = sh.col("Бренд")
    c_grp = sh.col("Группа\\Класс")
    c_price = sh.col("Цена, USD")
    # подзаголовки складов — в строке 6
    sub = {norm_header(v): i for i, v in enumerate(sh.rows[5]) if norm_header(v)}
    qty_cols = [sub[k] for k in ("мск", "спб") if k in sub]
    if not qty_cols:
        raise RuntimeError(f"{src_path.name}: не найдены подзаголовки складов МСК/СПБ (строка 6)")

    for _rn, row in sh.data_rows(7):
        name = clean(cell(row, c_name))
        if not name:
            continue
        r = ResultRow()
        r.article = clean(cell(row, c_article))
        r.name = name
        r.manufacturer = clean(cell(row, c_manu))
        r.group = _group(clean(cell(row, c_grp)))
        for qc in qty_cols:
            q = parse_number(cell(row, qc))
            if q is not None:
                r.quantity = fmt_number(q)
                break
        r.price = number_or_text(cell(row, c_price), clean)
        r.currency = "USD"
        writer.add(r)


def _sale_sheet(src_path: Path, writer: ResultWriter) -> None:
    sh = Sheet(src_path, "SUPER SALE", 3)
    c_article = sh.col("PartNumber")
    c_name = sh.col("Название")
    c_manu = sh.col("Бренд")
    c_grp = sh.col("Группа\\Класс")
    c_qty = sh.col("Кол-во общее")
    c_price = sh.col("Цена", "Цена, USD")
    c_cur = sh.col("Валюта")

    for _rn, row in sh.data_rows(4):
        name = clean(cell(row, c_name))
        if not name:
            continue
        r = ResultRow()
        r.article = clean(cell(row, c_article))
        r.name = name
        r.manufacturer = clean(cell(row, c_manu))
        r.group = _group(clean(cell(row, c_grp)))
        r.quantity = fmt_number(parse_number(cell(row, c_qty)))
        r.price = number_or_text(cell(row, c_price), clean)
        cur = map_currency(cell(row, c_cur))
        if cur is None:
            raw = clean(cell(row, c_cur))
            if raw:
                r.add_error(f"неизвестная валюта: {raw}")
            cur = "USD"
        r.currency = cur
        r.quality = "Распродажа"
        writer.add(r)


def process(src_path: Path, out_path: Path, start_number: int, ctx: Ctx | None = None) -> WorkerResult:
    src_path = Path(src_path)
    writer = ResultWriter(Path(out_path), SUPPLIER, start_number)
    _main_sheet(src_path, writer)
    _sale_sheet(src_path, writer)
    writer.close()
    return result_of(writer)


if __name__ == "__main__":
    run_cli(process)
