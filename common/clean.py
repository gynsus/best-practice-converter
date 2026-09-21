# -*- coding: utf-8 -*-
"""Очистка текстовых строк по ТЗ п. 4.2.1.

Обязательные операции в заданном ТЗ порядке:
1) ';' -> ','   (разделитель результирующего CSV);
2) '"' -> ''    (двойная кавычка -> два апострофа);
3) непечатаемые символы -> пробел;
4) несколько пробелов подряд -> один пробел;
5) строка не должна начинаться/заканчиваться непечатаемым символом (trim).
"""
from __future__ import annotations

import re

# Управляющие символы, DEL, неразрывные/нулевые пробелы
_BAD = re.compile(r"[\x00-\x1f\x7f  ​ ﻿]")
_MULTISPACE = re.compile(r" {2,}")


def cell_text(value) -> str:
    """Значение ячейки -> строка без артефактов float (83549.0 -> '83549')."""
    if value is None:
        return ""
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return repr(value)
    return str(value)


def clean(value) -> str:
    """Очистка текстового значения по ТЗ 4.2.1 (порядок операций обязателен)."""
    s = cell_text(value)
    if not s:
        return ""
    s = s.replace(";", ",")
    s = s.replace('"', "''")
    s = _BAD.sub(" ", s)
    s = _MULTISPACE.sub(" ", s)
    return s.strip()
