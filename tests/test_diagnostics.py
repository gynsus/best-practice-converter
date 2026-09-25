# -*- coding: utf-8 -*-
"""Тесты диагностики: история прогонов, report.html, письмо, email.yaml,
инкрементальный отчёт и status.txt на реальном прогоне main.run()."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import yaml

import main
from common import report_html
from common.notify import load_email_cfg, want_mail

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _summary(result="OK", **kw):
    s = dict(date="21.09.2026", start="22:00:00", finish="22:01:43", seconds=103.0,
             result=result, done=17, error=0, no_file=5, rows=290116, rows_err=463,
             report=r"\\srv\archive\2026.09.21\run_report_220143.csv")
    s.update(kw)
    return s


def _item(**kw):
    d = dict(name="Тест", masks=["t*.xlsx"], worker="w", result="t.csv", enabled=True,
             status="DONE", src_file="t.xlsx", rows=10, rows_err=1, seconds=1.5, message="")
    d.update(kw)
    return main.Item(**d)


# --- История ---

def test_history_append_and_read(tmp_path):
    report_html.append_history(tmp_path, _summary())
    report_html.append_history(tmp_path, _summary(result="ОШИБКИ", error=2))
    rows = report_html.read_history(tmp_path)
    assert len(rows) == 2
    assert rows[0][3] == "ОШИБКИ"          # новые сверху
    assert rows[1][3] == "OK"
    head = (tmp_path / "history.csv").read_text(encoding="utf-8-sig").splitlines()[0]
    assert head.startswith("Дата;")


# --- Страница и письмо ---

def test_render_page_and_email(tmp_path):
    items = [_item(), _item(name="Сломанный", status="ERROR",
                    message='не найдена колонка "Цена" <тег>')]
    page = report_html.render_page(items, ["левый.txt"], _summary(result="ОШИБКИ", error=1),
                                   report_html.read_history(tmp_path))
    assert "Сломанный" in page and "ERROR" in page and "UNKNOWN" in page
    assert "&lt;тег&gt;" in page            # экранирование HTML
    text, html_body = report_html.render_email(items, [], _summary())
    assert "Итог: OK" in text and "строк 10" in text
    assert "Тест" in html_body


# --- email.yaml ---

def test_email_cfg_missing_and_disabled(tmp_path):
    assert load_email_cfg(tmp_path) is None
    (tmp_path / "email.yaml").write_text("enabled: false\n", encoding="utf-8")
    assert load_email_cfg(tmp_path) is None


def test_email_cfg_valid_and_modes(tmp_path):
    (tmp_path / "email.yaml").write_text(yaml.safe_dump(dict(
        enabled=True, smtp_host="h", smtp_port=465, user="u", password="p",
        mail_to="one@x.ru", mode="errors")), encoding="utf-8")
    cfg = load_email_cfg(tmp_path)
    assert cfg["mail_to"] == ["one@x.ru"]   # строка -> список
    assert want_mail(cfg, had_error=True)
    assert not want_mail(cfg, had_error=False)
    assert not want_mail(None, had_error=True)


def test_email_cfg_broken_is_ignored(tmp_path):
    (tmp_path / "email.yaml").write_text("enabled: true\nsmtp_host: h\n", encoding="utf-8")
    assert load_email_cfg(tmp_path) is None  # нет обязательных полей -> отключено


# --- send_output.py: сбор файлов output и ZIP ---

def test_send_output_collect_and_zip(tmp_path):
    import io, zipfile
    from send_output import build_zip, collect
    (tmp_path / "A.csv").write_text("данные;1\n", encoding="utf-8-sig")
    (tmp_path / "B.CSV").write_text("x\n", encoding="utf-8")
    (tmp_path / "report.html").write_text("<html>", encoding="utf-8")
    (tmp_path / "converter.lock").write_text("1", encoding="utf-8")
    files = collect(tmp_path, "*.csv")
    assert [p.name for p in files] == ["A.csv", "B.CSV"]      # регистр не важен, lock исключён
    assert len(collect(tmp_path, "*")) == 3                    # без lock
    with zipfile.ZipFile(io.BytesIO(build_zip(files))) as z:
        assert sorted(z.namelist()) == ["A.csv", "B.CSV"]
        assert "данные" in z.read("A.csv").decode("utf-8-sig")


# --- Реальный прогон: инкрементальный отчёт, status.txt, report.html ---

@pytest.mark.skipif(not FIXTURES.is_dir(), reason="нет fixtures")
def test_run_writes_diagnostics(tmp_path, monkeypatch):
    inp, out, arc = tmp_path / "in", tmp_path / "out", tmp_path / "arc"
    inp.mkdir(); out.mkdir(); arc.mkdir()
    import shutil
    shutil.copy(FIXTURES / "Treolan_DEMO.xlsx", inp / "Treolan_DEMO.xlsx")
    (inp / "мусор.bin").write_bytes(b"x")
    (inp / "ready.txt").write_text("09:15:00 Treolan_DEMO.xlsx\n", encoding="utf-8")
    settings = tmp_path / "s.yaml"
    settings.write_text(yaml.safe_dump(dict(
        dirs=dict(input=str(inp), output=str(out), archive=str(arc)),
        pricelists=[
            dict(name="Treolan (демо)", match="Treolan_DEMO.xlsx",
                 worker="treolan", result="Treolan_DEMO.csv"),
            dict(name="Отключённый", match="никогда.xlsx", worker="treolan",
                 result="x.csv", enabled=False),
        ]), allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(main, "BASE_DIR", tmp_path)   # email.yaml нет -> без писем

    rc = main.run(settings)
    assert rc == 0

    # иерархия архива: ГГГГ.ММ.ДД/<номер запуска>/{Input,Output,Log}
    sub = next(arc.glob("????.??.??")) / "1"
    assert (sub / "Input").is_dir() and (sub / "Output").is_dir() and (sub / "Log").is_dir()
    rep = next((sub / "Log").glob("run_report_*.csv"))
    assert next((sub / "Log").glob("run_*.log"), None) is not None
    assert (sub / "Input" / "Treolan_DEMO.xlsx").is_file()     # исходник в Input
    assert (sub / "Output" / "Treolan_DEMO.csv").is_file()     # копия результата в Output
    lines = rep.read_text(encoding="utf-8-sig").splitlines()
    assert any("DONE" in ln for ln in lines)
    assert any("SKIP" in ln for ln in lines)
    assert any("UNKNOWN" in ln and "мусор.bin" in ln for ln in lines)

    status = (out / "status.txt").read_text(encoding="utf-8")
    assert "Итог: OK" in status and "DONE=1" in status

    page = (out / "report.html").read_text(encoding="utf-8")
    assert "Treolan (демо)" in page and "История прогонов" in page
    hist = report_html.read_history(arc)
    assert len(hist) == 1 and hist[0][3] == "OK"
    assert (out / "Treolan_DEMO.csv").is_file()
    assert (out / "done.txt").is_file()
    assert not (out / "converter.lock").exists()
    # ready.txt не попал в UNKNOWN и забран в архив запуска (Input)
    assert not any("ready.txt" in ln for ln in lines)
    assert not (inp / "ready.txt").exists()
    assert (sub / "Input" / "ready.txt").is_file()

    # второй запуск в тот же день -> папка «2»
    rc2 = main.run(settings)
    assert rc2 == 0
    assert (sub.parent / "2" / "Log").is_dir()
