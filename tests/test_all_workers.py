# -*- coding: utf-8 -*-
"""Регресс этапа 2: все воркеры на реальных исходниках (fixtures/).

Эталон числа строк — прогон конвертера v112 от 31.08.2026, с задокументированными
отличиями (Artron: +2 — v112 начинал чтение со строки 17 и терял первые товары).
"""
import csv
import re
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
FIXTURES = BASE / "fixtures"

# Фикстуры (реальные прайсы) не публикуются в открытый репозиторий —
# на машинах без них регресс-тесты пропускаются, unit-тесты работают.
pytestmark = pytest.mark.skipif(
    not (FIXTURES / "Getsy.xlsx").exists(),
    reason="нет локальных фикстур (162 МБ реальных прайсов, вне публичного репо)",
)

E_NOTATION = re.compile(r"^[0-9,+-]+[eE][+-]?[0-9]+$")
NUMERIC_COLS = (6, 7, 8, 9, 18)

CASES = [
    # (воркер, файл, строк, {проверки колонок: индекс -> множество допустимых или callable})
    ("logic3_2", "3Logic_2.xlsx", 7371),
    ("a1tis", "A1TIS.xlsx", 9654),
    ("absolut", "ABSOLUT TRADE.xlsx", 6153),
    ("artron", "Artron.xlsx", 2809),          # v112: 2807 — терял 2 первых товара
    ("citilink", "CitilinkPrice.xlsx", 43896),
    ("idistribute", "iDistribute.xls", 986),
    ("komus", "komus_2.xlsx", 47898),
    ("marvel", "Marvel.xlsx", 5167),
    ("merlion", "Merlion_2.xlsm", 34605),
    ("mics", "MICS.xlsx", 1132),
    ("netlab", "NetlabPrice.xml", 66205),
    ("ocs", "OCS.xlsx", 36829),
    ("proway", "ProWay.xlsx", 3908),
    ("resurs_nekond", "Resurs Media_price_nec.xlsx", 95),
    ("resurs_struct", "Resurs Media_price_struct (no problem).xlsx", 15802),
    ("vtt", "vtt.main.price.rub.xls", 9971),
    ("vvp", "VVP_Group.xlsx", 3513),
]


@pytest.mark.parametrize("worker,fname,expected_rows", CASES, ids=[c[0] for c in CASES])
def test_worker_contract_and_rows(worker, fname, expected_rows, tmp_path):
    import importlib
    mod = importlib.import_module(f"workers.{worker}")
    out = tmp_path / "out.csv"
    res = mod.process(FIXTURES / fname, out, 1)
    with open(out, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))
    header, data = rows[0], rows[1:]

    assert len(data) == expected_rows
    assert res.rows_written == expected_rows
    assert res.last_number == expected_rows
    assert len(header) == 21
    for r in data:
        assert len(r) == 21
        for i in NUMERIC_COLS:
            assert not E_NOTATION.match(r[i]), f"научная нотация: {r[i]}"
        assert r[17] != "", "Состояние не должно быть пустым"
        assert r[15] in ("RUB", "USD", "EUR"), f"валюта: {r[15]}"


def _read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f, delimiter=";"))[1:]


def test_a1tis_quality_by_sheets(tmp_path):
    from workers import a1tis
    out = tmp_path / "a.csv"
    a1tis.process(FIXTURES / "A1TIS.xlsx", out, 1)
    q = {}
    for r in _read(out):
        q[r[17]] = q.get(r[17], 0) + 1
    assert set(q) == {"Стандарт", "Уценка", "Распродажа"}
    assert q["Уценка"] == 19 and q["Распродажа"] == 36  # как в исходнике 31.08


def test_absolut_nekond_categories(tmp_path):
    from workers import absolut
    out = tmp_path / "a.csv"
    absolut.process(FIXTURES / "ABSOLUT TRADE.xlsx", out, 1)
    rows = _read(out)
    # гарантия из кол.14, а не в «Глубине» (исторический баг конвертера)
    warr = [r for r in rows if r[10]]
    assert len(warr) > 5000
    # категории некондиции подтянуты с листа-справочника
    long_quality = [r for r in rows if len(r[17]) > 20]
    assert long_quality, "нет строк с категориями некондиции"
    # габариты в см и согласованы с объёмом: Ш×В×Г ≈ Объём (для полной строки)
    for r in rows:
        if all(r[i] not in ("", "0") for i in (6, 7, 8, 18)):
            w, h, d = (float(r[i].replace(",", ".")) for i in (6, 7, 8))
            v = float(r[18].replace(",", "."))
            assert abs(w * h * d / 1e6 - v) / v < 0.02
            break


def test_citilink_exponent_values_preserved(tmp_path):
    """Кейс v112: объём/вес из экспоненциальной записи обнулялись."""
    from workers import citilink
    out = tmp_path / "c.csv"
    citilink.process(FIXTURES / "CitilinkPrice.xlsx", out, 1)
    rows = {r[1]: r for r in _read(out)}
    r = rows.get("1830444")
    if r is not None:  # артикул из фикстуры 31.08
        assert r[18] not in ("", "0"), "объём из e-notation потерян"
        assert r[9] not in ("", "0"), "вес из e-notation потерян"
    nonzero_vol = sum(1 for x in rows.values() if x[18] not in ("", "0"))
    assert nonzero_vol > 42000


def test_komus_vat_and_volume(tmp_path):
    from workers import komus
    out = tmp_path / "k.csv"
    komus.process(FIXTURES / "komus_2.xlsx", out, 1)
    rows = _read(out)
    vats = {r[11] for r in rows}
    assert vats <= {"22", "10", "0", ""}
    zero_vol = sum(1 for r in rows if r[18] == "0")
    assert zero_vol < len(rows) * 0.05, "объёмы Komus снова обнулились"


def test_vtt_groups_and_currency(tmp_path):
    from workers import vtt
    out = tmp_path / "v.csv"
    vtt.process(FIXTURES / "vtt.main.price.rub.xls", out, 1)
    rows = _read(out)
    assert all(r[15] == "RUB" for r in rows)
    with_group = sum(1 for r in rows if " -> " in r[5])
    assert with_group > len(rows) * 0.9, "иерархия групп из outline не собрана"


def test_netlab_title_from_brackets(tmp_path):
    from workers import netlab
    out = tmp_path / "n.csv"
    netlab.process(FIXTURES / "NetlabPrice.xml", out, 1)
    rows = _read(out)
    titled = sum(1 for r in rows if r[3])
    assert titled > len(rows) * 0.5, "«Название» из [скобок] RussianName не извлекается"
    assert all("[" not in r[3] for r in rows[:2000])


def test_marvel_repair_and_quality(tmp_path):
    from workers import marvel
    out = tmp_path / "m.csv"
    marvel.process(FIXTURES / "Marvel.xlsx", out, 1)   # файл с битым styles.xml
    rows = _read(out)
    q = {r[17] for r in rows}
    assert "Стандарт" in q
    assert q <= {"Стандарт", "Дефект упаковки", "Демо", "Из ремонта", "Некомплект"}
    assert all(r[15] == "RUB" or r[15] in ("USD", "EUR") for r in rows)


def test_proway_sale_marked(tmp_path):
    from workers import proway
    out = tmp_path / "p.csv"
    proway.process(FIXTURES / "ProWay.xlsx", out, 1)
    rows = _read(out)
    sale = [r for r in rows if r[17] == "Распродажа"]
    assert len(sale) > 1000
    assert all(r[14] != "" for r in sale), "у распродажи должна быть цена"
