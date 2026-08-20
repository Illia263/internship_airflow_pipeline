# Полагодь те, що вже в проді

**Час:** 2 тижні
**Здача:** один PR + `POSTMORTEM.md`

---

## Легенда

Ти вийшов на роботу в понеділок.

Є пайплайн, який вантажить поїздки таксі в Postgres. Його писав стажер, він три місяці в проді, і всіх усе влаштовувало — поки не сталося три речі. Стажера немає.

Дашборд `dashboard_daily_revenue` читає таблицю `trips` прямо зараз. Ним користуються. Твоя задача — **не переписати з нуля**. Так робити не можна. Твоя задача — зрозуміти, що зламано, і полагодити так, щоб дашборд не помітив.

---

## Запуск

Треба: Docker, Docker Compose, Python 3.12+, ~8 ГБ вільного диска, інтернет один раз.

```bash
git clone <repo> && cd fix-the-pipeline
python -m venv .venv && source .venv/bin/activate
make setup          # качає дані TLC, піднімає Postgres. Перший раз ~10 хв.
```

Перевірка, що все живе:

```bash
make psql
taxi=# \dt
taxi=# select count(*) from trips;    -- 0, це нормально

python etl.py                          # запусти як є. Подивись, що буде.
```

Що з'явилось після `make setup`:

```
source/                 13 CSV: 12 місяців 2024 + yellow_tripdata_2024-06-broken.csv
expected/reference.csv  еталонні суми по місяцях. З ними звірятимешся.
etl.py                  те, що в проді
schema.sql              схема, яку залишив стажер
```

`source/` роздається по HTTP на `localhost:8000` — це «джерело». Так, це `http.server` поверх директорії. Але звертатись до нього треба по HTTP саме тому, що по HTTP бувають таймаути й обірвані з'єднання.

---

## Три інциденти

Кожен — реальний тікет із трекера.

### INC-1. «Дашборд показує 8 млн поїздок за березень. Їх було 3 млн»

12 березня джоб падав по таймауту. Черговий перезапустив тричі. Дані потроїлись. Зараз у таблиці лежить суміш, і ніхто не знає, які рядки справжні.

**Треба:** зробити так, щоб перезапуск не міг цього повторити. І прибрати наявні дублікати, не зупиняючи дашборд.

### INC-2. «Треба перезалити січень. Джерело перевидало файл»

Запустив — залив поточний місяць. Ще раз — знову поточний. Джоб фізично не вміє завантажити минуле.

**Треба:** `--month 2024-01` і `--backfill 2024-01:2024-12`.

### INC-3. «Бухгалтерія каже, виручка за лютий розходиться на 340 злотих»

Різниця дрібна, стабільна, росте з обсягом. Ніхто не знає звідки.

**Треба:** знайти причину, довести тестом, полагодити.

```bash
make check-money    # покаже обидва числа
```

---

## Вимоги

1. `python etl.py --month 2024-01`
2. `python etl.py --backfill 2024-01:2024-12`
3. Повторний запуск за той самий місяць не дублює дані
4. Кожен відхилений рядок — у dead-letter із причиною
5. Відхилено > 5% → падаємо, і **не лишаємо часткових даних**
6. RSS < 500 МБ на будь-якій кількості місяців
7. 500k рядків < 60 с
8. Структуровані логи з `run_id`
9. Exit codes: 0 — ок, 1 — дані погані, 2 — інфраструктура

---

## Критерії прийому

Це не «на око». Це команди.

```bash
make check-idempotent     # diff має бути порожній
make check-memory         # Maximum resident set size < 500000 kbytes
make check-money          # два числа мають збігтись до копійки
```

```bash
# Часткові дані
make reset
python etl.py --month 2024-06-broken
echo $?                                          # 1
make psql -c "select count(*) from trips"        # 0, не 350000

# Dead-letter
wc -l dead_letter/dt=2024-06/*.ndjson
head -1 dead_letter/dt=2024-06/*.ndjson | jq .reason

# Backfill
make reset && python etl.py --backfill 2024-01:2024-12
# 12 рядків, кожен зі своїм місяцем:
make psql -c "select date_trunc('month', pickup) m, count(*) from trips group by 1 order by 1"
```

---

## Головний артефакт: `POSTMORTEM.md`

Код — половина роботи.

| # | Що знайшов | Як це проявилось би в проді | Чому так сталось | Фікс | Тест на регрес |
|---|---|---|---|---|---|

Правила:

- **Симптом — не «код поганий».** «`float` для грошей» — не симптом. «Виручка за лютий розходиться на 340 злотих, і розбіжність росте з обсягом» — симптом.
- **Кожен фікс має тест.** Без тесту це не фікс, а надія.
- **Мінімум один рядок «знайшов, але не чіпав»** — з поясненням, чому зараз не варто.

У пайплайні більше проблем, ніж три інциденти. Скільки — не скажу. У проді теж ніхто не каже.

---

## Заборонено

- Переписати з нуля. Схему міняти можна — але з міграцією, дашборд має пережити.
- Лікувати симптом. `DISTINCT` у в'юсі поверх дублів — не фікс INC-1.
- `except Exception: pass` у будь-якому вигляді, включно з `logger.warning` і `continue`.
- Оптимізувати незаміряне. У PR має бути число «до» і «після».

---

## Рубрика (100)

| | Балів |
|---|---|
| Три інциденти закриті, причини названі правильно | 30 |
| Знайдено проблеми, про які не питали | 20 |
| Кожен фікс має тест на регрес | 20 |
| Критерії прийому проходять на чужій машині | 15 |
| POSTMORTEM читається людиною, що не бачила коду | 15 |

**Незалік незалежно від балів:**
- ідемпотентність «доведена» словами, а не `make check-idempotent`
- гроші лишились `float`
- у POSTMORTEM написано «переписав, тепер працює»

---

# Матчастина

Читай **під задачу**, а не підряд. Кожен блок відповідає конкретній проблемі, яку ти зустрінеш.

## Коли впреться в пам'ять (вимога 6)

Симптом: `--backfill 2024-01:2024-12` з'їдає 12 ГБ і його вбиває OOM killer.

- David Beazley, **Generator Tricks for Systems Programmers** — https://www.dabeaz.com/generators/
  Єдине, що треба прочитати цілком. Слайди 1–40 — саме твій випадок.
- `itertools` — https://docs.python.org/3/library/itertools.html (`islice`, `chain`)
- `tracemalloc` — https://docs.python.org/3/library/tracemalloc.html
- Fluent Python, Ramalho, розділ 17 (ітератори й генератори)

Пастка: `tracemalloc` бачить лише пам'ять Python-алокатора. Реальний RSS процесу — `/usr/bin/time -v` або `psutil`. Різниця тебе здивує, коли дійдеш до parquet.

## Коли впреться в гроші (INC-3)

```python
>>> 0.1 + 0.2
0.30000000000000004
```

Далі має дійти самому. Якщо не доходить:

- **What Every Computer Scientist Should Know About Floating-Point** — https://docs.oracle.com/cd/E19957-01/806-3568/ncg_goldberg.html (перші 3 сторінки, решта — на потім)
- `decimal` — https://docs.python.org/3/library/decimal.html
- PostgreSQL, числові типи — https://www.postgresql.org/docs/current/datatype-numeric.html
  Читай абзац про `numeric` vs `double precision`. Там прямим текстом написано, що робити з грошима.

Питання, на яке маєш відповісти в POSTMORTEM: чому розбіжність **стабільна**, а не випадкова?

## Коли впреться в ідемпотентність (INC-1, INC-2)

Це найважливіша частина завдання. Решта — технікалії.

- **Fundamentals of Data Engineering**, Reis & Housley — розділ 5 (Data Generation) і 8 (Queries, Modeling)
- Idempotency в дата-пайплайнах: https://www.startdataengineering.com/post/why-how-idempotent-data-pipeline/
- `INSERT ... ON CONFLICT` — https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT
- Atomic file operations: `os.rename` — POSIX гарантує атомарність у межах однієї ФС. Це твій друг для критерію «не лишати часткових даних».

Питання: у тебе є `INSERT ... ON CONFLICT DO NOTHING`. По якому ключу? У вихідних даних немає `trip_id`. Що робитимеш?

## Коли впреться в швидкість завантаження (вимога 7)

Симптом: 500k `INSERT` виконуються 25 хвилин.

- `COPY` — https://www.postgresql.org/docs/current/sql-copy.html
- `psycopg2.copy_expert` — https://www.psycopg.org/docs/cursor.html#cursor.copy_expert
- Чому `INSERT` у циклі повільний: кожен — окремий round-trip до сервера + окремий WAL-запис. `COPY` — один потік.

Заміряй **до** і **після**. Число в PR.

## Коли впреться в биті рядки (вимоги 4, 5)

- Ієрархія винятків — https://docs.python.org/3/library/exceptions.html#exception-hierarchy
  Подивись, що саме ловить `except Exception`. І що не ловить.
- `raise ... from` — https://docs.python.org/3/tutorial/errors.html#exception-chaining
- Dead Letter Queue, патерн — https://learn.microsoft.com/en-us/azure/architecture/patterns/
  (шукай Dead Letter Channel; концепція та сама, реалізація в тебе — файл)

Питання: `except Exception: pass` ловить і `KeyboardInterrupt`? А `MemoryError`? Перевір, не вгадуй.

## Коли впреться в HTTP (вимога 9)

- `requests`, обробка помилок — https://requests.readthedocs.io/en/latest/user/quickstart/#errors-and-exceptions
  Зверни увагу: `requests.get()` **не кидає виняток на 404**. `r.content` мовчки поверне HTML сторінки помилки.
- **Exponential Backoff and Jitter**, AWS — https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/
  Читай про full jitter. Це та стаття, після якої стає зрозуміло, чому retry без jitter гірший за відсутність retry.
- `tenacity` — https://tenacity.readthedocs.io/

## Коли впреться в логи (вимога 8)

- `logging` cookbook — https://docs.python.org/3/howto/logging-cookbook.html
- `contextvars` — https://docs.python.org/3/library/contextvars.html
  Це відповідь на питання «як протягнути `run_id` крізь 8 рівнів стеку, не передаючи аргументом».
- `structlog` — https://www.structlog.org/

## Коли впреться в SQL-ін'єкцію

Подивись уважно на цей рядок:

```python
cur.execute("INSERT INTO trips VALUES (%s, '%s', %s, %s)" % (...))
```

- https://www.psycopg.org/docs/usage.html#the-problem-with-the-query-parameters
  Перший абзац. Червона рамка. Прочитай двічі.

## Загальне, читати паралельно

- **Fundamentals of Data Engineering**, Reis & Housley — карта місцевості. По 20 сторінок на день.
- **Designing Data-Intensive Applications**, Kleppmann — розділ 3 і 11. Не зараз, але скоро.

---

## Як я перевірятиму

1. Клоную твій PR на чисту машину.
2. `make setup && make check-idempotent && make check-memory && make check-money`.
3. Читаю POSTMORTEM. Якщо після нього не розумію, що було зламано — незалік, навіть якщо код бездоганний.
4. Ставлю питання «а що ще?» на кожен твій фікс.

Питання, до яких готуйся:

- Ти полагодив `datetime.now()`. Що ще в цьому файлі виконується в момент, який ти не контролюєш?
- Процес убито `kill -9` між записом файлу і комітом у БД. Що в системі?
- Твій `ON CONFLICT` працює. Що станеться, якщо джерело перевидасть файл із виправленими сумами?
- Чому розбіжність у грошах була стабільною?
