# -*- coding: utf-8 -*-
"""Общий контракт воркеров.

Каждый воркер — модуль workers/<имя>.py с функцией:

    def process(src_path, out_path, start_number, ctx=None) -> WorkerResult

Любой воркер запускается автономно для отладки одного прайса:

    python -m workers.<имя> <файл-прайса> -o <результат.csv> [--start N]
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Ctx:
    """Параметры вызова от основного скрипта (пока минимум, расширяемо)."""
    pricelist_name: str = ""


@dataclass
class WorkerResult:
    rows_written: int
    last_number: int
    warnings: list[str] = field(default_factory=list)
    rows_with_errors: int = 0   # строки результата с непустой колонкой «Ошибка»


def result_of(writer, warnings: list[str] | None = None) -> WorkerResult:
    """Стандартный результат воркера из ResultWriter."""
    return WorkerResult(writer.rows_written, writer.last_number,
                        warnings or [], writer.rows_with_errors)


def run_cli(process_fn) -> None:
    parser = argparse.ArgumentParser(description="Автономный запуск воркера (отладка одного прайс-листа)")
    parser.add_argument("src", type=Path, help="файл прайс-листа")
    parser.add_argument("-o", "--out", type=Path, required=True, help="файл результата CSV")
    parser.add_argument("--start", type=int, default=1, help="стартовый порядковый номер (по умолчанию 1)")
    args = parser.parse_args()
    res = process_fn(args.src, args.out, args.start, Ctx())
    print(f"OK: строк {res.rows_written}, номера {args.start}..{res.last_number} -> {args.out}")
    for w in res.warnings:
        print(f"  предупреждение: {w}", file=sys.stderr)
