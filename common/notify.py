# -*- coding: utf-8 -*-
"""Почтовые уведомления о результатах прогона (SMTP SSL/TLS).

Учётные данные — в ОТДЕЛЬНОМ файле email.yaml рядом с main.py: он в .gitignore
(в репозиторий не попадает) и сохраняется установщиком при обновлении.
Формат email.yaml:

    enabled: true
    smtp_host: mail.example.ru
    smtp_port: 465                 # SSL/TLS
    user: robot@example.ru
    password: "..."
    mail_from: robot@example.ru    # необязательно, по умолчанию = user
    mail_to: [one@example.ru, two@example.ru]
    mode: always                   # always — письмо после каждого прогона;
                                   # errors — только при ошибках/фатале
    verify_ssl: true               # false — если сертификат самоподписанный
"""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate
from pathlib import Path

import yaml

EMAIL_FILE = "email.yaml"


def load_email_cfg(base_dir: Path) -> dict | None:
    """Читает email.yaml; None — если файла нет или уведомления выключены.
    Ошибочный файл настроек не должен ронять прогон — возвращаем None."""
    path = base_dir / EMAIL_FILE
    if not path.is_file():
        return None
    try:
        cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not cfg.get("enabled"):
            return None
        for key in ("smtp_host", "smtp_port", "user", "password", "mail_to"):
            if not cfg.get(key):
                raise ValueError(f"не задано поле {key}")
        if isinstance(cfg["mail_to"], str):
            cfg["mail_to"] = [cfg["mail_to"]]
        return cfg
    except Exception as e:                        # noqa: BLE001
        print(f"email.yaml не прочитан, уведомления отключены: {e}")
        return None


def want_mail(cfg: dict | None, had_error: bool) -> bool:
    if cfg is None:
        return False
    return had_error or str(cfg.get("mode", "always")).lower() != "errors"


def send_mail(cfg: dict, subject: str, text_body: str, html_body: str | None = None,
              attachments: list[tuple[str, bytes, str, str]] | None = None) -> None:
    """Отправляет письмо; attachments — (имя файла, байты, maintype, subtype).
    Исключения пробрасываются — вызывающий решает, что с ними делать."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.get("mail_from") or cfg["user"]
    msg["To"] = ", ".join(cfg["mail_to"])
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    for name, data, maintype, subtype in attachments or []:
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)

    if cfg.get("verify_ssl", True):
        ctx = ssl.create_default_context()
    else:
        ctx = ssl._create_unverified_context()    # noqa: SLF001 — осознанно, по настройке
    with smtplib.SMTP_SSL(cfg["smtp_host"], int(cfg["smtp_port"]),
                          context=ctx, timeout=60) as smtp:
        smtp.login(cfg["user"], cfg["password"])
        smtp.send_message(msg)
