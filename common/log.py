# -*- coding: utf-8 -*-
"""Логирование: консоль (INFO) + файл прогона в Рабочем подкаталоге архива (DEBUG).

В файл попадает всё, включая полные traceback ошибок воркеров (log.debug);
консоль планировщика остаётся краткой.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup(log_file: Path | None = None) -> logging.Logger:
    logger = logging.getLogger("pyconverter")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    sh.setLevel(logging.INFO)
    logger.addHandler(sh)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        fh.setLevel(logging.DEBUG)
        logger.addHandler(fh)
    return logger
