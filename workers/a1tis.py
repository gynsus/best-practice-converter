# -*- coding: utf-8 -*-
"""Воркер A1TIS — «A1TIS.xlsx», три листа: Стандарт, Уценка, Распродажа.

Спека ТЗ V2 «A1TIS»: Артикул <- «Артикул (код товара)»; Наименование <-
«Наименование»; Группа <- СЦЕПИТЬ(«Группа»; «Подгруппа»); Производитель <-
«Вендор»; Количество <- ВЫБОР(«В наличии»; «Транзит до 10 дн»; «Транзит до
20 дн»; «Транзит более 20 дн») — на листах Уценка/Распродажа транзитных
колонок нет; Цена <- «Цена»; Валюта <- «Валюта» (словарь: RUR -> RUB).
Состояние — по листу (в спеке не задано, листы говорят сами за себя):
Стандарт / Уценка / Распродажа.
"""
from __future__ import annotations

from pathlib import Path

from common.clean import clean
from common.dicts import map_currency
from common.numbers import fmt_number, number_or_text, parse_number
from common.reader import Sheet, cell
from common.result import ResultRow, ResultWriter, join_group

from ._base import Ctx, WorkerResult, result_of, run_cli

SUPPLIER = "A1TIS"
HEADER_ROW, FIRST_DATA_ROW = 6, 7
DEFAULT_CURRENCY = "RUB"
QTY_COLUMNS = ["В наличии", "Транзит до 10 дн", "Транзит до 20 дн", "Транзит более 20 дн"]
SHEETS = [("Стандарт", "Стандарт"), ("Уценка", "Уценка"), ("Распродажа", "Распродажа")]


def _one_sheet(src_path: Path, writer: ResultWriter, sheet_name: str, quality: str) -> None:
    sh = Sheet(src_path, sheet_name, HEADER_ROW)
    c_article = sh.col("Артикул (код товара)")
    c_name = sh.col("Наименование")
    c_manu = sh.col("Вендор")
    c_g1, c_g2 = sh.col("Группа"), sh.col("Подгруппа")
    c_price, c_cur = sh.col("Цена"), sh.col("Валюта")
    qty_cols = []
    for n in QTY_COLUMNS:
        try:
            qty_cols.append(sh.col(n))
        except Exception:
            pass  # на листах Уценка/Распродажа транзитных колонок нет
    if not qty_cols:
        raise RuntimeError(f"{src_path.name}, лист «{sheet_name}»: нет колонок количества")

    for _rn, row in sh.data_rows(FIRST_DATA_ROW):
        name = clean(cell(row, c_name))
        if not name:
            continue
        r = ResultRow()
        r.article = clean(cell(row, c_article))
        r.name = name
        r.manufacturer = clean(cell(row, c_manu))
        r.group = join_group(clean(cell(row, c_g1)), clean(cell(row, c_g2)))
        # =ВЫБОР(ЧИСЛО(...)) — первое ЧИСЛОВОЕ значение: «В наличии» бывает
        # текстом «Заказ» (нет на складе) — тогда берётся транзитная колонка.
        # Если чисел нет нигде — текст копируется как есть (ТЗ 3.2.17),
        # чтобы не потерять сведения о наличии молча.
        text_qty = ""
        for qc in qty_cols:
            q = parse_number(cell(row, qc))
            if q is not None:
                r.quantity = fmt_number(q)
                break
            if not text_qty:
                text_qty = clean(cell(row, qc))
        else:
            r.quantity = text_qty
        r.price = number_or_text(cell(row, c_price), clean)
        cur = map_currency(cell(row, c_cur))
        if cur is None:
            raw = clean(cell(row, c_cur))
            if raw:
                r.add_error(f"неизвестная валюта: {raw}")
            cur = DEFAULT_CURRENCY
        r.currency = cur
        r.quality = quality
        writer.add(r)


def process(src_path: Path, out_path: Path, start_number: int, ctx: Ctx | None = None) -> WorkerResult:
    src_path = Path(src_path)
    writer = ResultWriter(Path(out_path), SUPPLIER, start_number)
    for sheet_name, quality in SHEETS:
        _one_sheet(src_path, writer, sheet_name, quality)
    writer.close()
    return result_of(writer)


if __name__ == "__main__":
    run_cli(process)
