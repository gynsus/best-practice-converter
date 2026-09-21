# -*- coding: utf-8 -*-
"""Формирование файла Результата (ТЗ 3.2, 4.2.6).

Контракт CSV: 21 колонка, разделитель ';', UTF-8 с BOM, перевод строки '\n'.
Решения от 17.09.2026: габариты в СМ; пустые числовые — пусто (не 0);
«Состояние» по умолчанию «Стандарт»; НДС пусто; объём в м³, при отсутствии
вычисляется из габаритов (ТЗ 3.2.12).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .dicts import QUALITY_ALLOWED, QUALITY_STANDARD
from .numbers import fmt_number

COLUMNS = [
    "№", "Код", "Артикул", "Название", "Наименование", "Группа номенклатуры",
    "Ширина", "Высота", "Глубина", "Вес", "Гарантия", "НДС", "Производитель",
    "Количество", "Значение цены", "Валюта цены", "Единица измерения",
    "Состояние", "Объём", "Поставщик", "Ошибка",
]
HEADER = ";".join(COLUMNS)
GROUP_SEP = " -> "


def join_group(*parts: str) -> str:
    """Сцепка уровней группы номенклатуры через « -> » (ТЗ 3.2.6)."""
    return GROUP_SEP.join(p for p in (s.strip() for s in parts) if p)


@dataclass
class ResultRow:
    code: str = ""
    article: str = ""
    title: str = ""            # «Название» — служебное, обычно пусто
    name: str = ""
    group: str = ""
    width_cm: float | None = None
    height_cm: float | None = None
    depth_cm: float | None = None
    weight_kg: float | None = None
    volume_m3: float | None = None
    warranty: str = ""
    vat: str = ""              # пусто = нет данных (решение 17.09)
    manufacturer: str = ""
    quantity: str = ""         # прямое копирование (ТЗ 3.2.17)
    price: str = ""            # число в формате CSV либо текст поставщика
    currency: str = ""         # RUB/USD/EUR, не может быть пустой (ТЗ 3.2.15)
    unit: str = ""
    quality: str = ""          # пусто -> «Стандарт»
    error: str = ""
    _errors: list = field(default_factory=list, repr=False)

    def add_error(self, text: str) -> None:
        if text:
            self._errors.append(text)


class ResultWriter:
    """Накапливает строки, применяет общие правила и пишет CSV целиком.

    Файл создаётся только при close() — при ошибке воркера частичный
    результат на диск не попадает (правило «целиком либо никак»).
    """

    def __init__(self, out_path: Path, supplier: str, start_number: int,
                 extra_allowed: set[str] | None = None):
        self.out_path = Path(out_path)
        self.supplier = supplier
        self.next_number = start_number
        # extra_allowed — значения качества сверх базового списка, заданные
        # спецификацией конкретного прайса (категории некондиции ABSOLUT/Resurs)
        self.allowed = QUALITY_ALLOWED | (extra_allowed or set())
        self.rows_with_errors = 0  # строки с непустой колонкой «Ошибка»
        self._lines: list[str] = [HEADER]

    @property
    def rows_written(self) -> int:
        return len(self._lines) - 1

    @property
    def last_number(self) -> int:
        return self.next_number - 1

    def add(self, r: ResultRow) -> None:
        quality = r.quality or QUALITY_STANDARD
        if quality not in self.allowed:
            r.add_error(f"недопустимое качество: {quality}")
            quality = QUALITY_STANDARD
        if not r.currency:
            r.add_error("валюта не определена")

        volume = r.volume_m3
        if volume is None and None not in (r.width_cm, r.height_cm, r.depth_cm):
            if r.width_cm > 0 and r.height_cm > 0 and r.depth_cm > 0:
                # габариты в см -> объём в м³ (ТЗ 3.2.12: вычислять при отсутствии)
                volume = r.width_cm * r.height_cm * r.depth_cm / 1_000_000

        error = "; ".join(dict.fromkeys(filter(None, [r.error, *r._errors])))
        if error:
            self.rows_with_errors += 1
        fields = [
            str(self.next_number), r.code, r.article, r.title, r.name, r.group,
            fmt_number(r.width_cm), fmt_number(r.height_cm), fmt_number(r.depth_cm),
            fmt_number(r.weight_kg), r.warranty, r.vat, r.manufacturer,
            r.quantity, r.price, r.currency, r.unit, quality,
            fmt_number(volume), self.supplier, error,
        ]
        self._lines.append(";".join(fields))
        self.next_number += 1

    def close(self) -> None:
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        # utf-8-sig = UTF-8 с BOM (решение 17.09), перевод строки '\n'
        with open(self.out_path, "w", encoding="utf-8-sig", newline="\n") as f:
            f.write("\n".join(self._lines) + "\n")
