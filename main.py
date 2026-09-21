#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Основной скрипт Конвертера прайс-листов (ТЗ п. 4.1).

Пассивный запуск планировщиком (cron / Планировщик Windows):

    python3 main.py [--settings settings.yaml]

Алгоритм (ТЗ 4.1): рабочий подкаталог ГГГГ.ММ.ДД в архиве -> обнаружение
прайс-листов -> сличение имён с настройками (точное имя или маска) ->
для каждого: копия во временный файл, оригинал в архив, запуск воркера ->
сквозная нумерация «без зазоров» -> отчёт прогона -> done.txt.

Коды возврата: 0 — без ошибок; 1 — часть файлов с ошибкой; 2 — фатально.
"""
from __future__ import annotations

import argparse
import fnmatch
import importlib
import os
import shutil
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from common.log import setup as setup_log          # noqa: E402
from common.notify import load_email_cfg, send_mail, want_mail  # noqa: E402
from common import report_html                     # noqa: E402
from workers._base import Ctx                      # noqa: E402

DONE_FILE = "done.txt"
STATUS_FILE = "status.txt"       # сводка последнего прогона в выходном каталоге
REPORT_PAGE = "report.html"      # страница диагностики в выходном каталоге
# Служебные файлы конвейера — не прайс-листы, в сопоставлении не участвуют
SERVICE_FILES = {DONE_FILE, "converter.lock", "start.cmd", "_start.cmd"}


@dataclass
class Item:
    name: str
    masks: list
    worker: str
    result: str
    enabled: bool
    status: str = ""
    src_file: str = ""
    rows: int = 0
    rows_err: int = 0
    seconds: float = 0.0
    message: str = ""


def load_settings(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    for key in ("input", "output", "archive"):
        if not cfg.get("dirs", {}).get(key):
            raise ValueError(f"settings: не задан каталог dirs.{key}")
    if not cfg.get("pricelists"):
        raise ValueError("settings: пуст список pricelists")
    return cfg


def parse_items(cfg: dict) -> list[Item]:
    items = []
    for p in cfg["pricelists"]:
        raw = p["match"]
        masks = [str(m) for m in raw] if isinstance(raw, list) else [str(raw)]
        items.append(Item(
            name=str(p["name"]),
            masks=masks,
            worker=str(p["worker"]),
            result=str(p["result"]),
            enabled=bool(p.get("enabled", True)),
        ))
    return items


def match_any(name: str, masks: list) -> bool:
    """Имя файла подходит под любую из масок записи (регистр не учитывается)."""
    return any(fnmatch.fnmatch(name.casefold(), m.casefold()) for m in masks)


def mask_str(item: Item) -> str:
    return " | ".join(item.masks)


def archive_original(src: Path, archive_sub: Path) -> None:
    """Оригинал прайс-листа -> Рабочий подкаталог (ТЗ 4.1.4)."""
    target = archive_sub / src.name
    if target.exists():  # повторный прогон в тот же день
        stamp = datetime.now().strftime("%H%M%S")
        target = archive_sub / f"{src.stem}.{stamp}{src.suffix}"
    shutil.move(str(src), str(target))


def check(settings_path: Path) -> int:
    """Предварительная проверка без обработки: настройки, доступность каталогов
    (в т.ч. сетевых UNC), права на запись, сопоставление файлов входного
    каталога записям настроек. Ничего не перемещает и не конвертирует."""
    ok = True

    def good(msg): print(f"  [OK] {msg}")

    def bad(msg):
        nonlocal ok
        ok = False
        print(f"  [!!] {msg}")

    print(f"Настройки: {settings_path}")
    try:
        cfg = load_settings(settings_path)
        items = parse_items(cfg)
        good(f"настройки прочитаны, записей прайс-листов: {len(items)}")
    except Exception as e:
        bad(f"настройки не прочитаны: {e}")
        return 2

    dirs = {k: Path(v) for k, v in cfg["dirs"].items()}
    print("\nКаталоги:")
    for kind, p in dirs.items():
        try:
            if not p.is_dir():
                bad(f"{kind}: НЕДОСТУПЕН — {p}")
                continue
            n = sum(1 for x in p.iterdir() if x.is_file())
            good(f"{kind}: {p} (файлов: {n})")
            if kind in ("output", "archive"):
                probe = p / "_write_test.tmp"
                probe.write_text("test", encoding="utf-8")
                probe.unlink()
                good(f"{kind}: запись разрешена")
        except OSError as e:
            bad(f"{kind}: ошибка доступа — {e}")

    if not dirs["input"].is_dir():
        return 2 if not ok else 0

    print("\nСопоставление файлов входного каталога (dry-run):")
    files = sorted(p for p in dirs["input"].iterdir()
                   if p.is_file() and p.name.casefold() not in {s.casefold() for s in SERVICE_FILES})
    claimed: set[Path] = set()
    for item in items:
        matches = [p for p in files if p not in claimed and match_any(p.name, item.masks)]
        if not item.enabled:
            print(f"  [--] {item.name}: отключён")
            continue
        if matches:
            claimed.add(matches[0])
            good(f"{item.name}: «{matches[0].name}» -> {item.result} (воркер {item.worker})")
        else:
            print(f"  [??] {item.name}: файла по маске «{mask_str(item)}» сейчас нет")
        try:
            importlib.import_module(f"workers.{item.worker}")
        except Exception as e:
            bad(f"{item.name}: воркер «{item.worker}» не загружается: {e}")
    for p in files:
        if p not in claimed:
            print(f"  [??] файл «{p.name}» не подходит ни под одну маску")

    print("\nИтог:", "готово к запуску" if ok else "ЕСТЬ ПРОБЛЕМЫ (см. [!!])")
    return 0 if ok else 2


def write_status(output_dir: Path, text: str) -> None:
    """status.txt — состояние конвертера одним файлом в выходном каталоге.
    Ошибка записи (сеть) не должна ронять прогон."""
    try:
        (output_dir / STATUS_FILE).write_text(text, encoding="utf-8")
    except OSError:
        pass


def notify_fatal(message: str) -> None:
    """Письмо о фатальной ошибке (если настроен email.yaml). Не бросает исключений."""
    cfg = load_email_cfg(BASE_DIR)
    if cfg is None:
        return
    try:
        send_mail(cfg, "Конвертер прайс-листов: ФАТАЛЬНАЯ ОШИБКА",
                  f"Прогон {datetime.now():%d.%m.%Y %H:%M:%S} не выполнен.\n\n{message}")
    except Exception as e:                                   # noqa: BLE001
        print(f"письмо о фатальной ошибке не отправлено: {e}", file=sys.stderr)


def run(settings_path: Path) -> int:
    try:
        cfg = load_settings(settings_path)
    except Exception as e:
        print(f"ФАТАЛЬНО: настройки не прочитаны: {e}", file=sys.stderr)
        notify_fatal(f"Настройки не прочитаны: {e}")
        return 2

    dirs = cfg["dirs"]
    input_dir = Path(dirs["input"])
    output_dir = Path(dirs["output"])
    archive_dir = Path(dirs["archive"])
    # Каталоги могут быть сетевыми (UNC \\server\share) — недоступность сети
    # должна давать внятный фатал, а не traceback
    try:
        if not input_dir.is_dir():
            print(f"ФАТАЛЬНО: входной каталог недоступен: {input_dir}", file=sys.stderr)
            notify_fatal(f"Входной каталог недоступен: {input_dir}")
            return 2
        output_dir.mkdir(parents=True, exist_ok=True)
        # Рабочий подкаталог: имя фиксируется на старте и не меняется (ТЗ 4.1.1)
        archive_sub = archive_dir / datetime.now().strftime("%Y.%m.%d")
        archive_sub.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"ФАТАЛЬНО: каталог недоступен (сеть/права): {e}", file=sys.stderr)
        notify_fatal(f"Каталог недоступен (сеть/права): {e}")
        return 2

    log = setup_log(archive_sub / f"run_{datetime.now():%H%M%S}.log")
    log.info("Старт. Вход: %s | Выход: %s | Архив: %s", input_dir, output_dir, archive_sub)

    # Защита от параллельного запуска (наложение прогонов планировщика)
    lock = output_dir / "converter.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
    except FileExistsError:
        age_h = (time.time() - lock.stat().st_mtime) / 3600 if lock.exists() else 0
        if age_h < 6:
            log.error("Обнаружен %s (возраст %.1f ч) — другой прогон ещё работает, выходим", lock.name, age_h)
            return 3
        log.warning("Устаревший %s (%.1f ч) — перехватываем", lock.name, age_h)
        lock.write_text(str(os.getpid()), encoding="utf-8")

    started = datetime.now()
    write_status(output_dir,
                 f"RUNNING: старт {started:%d.%m.%Y %H:%M:%S}, PID {os.getpid()}\n"
                 f"Если прогон давно должен был завершиться, а эта строка осталась — "
                 f"он оборвался аварийно; см. run_*.log в {archive_sub}\n")
    try:
        return _run_locked(cfg, input_dir, output_dir, archive_dir, archive_sub,
                           lock, log, started)
    except Exception as e:  # непредвиденное падение вне обработки одного файла
        log.error("ФАТАЛЬНО: непредвиденная ошибка прогона: %s", e)
        log.debug("%s", traceback.format_exc())
        write_status(output_dir,
                     f"FATAL: прогон {started:%d.%m.%Y %H:%M:%S} оборван ошибкой: {e}\n"
                     f"Подробности: run_*.log в {archive_sub}\n")
        notify_fatal(f"Прогон оборван непредвиденной ошибкой.\n\n{traceback.format_exc()}")
        lock.unlink(missing_ok=True)
        return 2


def _run_locked(cfg: dict, input_dir: Path, output_dir: Path, archive_dir: Path,
                archive_sub: Path, lock: Path, log, started: datetime) -> int:
    items = parse_items(cfg)
    service = {s.casefold() for s in SERVICE_FILES} | {lock.name.casefold()}
    available = sorted(p for p in input_dir.iterdir()
                       if p.is_file() and p.name.casefold() not in service)
    claimed: set[Path] = set()
    produced: set[str] = set()
    number = 1
    had_error = False
    done_count = 0

    # Отчёт пишется ИНКРЕМЕНТАЛЬНО — строка за строкой по ходу прогона:
    # при аварийном обрыве отчёт остаётся заполненным до места падения
    report = archive_sub / f"run_report_{datetime.now():%H%M%S}.csv"
    rep_f = open(report, "w", encoding="utf-8-sig", newline="\n")
    rep_f.write("Прайс-лист;Маска;Файл;Статус;Строк;Строк с ошибками;Время, сек;Сообщение\n")
    rep_f.flush()

    def rep_row(it: Item) -> None:
        rep_f.write(f"{it.name};{mask_str(it)};{it.src_file};{it.status};{it.rows};"
                    f"{it.rows_err};{it.seconds:.1f};{it.message}\n")
        rep_f.flush()

    for item in items:
        if not item.enabled:
            item.status = "SKIP"
            item.message = "отключён в настройках"
            log.info("[%s] SKIP (отключён)", item.name)
            rep_row(item)
            continue

        matches = [p for p in available if p not in claimed and match_any(p.name, item.masks)]
        if not matches:
            item.status = "NO_FILE"
            item.message = f"файл по маске «{mask_str(item)}» не найден"
            log.warning("[%s] файл не найден (маска «%s»)", item.name, mask_str(item))
            rep_row(item)
            continue
        src = matches[0]
        if len(matches) > 1:
            item.message = "несколько файлов по маске, взят первый: " + ", ".join(p.name for p in matches)
            log.warning("[%s] %s", item.name, item.message)
        claimed.add(src)
        item.src_file = src.name

        out_final = output_dir / item.result
        out_part = output_dir / (item.result + ".part")
        # Временная копия с СОХРАНЕНИЕМ имени файла: воркеры могут зависеть от
        # имени (Treolan: качество по суффиксу _nc/_demo)
        tmp_dir = Path(tempfile.mkdtemp(prefix="pricelist_"))
        tmp = tmp_dir / src.name
        t0 = time.monotonic()
        try:
            # Копия во временный файл, оригинал — в архив (ТЗ 4.1.4)
            shutil.copy2(str(src), str(tmp))
            archive_original(src, archive_sub)

            module = importlib.import_module(f"workers.{item.worker}")
            res = module.process(tmp, out_part, number, Ctx(pricelist_name=item.name))
            if res.rows_written == 0:
                # пустой результат почти всегда означает смену формата поставщиком
                raise RuntimeError("в файле не найдено ни одного товара — вероятно, изменился формат")
            if item.result in produced:
                raise RuntimeError(f"результат «{item.result}» уже создан этим прогоном другой записью настроек")
            out_part.replace(out_final)  # результат целиком либо никак
            produced.add(item.result)

            for w in res.warnings:
                log.warning("[%s] %s", item.name, w)
            if res.rows_with_errors:
                log.warning("[%s] строк с заполненной колонкой «Ошибка»: %d из %d",
                            item.name, res.rows_with_errors, res.rows_written)
            log.info("[%s] DONE: %s -> %s, строк %d, №%d..%d",
                     item.name, src.name, item.result, res.rows_written, number, res.last_number)
            number = res.last_number + 1
            item.status = "DONE"
            item.rows = res.rows_written
            item.rows_err = res.rows_with_errors
            if res.warnings:
                item.message = "; ".join([item.message, *res.warnings]).strip("; ")
            done_count += 1
        except Exception as e:
            had_error = True
            item.status = "ERROR"
            item.message = str(e)
            log.error("[%s] ОШИБКА: %s", item.name, e)
            log.debug("%s", traceback.format_exc())
            out_part.unlink(missing_ok=True)
        finally:
            item.seconds = time.monotonic() - t0
            shutil.rmtree(tmp_dir, ignore_errors=True)
            rep_row(item)

    unknown = [p.name for p in available if p not in claimed]
    if unknown:
        log.warning("Нераспознанные файлы во входном каталоге: %s", ", ".join(unknown))
        rep_f.write(f";;{', '.join(unknown)};UNKNOWN;;;;нераспознанные файлы\n")
    rep_f.close()
    log.info("Отчёт прогона: %s", report)

    if done_count and cfg.get("defaults", {}).get("write_done", True):
        (output_dir / DONE_FILE).write_text("", encoding="utf-8")
        log.info("Создан %s (обработано файлов: %d)", DONE_FILE, done_count)

    finished = datetime.now()
    err_count = sum(1 for i in items if i.status == "ERROR")
    summary = {
        "date": f"{started:%d.%m.%Y}", "start": f"{started:%H:%M:%S}",
        "finish": f"{finished:%H:%M:%S}",
        "seconds": (finished - started).total_seconds(),
        "result": "ОШИБКИ" if had_error else "OK",
        "done": done_count, "error": err_count,
        "no_file": sum(1 for i in items if i.status == "NO_FILE"),
        "rows": sum(i.rows for i in items),
        "rows_err": sum(i.rows_err for i in items),
        "report": str(report),
    }

    # Диагностика: история прогонов в архиве + страница report.html в output
    try:
        report_html.append_history(archive_dir, summary)
        page = report_html.render_page(items, unknown, summary,
                                       report_html.read_history(archive_dir))
        (output_dir / REPORT_PAGE).write_text(page, encoding="utf-8")
        log.info("Страница диагностики: %s", output_dir / REPORT_PAGE)
    except Exception as e:                                   # noqa: BLE001
        log.error("Диагностика (history/%s) не записана: %s", REPORT_PAGE, e)
    write_status(output_dir, "\n".join([
        f"Последний прогон: {summary['date']} {summary['start']} — "
        f"{summary['finish']} ({summary['seconds']:.0f} сек)",
        f"Итог: {summary['result']}",
        f"DONE={done_count}, ERROR={err_count}, NO_FILE={summary['no_file']}, "
        f"строк={summary['rows']}, строк с ошибками={summary['rows_err']}",
        f"Отчёт: {report}",
        f"Диагностика: {REPORT_PAGE} рядом с этим файлом",
    ]) + "\n")

    # Письмо-отчёт (email.yaml рядом с main.py; mode: always | errors)
    email_cfg = load_email_cfg(BASE_DIR)
    if want_mail(email_cfg, had_error):
        try:
            text, html_body = report_html.render_email(items, unknown, summary)
            subject = (f"Конвертер прайс-листов: {summary['result']} — "
                       f"обработано {done_count}, ошибок {err_count}, "
                       f"строк {summary['rows']} ({summary['date']})")
            attach = [(report.name, report.read_bytes(), "text", "csv")]
            send_mail(email_cfg, subject, text, html_body, attach)
            log.info("Письмо-отчёт отправлено: %s", ", ".join(email_cfg["mail_to"]))
        except Exception as e:                               # noqa: BLE001
            log.error("Письмо-отчёт не отправлено: %s", e)
            log.debug("%s", traceback.format_exc())
    elif email_cfg is None:
        log.info("Почтовые уведомления не настроены (нет email.yaml)")

    log.info("Завершено. DONE=%d, ERROR=%d, всего записей настроено=%d",
             done_count, err_count, len(items))
    lock.unlink(missing_ok=True)  # при аварийном завершении лок снимет 6-часовой перехват
    return 1 if had_error else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Конвертер прайс-листов (основной скрипт)")
    parser.add_argument("--settings", type=Path, default=BASE_DIR / "settings.yaml",
                        help="файл настроек (по умолчанию settings.yaml рядом со скриптом)")
    parser.add_argument("--check", action="store_true",
                        help="только проверить настройки/каталоги/сопоставление файлов, без обработки")
    args = parser.parse_args()
    sys.exit(check(args.settings) if args.check else run(args.settings))


if __name__ == "__main__":
    main()
