# -*- coding: utf-8 -*-
"""Числа: разбор входных значений и вывод в CSV (ТЗ п. 4.2.3).

Разбор принимает все встречавшиеся в прайсах форматы:
- запятая и точка как десятичный разделитель ('204,96' / '204.96');
- пробел / неразрывный пробел как разделитель тысяч ('385 000');
- смешанный формат '1 567.000' (Komus);
- экспоненциальная запись '5.5225e-05' (Citilink/OCS — в старом VBA-конвертере
  такие значения терялись);
- '1.234.567' (точки-тысячи).

Вывод: десятичная ЗАПЯТАЯ, никогда научная нотация, без хвостовых нулей.
Пустое значение (нет данных) выводится пустой строкой — решение от 17.09.2026.
"""
from __future__ import annotations

import math
import re
from decimal import Decimal

_SPACES = re.compile(r"[\s   ]+")
_ALLOWED = re.compile(r"^[+-]?[0-9.,]+(?:[eE][+-]?[0-9]+)?$")


def parse_number(value) -> float | None:
    """Разбор числа из ячейки. None — «нет данных / не число»."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else None
    s = _SPACES.sub("", str(value))
    if s in ("", "-", "+"):
        return None
    if not _ALLOWED.match(s):
        return None
    has_c, has_d = "," in s, "." in s
    if has_c and has_d:
        # Последний из разделителей — десятичный, остальные — тысячные
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif has_c:
        if s.count(",") == 1:
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")  # запятые-тысячи
    elif has_d and s.count(".") > 1:
        s = s.replace(".", "")      # точки-тысячи
    try:
        return float(s)
    except ValueError:
        return None


def fmt_number(x: float | None) -> str:
    """Число -> строка CSV: десятичная запятая, без экспоненты и хвостовых нулей.

    Два шага:
    1) %.15g ограничивает 15 значащими цифрами — как показывает Excel; это
       срезает мусор двоичного float и артефакты арифметики
       (40491.00000000001 -> 40491; 0.145*100 -> 14.5). Значения, которым
       нужно 16-17 значащих цифр, округляются до 15 — осознанно;
    2) Decimal разворачивает экспоненциальную форму в позиционную без
       дополнительных потерь (4.930325e-08 -> 0.00000004930325).

    Нечисловые float (inf/nan) считаются отсутствием данных.
    """
    if x is None:
        return ""
    x = float(x)
    if not math.isfinite(x):
        return ""
    cleaned = float(f"{x:.15g}")
    s = format(Decimal(repr(cleaned)), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if s in ("", "-0", "-"):
        s = "0"
    return s.replace(".", ",")


def number_or_text(value, cleaner) -> str:
    """Для полей типа «Значение цены»: число -> формат CSV, иначе очищенный текст
    («По запросу», «Уточняйте» и т.п. по ТЗ 3.2.16 допустимы)."""
    n = parse_number(value)
    if n is not None:
        return fmt_number(n)
    return cleaner(value)
