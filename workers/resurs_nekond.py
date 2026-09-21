# -*- coding: utf-8 -*-
"""Воркер Resurs Media (некондиция) — «Resurs Media_price_nec.xlsx», лист
«price» (спека ТЗ V2 «Resurs Media (неконд)»).

Блочная структура: заголовок категорий в строке 3 (4 блока по 3 колонки:
«Легкое/Среднее/Тяжелое повреждение упаковки», «Просроченный срок годности»),
подзаголовки «Остаток / Цена, у.е. / Цена, руб.» в строке 4, данные с
строки 5. Каждый непустой блок строки даёт отдельную запись результата с
«Состоянием» = заголовок блока. «Нет» в остатке = блок пуст.
Группа <- «Тип продукции»; Артикул <- «Артикул производителя»; RUB.
"""
from __future__ import annotations

from pathlib import Path

from common.clean import clean
from common.numbers import number_or_text, parse_number, fmt_number
from common.reader import Sheet, SourceFormatError, cell, norm_header
from common.result import ResultRow, ResultWriter

from ._base import Ctx, WorkerResult, result_of, run_cli

SHEET, BLOCK_HEADER_ROW, SUB_HEADER_ROW, FIRST_DATA_ROW = "price", 3, 4, 5
SUPPLIER = "ResursMedia"


def process(src_path: Path, out_path: Path, start_number: int, ctx: Ctx | None = None) -> WorkerResult:
    src_path = Path(src_path)
    sh = Sheet(src_path, SHEET, BLOCK_HEADER_ROW)
    c_group = sh.col("Тип продукции")
    c_manu = sh.col("Производитель")
    c_article = sh.col("Артикул производителя")
    c_name = sh.col("Номенклатура")

    # Блоки категорий: колонка с подзаголовком «Остаток» (строка 4) открывает
    # блок из трёх колонок; имя категории — над ней в строке 3.
    header = sh.rows[BLOCK_HEADER_ROW - 1]
    sub = sh.rows[SUB_HEADER_ROW - 1]
    blocks: list[tuple[int, str]] = []  # (индекс колонки «Остаток», текст категории)
    for idx, v in enumerate(sub):
        if norm_header(v) != "остаток":
            continue
        category = clean(cell(header, idx))
        if not category:
            raise SourceFormatError(
                f"{src_path.name}: над «Остатком» (колонка {idx + 1}) нет имени категории (строка {BLOCK_HEADER_ROW})"
            )
        blocks.append((idx, category))
    if not blocks:
        raise SourceFormatError(f"{src_path.name}: не найдены блоки категорий некондиции")

    writer = ResultWriter(Path(out_path), SUPPLIER, start_number,
                          extra_allowed={b[1] for b in blocks})
    for _rn, row in sh.data_rows(FIRST_DATA_ROW):
        name = clean(cell(row, c_name))
        if not name:
            continue
        for qty_idx, category in blocks:
            qty_raw = clean(cell(row, qty_idx))
            price_raw = cell(row, qty_idx + 2)  # «Цена, руб.» — третья колонка блока
            price = number_or_text(price_raw, clean)
            if (not qty_raw or qty_raw.casefold() == "нет") and not price:
                continue
            r = ResultRow()
            r.article = clean(cell(row, c_article))
            r.name = name
            r.manufacturer = clean(cell(row, c_manu))
            r.group = clean(cell(row, c_group))
            qty = parse_number(qty_raw)
            r.quantity = fmt_number(qty) if qty is not None else ("" if qty_raw.casefold() == "нет" else qty_raw)
            r.price = price
            r.currency = "RUB"
            r.quality = category
            writer.add(r)

    writer.close()
    return result_of(writer)


if __name__ == "__main__":
    run_cli(process)
