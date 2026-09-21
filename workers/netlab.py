# -*- coding: utf-8 -*-
"""Воркер Netlab — «NetlabPrice.xml» (YML-подобный XML, спека ТЗ V2 «Netlab»).

Категории <category id parentId> собираются в полную цепочку « -> ».
Офферы читаются потоково (файл ~30 МБ).
Код <- offer.uid; Артикул <- offer.PN; Наименование <- offer.name;
Название <- содержимое квадратных скобок из offer.RussianName;
Количество <- ВЫБОР(offer.count; offer.remote) — «remote» может отсутствовать;
Цена <- offer.priceD; Валюта <- offer.currencyId (словарь);
габариты width/height/length — сантиметры; вес кг; объём м³.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from common.clean import clean
from common.dicts import map_currency
from common.numbers import number_or_text, parse_number
from common.reader import SourceFormatError
from common.result import GROUP_SEP, ResultRow, ResultWriter

from ._base import Ctx, WorkerResult, result_of, run_cli

SUPPLIER = "Netlab"
DEFAULT_CURRENCY = "USD"
_BRACKETS = re.compile(r"\[([^\]]*)\]")


def _text(el, tag: str) -> str:
    node = el.find(tag)
    return node.text if node is not None and node.text else ""


def process(src_path: Path, out_path: Path, start_number: int, ctx: Ctx | None = None) -> WorkerResult:
    src_path = Path(src_path)
    writer = ResultWriter(Path(out_path), SUPPLIER, start_number)

    # Проход 1: категории (их немного — собираем в память)
    cats: dict[str, tuple[str, str]] = {}  # id -> (parentId, name)
    for _ev, el in ET.iterparse(src_path, events=("end",)):
        if el.tag == "category":
            cid = el.attrib.get("id", "")
            cats[cid] = (el.attrib.get("parentId", ""), clean(el.text))
            el.clear()
        elif el.tag == "categories":
            el.clear()
            break
    if not cats:
        raise SourceFormatError(f"{src_path.name}: не найдены категории")

    full_path: dict[str, str] = {}
    for cid in cats:
        chain, cur, seen = [], cid, set()
        while cur in cats and cur not in seen:
            seen.add(cur)
            parent, name = cats[cur]
            chain.append(name)
            cur = parent
        full_path[cid] = GROUP_SEP.join(reversed(chain))

    # Проход 2: офферы, потоково
    for _ev, el in ET.iterparse(src_path, events=("end",)):
        if el.tag != "offer":
            continue
        name = clean(_text(el, "name"))
        if name:
            r = ResultRow()
            r.code = clean(_text(el, "uid"))
            r.article = clean(_text(el, "PN"))
            r.name = name
            m = _BRACKETS.search(_text(el, "RussianName"))
            r.title = clean(m.group(1)) if m else ""
            r.manufacturer = clean(_text(el, "Vendor"))
            r.group = full_path.get(_text(el, "categoryId").strip(), "")
            count = clean(_text(el, "count"))
            r.quantity = count if count else clean(_text(el, "remote"))
            r.price = number_or_text(_text(el, "priceD"), clean)
            cur = map_currency(_text(el, "currencyId"))
            if cur is None:
                raw = clean(_text(el, "currencyId"))
                if raw:
                    r.add_error(f"неизвестная валюта: {raw}")
                cur = DEFAULT_CURRENCY
            r.currency = cur
            r.warranty = clean(_text(el, "warranty"))
            r.width_cm = parse_number(_text(el, "width"))
            r.height_cm = parse_number(_text(el, "height"))
            r.depth_cm = parse_number(_text(el, "length"))
            r.volume_m3 = parse_number(_text(el, "volume"))
            r.weight_kg = parse_number(_text(el, "weight"))
            writer.add(r)
        el.clear()

    writer.close()
    return result_of(writer)


if __name__ == "__main__":
    run_cli(process)
