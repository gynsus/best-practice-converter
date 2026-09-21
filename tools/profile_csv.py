#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Профайлер результатов: сводка по заполнению колонок CSV-файлов каталога.

    python3 tools/profile_csv.py <каталог с CSV>

Используется для самопроверки после прогона: паттерны значений, процент
заполнения, аномалии (научная нотация, неверное число полей).
"""
from __future__ import annotations

import csv
import glob
import os
import re
import sys
from collections import Counter

COLS = ["Объём", "Единица измерения", "Валюта цены", "Значение цены", "Количество",
        "НДС", "Гарантия", "Вес", "Глубина", "Высота", "Ширина", "Состояние"]
_E_NOTATION = re.compile(r"^[0-9,+-]+[eE][+-]?[0-9]+$")


def pattern(v: str) -> str:
    return re.sub(r"\d+", "9", v)


def analyze(path: str):
    name = os.path.splitext(os.path.basename(path))[0]
    stats = {c: {"empty": 0, "values": Counter(), "patterns": Counter()} for c in COLS}
    total = bad_fields = e_notation = 0
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            total += 1
            if None in row.values() or row.get("Ошибка") is None:
                bad_fields += 1
            for c in COLS:
                v = (row.get(c) or "").strip()
                if not v:
                    stats[c]["empty"] += 1
                    continue
                if _E_NOTATION.match(v):
                    e_notation += 1
                st = stats[c]
                if len(st["values"]) <= 60:
                    st["values"][v] += 1
                st["patterns"][pattern(v)] += 1
    return name, total, stats, bad_fields, e_notation


def main() -> None:
    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    for path in sorted(glob.glob(os.path.join(folder, "*.csv"))):
        name, total, stats, bad, e_not = analyze(path)
        flags = []
        if bad:
            flags.append(f"СТРОК С НЕВЕРНЫМ ЧИСЛОМ ПОЛЕЙ: {bad}")
        if e_not:
            flags.append(f"НАУЧНАЯ НОТАЦИЯ: {e_not}")
        print(f"\n{'=' * 80}\n### {name}  (строк: {total}{'; ' + '; '.join(flags) if flags else ''})")
        for c in COLS:
            st = stats[c]
            filled = total - st["empty"]
            pct = 100 * filled / total if total else 0
            line = f"  {c}: заполнено {filled}/{total} ({pct:.0f}%)"
            if not filled:
                print(line + " — ВСЕГДА ПУСТО")
                continue
            if len(st["values"]) <= 15:
                vals = "; ".join(f"'{v}'×{n}" for v, n in st["values"].most_common(15))
                print(line + f" | уникальных: {len(st['values'])} → {vals}")
            else:
                pats = "; ".join(f"'{p}'×{n}" for p, n in st["patterns"].most_common(6))
                samples = "; ".join(f"'{v}'" for v, _ in st["values"].most_common(5))
                print(line + f" | паттерны: {pats} | примеры: {samples}")


if __name__ == "__main__":
    main()
