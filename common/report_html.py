# -*- coding: utf-8 -*-
"""Диагностика прогонов: history.csv в корне архива, страница report.html
в выходном каталоге, тело письма-отчёта.

Объекты item — записи main.Item (duck-typing: name, masks, src_file, status,
rows, rows_err, seconds, message)."""
from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

HISTORY_FILE = "history.csv"
HISTORY_HEADER = "Дата;Старт;Финиш;Итог;DONE;ERROR;NO_FILE;Строк;Строк с ошибками;Время, сек\n"

STATUS_COLORS = {          # (фон, текст) — светлые тона, читаются и в письме
    "DONE":    ("#e9f6ef", "#17714a"),
    "ERROR":   ("#fdecec", "#b42318"),
    "FATAL":   ("#fdecec", "#b42318"),
    "NO_FILE": ("#f2f4f7", "#667085"),
    "SKIP":    ("#f2f4f7", "#667085"),
    "UNKNOWN": ("#fef3ec", "#a1580e"),
}


def esc(s) -> str:
    return html.escape(str(s), quote=False)


# --- История прогонов -------------------------------------------------------

def append_history(archive_dir: Path, summary: dict) -> None:
    path = archive_dir / HISTORY_FILE
    line = (f"{summary['date']};{summary['start']};{summary['finish']};{summary['result']};"
            f"{summary['done']};{summary['error']};{summary['no_file']};"
            f"{summary['rows']};{summary['rows_err']};{summary['seconds']:.0f}\n")
    new = not path.exists()
    with open(path, "a", encoding="utf-8-sig", newline="\n") as f:
        if new:
            f.write(HISTORY_HEADER)
        f.write(line)


def read_history(archive_dir: Path, limit: int = 30) -> list[list[str]]:
    """Последние строки истории, новые сверху."""
    path = archive_dir / HISTORY_FILE
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8-sig").splitlines()[1:]
    rows = [ln.split(";") for ln in lines if ln.strip()]
    return list(reversed(rows))[:limit]


# --- Таблицы -----------------------------------------------------------------

def _badge(status: str) -> str:
    bg, fg = STATUS_COLORS.get(status, ("#f2f4f7", "#667085"))
    return (f'<span style="background:{bg};color:{fg};border-radius:10px;'
            f'padding:1px 9px;font-size:12px;font-weight:600">{esc(status or "—")}</span>')


def items_table(items, unknown: list[str]) -> str:
    """Таблица результатов по прайс-листам, инлайн-стили (годится и для письма)."""
    td = 'style="padding:6px 10px;border-bottom:1px solid #e4e7ec;font-size:13px"'
    th = ('style="padding:6px 10px;border-bottom:2px solid #cfd6e0;font-size:13px;'
          'text-align:left;background:#eef2f9"')
    out = ['<table style="border-collapse:collapse;width:100%;background:#fff">',
           f"<tr><th {th}>Прайс-лист</th><th {th}>Файл</th><th {th}>Статус</th>"
           f"<th {th}>Строк</th><th {th}>С ошибками</th><th {th}>Сек</th><th {th}>Сообщение</th></tr>"]
    for it in items:
        rows = it.rows if it.status == "DONE" else ""
        rerr = it.rows_err if it.status == "DONE" else ""
        secs = f"{it.seconds:.1f}" if it.seconds else ""
        out.append(f"<tr><td {td}><b>{esc(it.name)}</b></td><td {td}>{esc(it.src_file)}</td>"
                   f"<td {td}>{_badge(it.status)}</td><td {td}>{rows}</td><td {td}>{rerr}</td>"
                   f"<td {td}>{secs}</td><td {td}>{esc(it.message)}</td></tr>")
    if unknown:
        out.append(f"<tr><td {td}></td><td {td}>{esc(', '.join(unknown))}</td>"
                   f"<td {td}>{_badge('UNKNOWN')}</td><td {td}></td><td {td}></td><td {td}></td>"
                   f"<td {td}>файлы не подходят ни под одну маску</td></tr>")
    out.append("</table>")
    return "\n".join(out)


def _history_table(rows: list[list[str]]) -> str:
    if not rows:
        return "<p>Истории пока нет.</p>"
    td = 'style="padding:5px 10px;border-bottom:1px solid #e4e7ec;font-size:13px"'
    th = ('style="padding:5px 10px;border-bottom:2px solid #cfd6e0;font-size:13px;'
          'text-align:left;background:#eef2f9"')
    heads = HISTORY_HEADER.strip().split(";")
    out = ['<table style="border-collapse:collapse;width:100%;background:#fff">',
           "<tr>" + "".join(f"<th {th}>{esc(h)}</th>" for h in heads) + "</tr>"]
    for r in rows:
        cells = []
        for i, c in enumerate(r):
            if i == 3 and c:  # колонка «Итог»
                color = "#17714a" if c == "OK" else "#b42318"
                v = f'<span style="color:{color};font-weight:600">{esc(c)}</span>'
            else:
                v = esc(c)
            cells.append(f"<td {td}>{v}</td>")
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</table>")
    return "\n".join(out)


# --- Страница report.html и письмо -------------------------------------------

def _summary_line(s: dict) -> str:
    color = "#17714a" if s["result"] == "OK" else "#b42318"
    return (f'<p style="font-size:15px">Итог: <b style="color:{color}">{esc(s["result"])}</b> — '
            f'обработано <b>{s["done"]}</b>, ошибок <b>{s["error"]}</b>, '
            f'нет файла {s["no_file"]}, строк в результатах <b>{s["rows"]}</b> '
            f'(с заполненной колонкой «Ошибка»: {s["rows_err"]}), '
            f'время {s["seconds"]:.0f} сек.<br>'
            f'Прогон {esc(s["date"])} {esc(s["start"])} — {esc(s["finish"])}. '
            f'Подробный отчёт: <code>{esc(s.get("report", ""))}</code></p>')


def render_page(items, unknown: list[str], summary: dict, history: list[list[str]]) -> str:
    return f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Конвертер — диагностика прогонов</title></head>
<body style="margin:0;background:#f6f7f9;color:#1e2430;font:15px/1.6 -apple-system,'Segoe UI',Roboto,sans-serif">
<div style="max-width:1000px;margin:0 auto;padding:30px 20px 60px">
<h1 style="font-size:24px;margin:0 0 4px">Конвертер прайс-листов — диагностика</h1>
<p style="color:#667085;margin:0 0 20px">Страница обновляется автоматически в конце каждого прогона.
Сформирована: {datetime.now():%d.%m.%Y %H:%M:%S}</p>
{_summary_line(summary)}
<h2 style="font-size:18px;border-bottom:2px solid #e4e7ec;padding-bottom:5px">Последний прогон</h2>
<div style="overflow-x:auto;border:1px solid #e4e7ec;border-radius:10px">{items_table(items, unknown)}</div>
<h2 style="font-size:18px;border-bottom:2px solid #e4e7ec;padding-bottom:5px;margin-top:30px">История прогонов</h2>
<div style="overflow-x:auto;border:1px solid #e4e7ec;border-radius:10px">{_history_table(history)}</div>
<p style="color:#667085;font-size:13px;margin-top:24px">Если прогон оборвался аварийно, сведения о нём сюда
не попадают — смотрите status.txt рядом с этой страницей и run_*.log в архиве за нужную дату.</p>
</div></body></html>"""


def render_email(items, unknown: list[str], summary: dict) -> tuple[str, str]:
    """(текст, html) для письма-отчёта."""
    lines = [f"Конвертер прайс-листов, прогон {summary['date']} {summary['start']} — {summary['finish']}",
             f"Итог: {summary['result']}. DONE={summary['done']}, ERROR={summary['error']}, "
             f"NO_FILE={summary['no_file']}, строк={summary['rows']} "
             f"(с ошибками {summary['rows_err']}), {summary['seconds']:.0f} сек.", ""]
    for it in items:
        extra = f" — {it.message}" if it.message else ""
        rows = f", строк {it.rows}" if it.status == "DONE" else ""
        lines.append(f"  [{it.status or '—':7}] {it.name}: {it.src_file or '—'}{rows}{extra}")
    if unknown:
        lines.append(f"  [UNKNOWN] нераспознанные файлы: {', '.join(unknown)}")
    lines += ["", f"Подробный отчёт: {summary.get('report', '')}"]
    text = "\n".join(lines)

    body = f"""<html><body style="margin:0;padding:16px;background:#f6f7f9;color:#1e2430;
font-family:-apple-system,'Segoe UI',Roboto,sans-serif">
<h2 style="font-size:18px;margin:0 0 8px">Конвертер прайс-листов — отчёт прогона</h2>
{_summary_line(summary)}
{items_table(items, unknown)}
</body></html>"""
    return text, body
