#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Отправка текущих файлов выходного каталога одним ZIP-архивом на почту.

    python send_output.py                  # все *.csv из output -> grigoryf@njsoft.dev
    python send_output.py --mask "*"       # всё содержимое output (и report.html и т.д.)
    python send_output.py --to адрес       # другой получатель
    python send_output.py --dry-run        # собрать архив и показать состав, не отправляя

Каталог output берётся из settings.yaml, SMTP — из email.yaml
(те же настройки, что у писем-отчётов).
"""
from __future__ import annotations

import argparse
import fnmatch
import io
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from common.notify import load_email_cfg, send_mail  # noqa: E402

DEFAULT_TO = "grigoryf@njsoft.dev"
SKIP = {"converter.lock"}
WARN_MB = 25  # типовой предел вложения у почтовых серверов


def collect(out_dir: Path, mask: str) -> list[Path]:
    return sorted(p for p in out_dir.iterdir()
                  if p.is_file() and p.name not in SKIP
                  and fnmatch.fnmatch(p.name.casefold(), mask.casefold()))


def build_zip(files: list[Path]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in files:
            z.write(p, p.name)
    return buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser(description="Отправить файлы output ZIP-архивом на почту")
    ap.add_argument("--to", default=DEFAULT_TO, help=f"получатель (по умолчанию {DEFAULT_TO})")
    ap.add_argument("--mask", default="*.csv", help="маска файлов output (по умолчанию *.csv)")
    ap.add_argument("--settings", type=Path, default=BASE_DIR / "settings.yaml")
    ap.add_argument("--dry-run", action="store_true", help="показать состав, не отправлять")
    a = ap.parse_args()

    with open(a.settings, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    out_dir = Path(cfg["dirs"]["output"])
    if not out_dir.is_dir():
        print(f"ОШИБКА: выходной каталог недоступен: {out_dir}", file=sys.stderr)
        return 2

    files = collect(out_dir, a.mask)
    if not files:
        print(f"В {out_dir} нет файлов по маске «{a.mask}» — отправлять нечего.")
        return 1

    total = sum(p.stat().st_size for p in files)
    for p in files:
        print(f"  {p.name:40} {p.stat().st_size / 1024:10.0f} КБ")
    data = build_zip(files)
    zip_name = f"output_{datetime.now():%Y-%m-%d_%H%M}.zip"
    zip_mb = len(data) / 1024 / 1024
    print(f"Итого файлов: {len(files)}, {total / 1024 / 1024:.1f} МБ; "
          f"архив {zip_name}: {zip_mb:.1f} МБ")
    if zip_mb > WARN_MB:
        print(f"ВНИМАНИЕ: архив больше {WARN_MB} МБ — почтовый сервер может отклонить письмо.")
    if a.dry_run:
        print("Режим --dry-run: письмо не отправлено.")
        return 0

    email_cfg = load_email_cfg(BASE_DIR)
    if email_cfg is None:
        print("ОШИБКА: email.yaml не настроен (см. INSTALL-WINDOWS.md).", file=sys.stderr)
        return 2
    email_cfg = dict(email_cfg, mail_to=[a.to])
    names = "\n".join(f"  - {p.name}" for p in files)
    send_mail(email_cfg,
              f"Конвертер прайс-листов: файлы output ({datetime.now():%d.%m.%Y %H:%M})",
              f"Во вложении архив выходного каталога {out_dir} "
              f"({len(files)} файлов, {total / 1024 / 1024:.1f} МБ до сжатия):\n{names}\n",
              attachments=[(zip_name, data, "application", "zip")])
    print(f"Отправлено: {a.to}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
