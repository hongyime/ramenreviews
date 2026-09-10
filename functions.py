"""Validated SQLite helpers. Importing this module never opens a database."""
from contextlib import contextmanager
import csv
from pathlib import Path
import sqlite3
from typing import Iterator, Mapping

COLUMNS = ('ID', 'Country', 'Brand', 'Type', 'Package', 'Rating')
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
MAX_OFFSET = 100_000
MAX_VALUE_LENGTH = 4096


class ValidationError(ValueError):
    """A request cannot be translated into a safe, unambiguous operation."""


def capitalisewords(value: str) -> str:
    """Retained for callers of the old utility; storage preserves input text."""
    return ' '.join(word.capitalize() for word in value.split(' '))


def dictfactory(cursor, row) -> dict:
    return {column[0]: value for column, value in zip(cursor.description, row)}


def _casefold(value):
    return value.casefold() if isinstance(value, str) else value


def _table(tablename: str) -> str:
    if not isinstance(tablename, str) or tablename.casefold() != 'ratings':
        raise ValidationError('Only the Ratings table is supported.')
    return '"Ratings"'


def _value(value) -> str:
    if value is None or isinstance(value, (dict, list, tuple, bool)):
        raise ValidationError('Review values must be text or numbers, not null.')
    text = str(value)
    if len(text) > MAX_VALUE_LENGTH or '\x00' in text:
        raise ValidationError('A review value is too long or contains a null character.')
    return text


def _fields(values: Mapping, *, extra=()) -> dict:
    if not isinstance(values, Mapping):
        raise ValidationError('Supply an object containing review fields.')
    names = {name.casefold(): name for name in (*COLUMNS, *extra)}
    normalized = {}
    for key, value in values.items():
        name = names.get(key.casefold()) if isinstance(key, str) else None
        if name is None:
            raise ValidationError('Unknown review field.')
        if name in normalized:
            raise ValidationError('Supply each review field only once.')
        normalized[name] = _value(value)
    return normalized


def pagination(limit=DEFAULT_LIMIT, offset=0) -> tuple[int, int]:
    def integer(value):
        text = str(value)
        if not text.isascii() or not text.isdecimal() or len(text) > 6:
            raise ValidationError('Pagination values must be non-negative integers.')
        return int(text)
    limit, offset = integer(limit), integer(offset)
    if not 1 <= limit <= MAX_LIMIT or offset > MAX_OFFSET:
        raise ValidationError('Use a limit from 1 to 200 and an offset up to 100000.')
    return limit, offset


@contextmanager
def _connection(databasename: str, *, create=False, write=False) -> Iterator[sqlite3.Connection]:
    path = Path(databasename)
    if path.suffix != '.db':
        path = Path(str(path) + '.db')
    mode = 'rwc' if create else ('rw' if write else 'ro')
    conn = sqlite3.connect(path.resolve().as_uri() + '?mode=' + mode, uri=True, timeout=2)
    conn.row_factory = dictfactory
    try:
        conn.create_function('ramen_casefold', 1, _casefold, deterministic=True)
        with conn:
            yield conn
    finally:
        conn.close()


def _where(values: Mapping, *, keyword=False) -> tuple[str, list[str]]:
    fields = _fields(values, extra=('Keyword',) if keyword else ())
    if not fields:
        raise ValidationError('Supply at least one filter.')
    clauses, params = [], []
    for name, value in fields.items():
        if name == 'Keyword':
            if not value.strip():
                raise ValidationError('A keyword must contain text.')
            clauses.append('instr(ramen_casefold("Type"), ?) > 0')
            params.append(value.casefold())
        elif name in {'ID', 'Rating'}:
            clauses.append(f'"{name}" = ? COLLATE BINARY')
            params.append(value)
        else:
            clauses.append(f'ramen_casefold("{name}") = ? COLLATE BINARY')
            params.append(value.casefold())
    return ' AND '.join(clauses), params


def createone(databasename: str, tablename: str) -> bool:
    table = _table(tablename)
    columns = ', '.join(f'"{column}" TEXT' for column in COLUMNS)
    with _connection(databasename, create=True, write=True) as conn:
        conn.execute(f'CREATE TABLE IF NOT EXISTS {table} ({columns})')
    return True


def insertone(databasename: str, tablename: str, dic: Mapping) -> int:
    table, fields = _table(tablename), _fields(dic)
    if not fields:
        raise ValidationError('Supply at least one review field.')
    columns = ', '.join(f'"{name}"' for name in fields)
    placeholders = ', '.join('?' for _ in fields)
    with _connection(databasename, write=True) as conn:
        # Identifiers come only from _table/_fields; every value is bound.
        return conn.execute(f'INSERT INTO {table} ({columns}) VALUES ({placeholders})', tuple(fields.values())).rowcount  # nosec B608


def insertall(databasename: str, csvname: str, tablename='Ratings') -> int:
    """Append a bounded CSV atomically. Explicit repeat imports append again."""
    table = _table(tablename)
    path = Path(csvname)
    if path.suffix != '.csv':
        path = Path(str(path) + '.csv')
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValidationError('CSV imports are limited to 8 MiB.')
    columns = ', '.join(f'"{name}"' for name in COLUMNS)
    # Both the table and projection are fixed allowlisted identifiers.
    statement = f'INSERT INTO {table} ({columns}) VALUES (?, ?, ?, ?, ?, ?)'  # nosec B608
    count = 0
    with path.open(encoding='utf-8-sig', newline='') as source:
        reader = csv.DictReader(source, strict=True)
        if reader.fieldnames is None or len(reader.fieldnames) != len(COLUMNS) or set(reader.fieldnames) != set(COLUMNS):
            raise ValidationError('The CSV header must contain the six review columns once each.')
        with _connection(databasename, write=True) as conn:
            for row in reader:
                count += 1
                if count > 10_000:
                    raise ValidationError('CSV imports are limited to 10000 rows.')
                fields = _fields(row)
                conn.execute(statement, tuple(fields[name] for name in COLUMNS))
    return count


def deleteall(databasename: str, tablename: str) -> int:
    table = _table(tablename)
    with _connection(databasename, write=True) as conn:
        # _table permits Ratings only.
        return conn.execute(f'DELETE FROM {table}').rowcount  # nosec B608


def deletesome(databasename: str, tablename: str, dic: Mapping) -> int:
    table = _table(tablename)
    where, params = _where(dic)
    with _connection(databasename, write=True) as conn:
        # _where builds clauses from allowlisted columns and binds all values.
        return conn.execute(f'DELETE FROM {table} WHERE {where}', params).rowcount  # nosec B608


def updatesome(databasename: str, tablename: str, dic: Mapping) -> int:
    table = _table(tablename)
    fields = _fields(dic, extra=tuple('Update' + name.lower() for name in COLUMNS if name != 'ID'))
    filters = {key: value for key, value in fields.items() if not key.startswith('Update')}
    updates = {key[6:].capitalize(): value for key, value in fields.items() if key.startswith('Update')}
    where, params = _where(filters)
    if not updates:
        raise ValidationError('Supply at least one update field.')
    assignments = ', '.join(f'"{name}" = ?' for name in updates)
    with _connection(databasename, write=True) as conn:
        # _fields/_where constrain identifiers; assignments and filters are bound.
        return conn.execute(f'UPDATE {table} SET {assignments} WHERE {where}', [*updates.values(), *params]).rowcount  # nosec B608


def read_page(databasename: str, tablename: str, filters=None, *, sortby='ID', limit=DEFAULT_LIMIT, offset=0) -> dict:
    table = _table(tablename)
    limit, offset = pagination(limit, offset)
    sort = next((column for column in COLUMNS if column.casefold() == str(sortby).casefold()), None)
    if sort is None:
        raise ValidationError('Choose a review column to sort by.')
    where, params = _where(filters, keyword=True) if filters else ('1', [])
    columns = ', '.join(f'"{name}"' for name in COLUMNS)
    with _connection(databasename) as conn:
        # Projection and sort use COLUMNS; filters, limit and offset are bound.
        records = conn.execute(f'SELECT {columns} FROM {table} WHERE {where} ORDER BY "{sort}" COLLATE NOCASE ASC, rowid ASC LIMIT ? OFFSET ?', [*params, limit + 1, offset]).fetchall()  # nosec B608
    has_more = len(records) > limit
    return {'items': records[:limit], 'limit': limit, 'offset': offset, 'has_more': has_more,
            'next_offset': offset + limit if has_more and offset + limit <= MAX_OFFSET else None}


def searchsome(databasename: str, tablename: str, dic: Mapping, *, limit=DEFAULT_LIMIT, offset=0) -> list[dict]:
    fields = _fields(dic, extra=('Sortby', 'Keyword'))
    sort = fields.pop('Sortby', 'ID')
    _where(fields, keyword=True)
    return read_page(databasename, tablename, fields, sortby=sort, limit=limit, offset=offset)['items']


def selectall(databasename: str, tablename: str, *, limit=DEFAULT_LIMIT, offset=0) -> list[dict]:
    return read_page(databasename, tablename, limit=limit, offset=offset)['items']
