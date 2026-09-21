# -*- coding: utf-8 -*-
"""Воркер Treolan — прайсы «Treolan.xlsx», «Treolan_NC.xlsx», «Treolan_DEMO.xlsx»
(один воркер на три варианта файла), лист «Каталог».

Маппинг — по листам «Treolan (новое)/(неконд)/(демо)» ТЗ V2:
Артикул <- «Артикул»; Наименование <- «Наименование»; Производитель <-
«Производитель»; Количество <- «Склад»; Гарантия <- «Гар.»; Вес <- «Вес [кг]»;
Объём <- «Объем [м3]»; Глубина <- «Длина [см]»; Ширина <- «Ширина [см]»;
Высота <- «Высота [см]»; Ед.изм. <- «Ед. изм.»;
Цена/Валюта <- =ВЫБОР(«Цена*» -> USD; «Цена руб.**» -> RUB);
Группа номенклатуры — вычисляемая по структуре: строка с пустым «Наименованием»
задаёт текущую группу (текст в колонке «Артикул»);
Состояние — константа по имени файла: *_nc -> «Некондиция», *_demo -> «Демо»,
иначе «Стандарт».
"""
from __future__ import annotations

from pathlib import Path

from common.clean import clean
from common.numbers import number_or_text, parse_number
from common.reader import Sheet, cell
from common.result import ResultRow, ResultWriter

from ._base import Ctx, WorkerResult, result_of, run_cli

SHEET = "Каталог"
HEADER_ROW = 3
FIRST_DATA_ROW = 4
SUPPLIER = "Treolan"
DEFAULT_CURRENCY = "USD"


def quality_for_file(src_path: Path) -> str:
    """Качество — по имени файла; поддерживаются оба стиля именования:
    Treolan_NC/_DEMO и кириллические Treolan_Некондиция/_Демо/_Регуляр."""
    stem = src_path.stem.casefold()
    if stem.endswith("_nc") or "некондиц" in stem:
        return "Некондиция"
    if stem.endswith("_demo") or "демо" in stem:
        return "Демо"
    return "Стандарт"


def process(src_path: Path, out_path: Path, start_number: int, ctx: Ctx | None = None) -> WorkerResult:
    src_path = Path(src_path)
    sh = Sheet(src_path, SHEET, HEADER_ROW)
    quality = quality_for_file(src_path)

    c_article = sh.col("Артикул")
    c_name = sh.col("Наименование")
    c_manu = sh.col("Производитель")
    c_qty = sh.col("Склад")
    c_usd = sh.col("Цена*")
    c_rub = sh.col("Цена руб.**")
    c_war = sh.col("Гар.")
    c_wt = sh.col("Вес [кг]")
    c_vol = sh.col("Объем [м3]", "Объём [м3]")
    c_depth = sh.col("Длина [см]")
    c_width = sh.col("Ширина [см]")
    c_height = sh.col("Высота [см]")
    c_unit = sh.col("Ед. изм.")

    writer = ResultWriter(Path(out_path), SUPPLIER, start_number)
    warnings: list[str] = []
    group = ""
    stopped_at = None
    for _rn, row in sh.data_rows(FIRST_DATA_ROW):
        first = clean(cell(row, c_article))
        if not first:
            stopped_at = _rn
            break  # конец данных (правило исторического конвертера)
        name = clean(cell(row, c_name))
        if not name:
            group = first  # строка-группа: текст в первой колонке
            continue

        r = ResultRow()
        r.article = first
        r.name = name
        r.group = group
        r.manufacturer = clean(cell(row, c_manu))
        r.quantity = clean(cell(row, c_qty))
        r.warranty = clean(cell(row, c_war))
        r.unit = clean(cell(row, c_unit))
        r.quality = quality

        usd = cell(row, c_usd)
        rub = cell(row, c_rub)
        if clean(usd):
            r.price = number_or_text(usd, clean)
            r.currency = "USD"
        elif clean(rub):
            r.price = number_or_text(rub, clean)
            r.currency = "RUB"
        else:
            r.currency = DEFAULT_CURRENCY  # цена пустая — допускается ТЗ 3.2.16

        r.weight_kg = parse_number(cell(row, c_wt))
        r.volume_m3 = parse_number(cell(row, c_vol))
        r.depth_cm = parse_number(cell(row, c_depth))
        r.width_cm = parse_number(cell(row, c_width))
        r.height_cm = parse_number(cell(row, c_height))
        writer.add(r)

    # После обрыва идёт подвал-легенда (сноски «*», «Условные обозначения»…);
    # товарной строку считаем по заполненной «Ед. изм.» — в легенде её нет.
    if stopped_at is not None:
        tail = sum(1 for _rn2, row2 in sh.data_rows(stopped_at + 1)
                   if clean(cell(row2, c_name)) and clean(cell(row2, c_unit)))
        if tail:
            warnings.append(f"после пустой строки {stopped_at} осталось {tail} товарных строк — проверить файл")

    writer.close()
    return result_of(writer, warnings)


if __name__ == "__main__":
    run_cli(process)
