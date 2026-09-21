# -*- coding: utf-8 -*-
"""Воркер Resurs Media (структурный прайс) — «Resurs Media_price_struct*.xlsx»,
лист «Price» (спека ТЗ V2 «Resurs Media (новое)»).

Заголовок в строке 2. Группы «вычисляемые по структуре»: строка-группа не
содержит «Номенклатуры», уровень = номер заполненной колонки (1 или 2).
Артикул <- «Артикул производителя»; Наименование <- «Номенклатура»;
Количество <- «Факт Москва» (копирование: «Мало»/«Много» как есть);
Цена <- ЧИСЛО(«Цена.руб»); RUB; Объём <- «Обьем,м3»; Вес <- «Вес,кг».
"""
from __future__ import annotations

from pathlib import Path

from common.clean import clean
from common.numbers import number_or_text, parse_number
from common.reader import Sheet, cell
from common.result import GROUP_SEP, ResultRow, ResultWriter

from ._base import Ctx, WorkerResult, result_of, run_cli

SHEET, HEADER_ROW, FIRST_DATA_ROW = "Price", 2, 3
SUPPLIER = "ResursMedia"


def process(src_path: Path, out_path: Path, start_number: int, ctx: Ctx | None = None) -> WorkerResult:
    sh = Sheet(Path(src_path), SHEET, HEADER_ROW)
    c_article = sh.col("Артикул производителя")
    c_name = sh.col("Номенклатура")
    c_manu = sh.col("Производитель")
    c_qty = sh.col("Факт Москва")
    c_price = sh.col("Цена.руб", "Цена, руб.")
    c_vol = sh.col("Обьем,м3", "Объем,м3")
    c_wt = sh.col("Вес,кг")

    writer = ResultWriter(Path(out_path), SUPPLIER, start_number)
    levels: dict[int, str] = {}
    for _rn, row in sh.data_rows(FIRST_DATA_ROW):
        # Строка-группа: заполнена РОВНО одна ячейка (группы 3-го уровня пишутся
        # в колонке «Номенклатура» — «Блоки лазера», «Печки» и т.п.);
        # её колонка задаёт уровень вложенности.
        filled = [(idx, clean(cell(row, idx))) for idx in range(len(row))]
        filled = [(i, t) for i, t in filled if t]
        if not filled:
            continue
        if len(filled) == 1:
            level = filled[0][0] + 1
            levels[level] = filled[0][1]
            for k in [k for k in levels if k > level]:
                del levels[k]
            continue
        name = clean(cell(row, c_name))
        if not name:
            continue
        r = ResultRow()
        r.article = clean(cell(row, c_article))
        r.name = name
        r.manufacturer = clean(cell(row, c_manu))
        r.group = GROUP_SEP.join(levels[k] for k in sorted(levels))
        r.quantity = number_or_text(cell(row, c_qty), clean)
        r.price = number_or_text(cell(row, c_price), clean)
        r.currency = "RUB"
        r.volume_m3 = parse_number(cell(row, c_vol))
        r.weight_kg = parse_number(cell(row, c_wt))
        writer.add(r)

    writer.close()
    return result_of(writer)


if __name__ == "__main__":
    run_cli(process)
