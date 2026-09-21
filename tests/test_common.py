# -*- coding: utf-8 -*-
"""Unit-тесты общей библиотеки: очистка, числа, словари, запись результата."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.clean import clean, cell_text
from common.dicts import GETSY_OCS_NEKOND, map_currency, map_nekond
from common.numbers import fmt_number, number_or_text, parse_number
from common.result import ResultRow, ResultWriter, join_group


# --- Очистка строк (ТЗ 4.2.1) ---

def test_clean_semicolon_and_quote():
    assert clean('AB;C "D"') == "AB,C ''D''"

def test_clean_control_chars_and_spaces():
    assert clean("Группа\nПодгруппа") == "Группа Подгруппа"        # перенос -> пробел
    assert clean("  много   пробелов\t ") == "много пробелов"
    assert clean(" текст ") == "текст"                    # nbsp

def test_cell_text_floats():
    assert cell_text(83549.0) == "83549"
    assert cell_text(3.5) == "3.5"
    assert cell_text(None) == ""


# --- Числа (ТЗ 4.2.3 + все исторические кейсы) ---

def test_parse_decimal_comma_and_dot():
    assert parse_number("204,96") == 204.96
    assert parse_number("204.96") == 204.96

def test_parse_thousands():
    assert parse_number("385 000") == 385000.0        # пробел-тысячи (Artron)
    assert parse_number("1 567.000") == 1567.0        # смешанный (Komus)
    assert parse_number("1.234.567") == 1234567.0     # точки-тысячи
    assert parse_number("1.234,56") == 1234.56

def test_parse_exponent():
    # Кейс Citilink/OCS: v112 терял такие значения (товар 1830444)
    assert parse_number("5.5225e-05") == 5.5225e-05
    assert parse_number(5.767446666666666e-05) == 5.767446666666666e-05

def test_parse_garbage():
    assert parse_number("По запросу") is None
    assert parse_number("") is None
    assert parse_number(None) is None
    assert parse_number("1-2") is None

def test_fmt_no_scientific_notation():
    assert fmt_number(5.5225e-05) == "0,000055225"
    assert fmt_number(6.39822857142857e-05) == "0,0000639822857142857"  # без потери точности
    assert "e" not in fmt_number(1e-10).lower()

def test_fmt_basics():
    assert fmt_number(None) == ""       # пусто = нет данных (решение 17.09)
    assert fmt_number(0.0) == "0"       # реальный ноль сохраняется
    assert fmt_number(1567.0) == "1567"
    assert fmt_number(204.96) == "204,96"

def test_fmt_float_artifacts():
    assert fmt_number(0.145 * 100) == "14,5"        # артефакт умножения м -> см
    assert fmt_number(8483.89) == "8483,89"         # артефакт двоичного float

def test_number_or_text():
    assert number_or_text("204,96", clean) == "204,96"
    assert number_or_text("По запросу", clean) == "По запросу"


# --- Словари ---

def test_currency_map():
    for raw in ("RUB", "RUR", "руб.", "Руб.", "₽", " rur "):
        assert map_currency(raw) == "RUB", raw
    assert map_currency("$") == "USD"
    assert map_currency("€") == "EUR"
    assert map_currency("XXX") is None
    assert map_currency("") is None

def test_nekond_map():
    assert map_nekond("", GETSY_OCS_NEKOND) == ("Стандарт", "")
    assert map_nekond("НК:УпакСредне", GETSY_OCS_NEKOND)[0] == "Дефект упаковки"
    assert map_nekond("НК:БУ", GETSY_OCS_NEKOND)[0] == "Демо"
    q, err = map_nekond("Что-то новое", GETSY_OCS_NEKOND)
    assert q == "Стандарт" and "Что-то новое" in err


# --- Результат ---

def test_group_join():
    assert join_group("А", "", "Б") == "А -> Б"

def test_writer_defaults_and_volume(tmp_path):
    out = tmp_path / "t.csv"
    w = ResultWriter(out, "Тест", start_number=10)
    r = ResultRow(article="A1", name="Товар", currency="RUB",
                  width_cm=10, height_cm=20, depth_cm=30)   # объём должен вычислиться
    w.add(r)
    r2 = ResultRow(article="A2", name="Товар2")             # нет валюты -> ошибка в строке
    w.add(r2)
    w.close()
    data = out.read_bytes()
    assert data.startswith("﻿".encode("utf-8"))        # BOM
    lines = data.decode("utf-8-sig").splitlines()
    assert lines[0].count(";") == 20                        # 21 колонка
    f1 = lines[1].split(";")
    assert f1[0] == "10"
    assert f1[17] == "Стандарт"                             # качество по умолчанию
    assert f1[18] == "0,006"                                # 10×20×30 см = 0.006 м³
    f2 = lines[2].split(";")
    assert f2[0] == "11"
    assert "валюта не определена" in f2[20]
    assert w.last_number == 11


def test_treolan_quality_by_filename_both_styles():
    """Качество Treolan по имени файла: латинские и кириллические варианты."""
    from pathlib import Path
    from workers.treolan import quality_for_file as q
    assert q(Path("Treolan_Регуляр.xlsx")) == "Стандарт"
    assert q(Path("Treolan.xlsx")) == "Стандарт"
    assert q(Path("Treolan_Демо.xlsx")) == "Демо"
    assert q(Path("Treolan_DEMO.xlsx")) == "Демо"
    assert q(Path("Treolan_Некондиция.xlsx")) == "Некондиция"
    assert q(Path("Treolan_NC.xlsx")) == "Некондиция"
