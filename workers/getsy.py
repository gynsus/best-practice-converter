# -*- coding: utf-8 -*-
"""Воркер Getsy — прайс «Getsy.xlsx», лист «Наличие и цены».

Маппинг — по листу «Getsy» ТЗ V2:
Код <- «Номенклатурный номер»; Артикул <- «Каталожный номер»;
Наименование <- «Наименование»; Группа <- сцепка «Группа/Категория/Вид
оборудования»; Ширина/Высота/Глубина <- «... (м)» (перевод в см);
Вес <- «Вес (кг)»; Объём <- «Объём (м3)»; Производитель <- «Производитель»;
Количество <- первое непустое из складских колонок (=ВЫБОР(...));
Цена <- «Цена»; Валюта <- «Валюта» (словарь, по умолчанию RUB);
Ед.изм. <- «Единица измерения»; Состояние <- «Некондиция/распродажа»
(справочник некондиции Getsy/OCS).
"""
from __future__ import annotations

from pathlib import Path

from common.clean import clean
from common.dicts import GETSY_OCS_NEKOND, map_currency, map_nekond
from common.numbers import number_or_text, parse_number
from common.reader import Sheet, cell
from common.result import ResultRow, ResultWriter, join_group

from ._base import Ctx, WorkerResult, result_of, run_cli

SHEET = "Наличие и цены"
HEADER_ROW = 1
FIRST_DATA_ROW = 2
SUPPLIER = "Getsy"
DEFAULT_CURRENCY = "RUB"

# =ВЫБОР(...) из ТЗ V2: первое непустое значение по порядку колонок
QTY_COLUMNS = [
    "Доступно для резерва", "Москва", "Санкт-Петербург",
    "Ближний транзит (до 7дн.)", "Распределительный центр",
    "Логистический хаб", "Склад вендора", "Дальний транзит", "Резервы",
]


def _m_to_cm(value) -> float | None:
    n = parse_number(value)
    return None if n is None else n * 100


def process(src_path: Path, out_path: Path, start_number: int, ctx: Ctx | None = None) -> WorkerResult:
    sh = Sheet(Path(src_path), SHEET, HEADER_ROW)
    warnings: list[str] = []

    c_code = sh.col("Номенклатурный номер")
    c_article = sh.col("Каталожный номер")
    c_name = sh.col("Наименование")
    c_manu = sh.col("Производитель")
    c_g1 = sh.col("Группа оборудования")
    c_g2 = sh.col("Категория оборудования")
    c_g3 = sh.col("Вид оборудования")
    c_price = sh.col("Цена")
    c_cur = sh.col("Валюта")
    c_nekond = sh.col("Некондиция/распродажа")
    c_unit = sh.col("Единица измерения")
    c_w = sh.col("Ширина (м)")
    c_h = sh.col("Высота (м)")
    c_d = sh.col("Глубина (м)")
    c_wt = sh.col("Вес (кг)")
    c_vol = sh.col("Объём (м3)", "Объем (м3)")
    qty_cols: list[int] = []
    for name in QTY_COLUMNS:
        try:
            qty_cols.append(sh.col(name))
        except Exception:
            warnings.append(f"нет складской колонки «{name}» — пропущена")
    if not qty_cols:
        raise RuntimeError(f"{Path(src_path).name}: не найдена ни одна складская колонка количества")

    writer = ResultWriter(Path(out_path), SUPPLIER, start_number)
    last_group = ""
    stopped_at = None
    for _rn, row in sh.data_rows(FIRST_DATA_ROW):
        name = clean(cell(row, c_name))
        if not name:
            stopped_at = _rn
            break  # конец данных (правило исторического конвертера)

        r = ResultRow()
        r.code = clean(cell(row, c_code))
        r.article = clean(cell(row, c_article))
        r.name = name
        r.manufacturer = clean(cell(row, c_manu))
        group = join_group(clean(cell(row, c_g1)), clean(cell(row, c_g2)), clean(cell(row, c_g3)))
        if group:
            last_group = group
        r.group = group or last_group  # редкие строки без групп наследуют предыдущую

        for qc in qty_cols:
            q = clean(cell(row, qc))
            if q:
                r.quantity = q
                break

        r.price = number_or_text(cell(row, c_price), clean)
        cur = map_currency(cell(row, c_cur))
        if cur is None:
            raw_cur = clean(cell(row, c_cur))
            if raw_cur:
                r.add_error(f"неизвестная валюта: {raw_cur}")
            cur = DEFAULT_CURRENCY
        r.currency = cur

        r.unit = clean(cell(row, c_unit))
        r.quality, nek_err = map_nekond(clean(cell(row, c_nekond)), GETSY_OCS_NEKOND)
        r.add_error(nek_err)

        r.width_cm = _m_to_cm(cell(row, c_w))
        r.height_cm = _m_to_cm(cell(row, c_h))
        r.depth_cm = _m_to_cm(cell(row, c_d))
        r.weight_kg = parse_number(cell(row, c_wt))
        r.volume_m3 = parse_number(cell(row, c_vol))
        writer.add(r)

    # защита от «дырки» в данных: после точки обрыва не должно быть товаров
    if stopped_at is not None:
        tail = sum(1 for _rn2, row2 in sh.data_rows(stopped_at + 1) if clean(cell(row2, c_name)))
        if tail:
            warnings.append(f"после пустой строки {stopped_at} осталось {tail} непустых наименований — проверить файл")

    writer.close()
    return result_of(writer, warnings)


if __name__ == "__main__":
    run_cli(process)
