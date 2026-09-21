# Установка на Windows VPS (сетевые каталоги UNC)

Каталоги input/output/archive подключены как сетевые папки
`\\dev.best-practice.ru\{input,output,archive}` — буква диска НЕ нужна,
конвертер работает с UNC-путями напрямую (они уже прописаны в `settings.yaml`).

## Установка одной командой

В PowerShell на VPS (правой кнопкой по «Пуск» → Windows PowerShell):

```powershell
powershell -ExecutionPolicy Bypass -c "iwr -useb https://raw.githubusercontent.com/gynsus/best-practice-converter/main/install.ps1 | iex"
```

Скрипт: проверит/поставит Python 3.12 (winget), скачает код в
`C:\Convert\best-practice-converter`, создаст venv, поставит зависимости и
запустит `main.py --check` — проверку каталогов и сопоставления файлов.
При обновлении кода локальный `settings.yaml` сохраняется.

## Проверка перед боевым запуском

```powershell
C:\Convert\best-practice-converter\.venv\Scripts\python.exe C:\Convert\best-practice-converter\main.py --check
```

`--check` ничего не обрабатывает и не перемещает; он показывает:
- доступность трёх каталогов и права на запись (output/archive);
- какой файл из input подхватится какой записью настроек `[OK]`;
- для каких записей файла сейчас нет `[??]`;
- какие файлы в input не подходят ни под одну маску `[??]` — их имена надо
  привести к ожидаемым (см. таблицу ниже) либо поправить маску в settings.yaml.

## Ожидаемые имена файлов во входном каталоге

Сопоставление по маске (регистр букв не важен; `*` — любые символы):

| Поставщик | Имя файла в input (маска) | Файл результата |
|---|---|---|
| 3LOGIC | `3logic_2.xlsx` | 3logic_2.csv |
| A1TIS | `A1TIS.xls*` | A1TIS.csv |
| ABSOLUT TRADE | `ABSOLUT TRADE.xlsx` | ABSOLUT TRADE.csv |
| ARTRON | `Artron.xlsx` | Artron.csv |
| Citilink | `CitilinkPrice.xlsx` | Citilink.csv |
| Getsy | `Getsy.xlsx` | Getsy.csv |
| iDistribute | `iDistribute.xls` | iDistribute.csv |
| Komus | `komus_2.xlsx` | Komus_2.csv |
| Marvel | `Marvel.xlsx` | Marvel.csv |
| Merlion | `Merlion_2.xlsm` | Merlion_2.csv |
| MICS | `MICS.xlsx` | MICS.csv |
| Netlab | `NetlabPrice.xml` | NetLab_XML.csv |
| OCS | `OCS.xlsx` | OCS.csv |
| ProWay | `ProWay.xlsx` | ProWay.csv |
| Resurs Media (неконд.) | `Resurs Media_price_nec.xlsx` | Resurs Media_Nekond.csv |
| Resurs Media (структ.) | `Resurs Media_price_struct*.xlsx` | Resurs Media_Struct.csv |
| Treolan | `Treolan.xlsx` | Treolan.csv |
| Treolan (демо) | `Treolan_DEMO.xlsx` | Treolan_DEMO.csv |
| Treolan (некондиция) | `Treolan_NC.xlsx` | Treolan_NC.csv |
| VTT (RUB) | `vtt.main.price.rub.xls` | VTT_RUB.csv |
| VTT (USD) | `vtt.main.price.usd.xls` | VTT_USD.csv |
| VVP Group | `VVP_Group*` | VVP_Group.csv |

Если поставщик присылает файлы с датой в имени (например
`price_treolan_2026-09-21.xlsx`) — поменяйте маску записи на
`price_treolan*` в `settings.yaml`, ничего больше менять не нужно.

## Планировщик задач

Ежедневно в 22:00 (пример; время/периодичность — на ваше усмотрение):

```powershell
schtasks /Create /F /TN "PriceConverter" /SC DAILY /ST 22:00 /TR "C:\Convert\best-practice-converter\.venv\Scripts\python.exe C:\Convert\best-practice-converter\main.py"
```

Каждые 30 минут:

```powershell
schtasks /Create /F /TN "PriceConverter" /SC MINUTE /MO 30 /TR "C:\Convert\best-practice-converter\.venv\Scripts\python.exe C:\Convert\best-practice-converter\main.py"
```

Наложения прогонов не страшны: второй экземпляр увидит `converter.lock`
и выйдет с кодом 3.

Коды возврата для мониторинга: 0 — успех; 1 — часть прайсов с ошибкой;
2 — фатально (настройки/каталоги недоступны); 3 — уже идёт другой прогон.

## Если сетевые папки требуют логин/пароль

Если задача планировщика запускается под пользователем, у которого нет
сохранённого доступа к `\\dev.best-practice.ru`, сохраните учётные данные:

```powershell
cmdkey /add:dev.best-practice.ru /user:ИМЯ /pass:ПАРОЛЬ
```

(выполнить под тем же пользователем, от которого работает задача).

## Где смотреть результаты работы

- Результаты: `\\dev.best-practice.ru\output` (CSV + `done.txt`);
- Логи и отчёты: `\\dev.best-practice.ru\archive\ГГГГ.ММ.ДД\` —
  `run_*.log` (подробный лог с трейсбеками) и `run_report_*.csv`
  (сводка: статус, строк, строк с ошибками, время, сообщения);
- туда же перемещаются обработанные исходники.
