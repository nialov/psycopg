from enum import Enum, auto

import pytest

from psycopg import pq, sql
from psycopg.adapt import PyFormat
from psycopg.types import TypeInfo
from psycopg.types.enum import EnumInfo, register_enum


class PureTestEnum(Enum):
    FOO = auto()
    BAR = auto()
    BAZ = auto()


class StrTestEnum(str, Enum):
    ONE = "ONE"
    TWO = "TWO"
    THREE = "THREE"


NonAsciiEnum = Enum(
    "NonAsciiEnum", {"X\xe0": "x\xe0", "X\xe1": "x\xe1", "COMMA": "foo,bar"}, type=str
)


class IntTestEnum(int, Enum):
    ONE = 1
    TWO = 2
    THREE = 3


enum_cases = [PureTestEnum, StrTestEnum, NonAsciiEnum, IntTestEnum]

encodings = ["utf8", "latin1"]


@pytest.fixture(scope="session", params=enum_cases)
def testenum(request, svcconn):
    enum = request.param
    name = enum.__name__.lower()
    labels = list(enum.__members__.keys())
    cur = svcconn.cursor()
    cur.execute(
        sql.SQL(
            """
            drop type if exists {name} cascade;
            create type {name} as enum ({labels});
            """
        ).format(name=sql.Identifier(name), labels=sql.SQL(",").join(labels))
    )
    return name, enum, labels


def test_fetch_info(conn, testenum):
    name, enum, labels = testenum

    info = EnumInfo.fetch(conn, name)
    assert info.name == name
    assert info.oid > 0
    assert info.oid != info.array_oid > 0
    assert len(info.labels) == len(labels)
    assert info.labels == labels


def test_register_makes_a_type(conn, testenum):
    name, enum, labels = testenum
    info = EnumInfo.fetch(conn, name)
    assert info
    assert info.enum is None
    register_enum(info, context=conn)
    assert info.enum is not None
    assert [e.name for e in info.enum] == [e.name for e in enum]


@pytest.mark.parametrize("encoding", encodings)
@pytest.mark.parametrize("fmt_in", PyFormat)
@pytest.mark.parametrize("fmt_out", pq.Format)
def test_enum_loader(conn, testenum, encoding, fmt_in, fmt_out):
    conn.execute(f"set client_encoding to {encoding}")

    name, enum, labels = testenum
    register_enum(EnumInfo.fetch(conn, name), enum, conn)

    for label in labels:
        cur = conn.execute(f"select %{fmt_in}::{name}", [label], binary=fmt_out)
        assert cur.fetchone()[0] == enum[label]


@pytest.mark.parametrize("fmt_in", PyFormat)
@pytest.mark.parametrize("fmt_out", pq.Format)
def test_enum_loader_sqlascii(conn, testenum, fmt_in, fmt_out):
    name, enum, labels = testenum
    if name == "nonasciienum":
        pytest.skip("ascii-only test")

    register_enum(EnumInfo.fetch(conn, name), enum, conn)
    conn.execute("set client_encoding to sql_ascii")

    for label in labels:
        cur = conn.execute(f"select %{fmt_in}::{name}", [label], binary=fmt_out)
        assert cur.fetchone()[0] == enum[label]


@pytest.mark.parametrize("encoding", encodings)
@pytest.mark.parametrize("fmt_in", PyFormat)
@pytest.mark.parametrize("fmt_out", pq.Format)
def test_enum_dumper(conn, testenum, encoding, fmt_in, fmt_out):
    conn.execute(f"set client_encoding to {encoding}")

    name, enum, labels = testenum
    register_enum(EnumInfo.fetch(conn, name), enum, conn)

    for item in enum:
        cur = conn.execute(f"select %{fmt_in}", [item], binary=fmt_out)
        assert cur.fetchone()[0] == item


@pytest.mark.parametrize("fmt_in", PyFormat)
@pytest.mark.parametrize("fmt_out", pq.Format)
def test_enum_dumper_sqlascii(conn, testenum, fmt_in, fmt_out):
    name, enum, labels = testenum
    if name == "nonasciienum":
        pytest.skip("ascii-only test")

    register_enum(EnumInfo.fetch(conn, name), enum, conn)
    conn.execute("set client_encoding to sql_ascii")

    for item in enum:
        cur = conn.execute(f"select %{fmt_in}", [item], binary=fmt_out)
        assert cur.fetchone()[0] == item


@pytest.mark.parametrize("encoding", encodings)
@pytest.mark.parametrize("fmt_in", PyFormat)
@pytest.mark.parametrize("fmt_out", pq.Format)
def test_generic_enum_dumper(conn, testenum, encoding, fmt_in, fmt_out):
    conn.execute(f"set client_encoding to {encoding}")

    name, enum, labels = testenum

    for item in enum:
        if enum is PureTestEnum:
            want = item.name
        else:
            want = item.value

        cur = conn.execute(f"select %{fmt_in}", [item], binary=fmt_out)
        assert cur.fetchone()[0] == want


@pytest.mark.parametrize("encoding", encodings)
@pytest.mark.parametrize("fmt_in", PyFormat)
@pytest.mark.parametrize("fmt_out", pq.Format)
def test_generic_enum_loader(conn, testenum, encoding, fmt_in, fmt_out):
    conn.execute(f"set client_encoding to {encoding}")

    name, enum, labels = testenum
    for label in labels:
        cur = conn.execute(f"select %{fmt_in}::{name}", [label], binary=fmt_out)
        want = enum[label].name
        if fmt_out == pq.Format.BINARY:
            want = want.encode(encoding)
        assert cur.fetchone()[0] == want


@pytest.mark.parametrize("encoding", encodings)
@pytest.mark.parametrize("fmt_in", PyFormat)
@pytest.mark.parametrize("fmt_out", pq.Format)
def test_enum_array_loader(conn, testenum, encoding, fmt_in, fmt_out):
    conn.execute(f"set client_encoding to {encoding}")

    name, enum, labels = testenum
    register_enum(EnumInfo.fetch(conn, name), enum, conn)

    cur = conn.execute(f"select %{fmt_in}::{name}[]", [labels], binary=fmt_out)
    assert cur.fetchone()[0] == list(enum)


@pytest.mark.parametrize("encoding", encodings)
@pytest.mark.parametrize("fmt_in", PyFormat)
@pytest.mark.parametrize("fmt_out", pq.Format)
def test_enum_array_dumper(conn, testenum, encoding, fmt_in, fmt_out):
    conn.execute(f"set client_encoding to {encoding}")

    name, enum, labels = testenum
    register_enum(EnumInfo.fetch(conn, name), enum, conn)

    cur = conn.execute(f"select %{fmt_in}", [list(enum)], binary=fmt_out)
    assert cur.fetchone()[0] == list(enum)


@pytest.mark.parametrize("encoding", encodings)
@pytest.mark.parametrize("fmt_in", PyFormat)
@pytest.mark.parametrize("fmt_out", pq.Format)
def test_generic_enum_array_loader(conn, testenum, encoding, fmt_in, fmt_out):
    conn.execute(f"set client_encoding to {encoding}")

    name, enum, labels = testenum
    info = TypeInfo.fetch(conn, name)
    info.register(conn)
    want = [member.name for member in enum]
    if fmt_out == pq.Format.BINARY:
        want = [item.encode(encoding) for item in want]
    cur = conn.execute(f"select %{fmt_in}::{name}[]", [labels], binary=fmt_out)
    assert cur.fetchone()[0] == want


@pytest.mark.asyncio
async def test_fetch_info_async(aconn, testenum):
    name, enum, labels = testenum

    info = await EnumInfo.fetch(aconn, name)
    assert info.name == name
    assert info.oid > 0
    assert info.oid != info.array_oid > 0
    assert len(info.labels) == len(labels)
    assert info.labels == labels


@pytest.mark.asyncio
@pytest.mark.parametrize("encoding", encodings)
@pytest.mark.parametrize("fmt_in", PyFormat)
@pytest.mark.parametrize("fmt_out", pq.Format)
async def test_enum_async(aconn, testenum, encoding, fmt_in, fmt_out):
    await aconn.execute(f"set client_encoding to {encoding}")

    name, enum, labels = testenum
    register_enum(await EnumInfo.fetch(aconn, name), enum, aconn)

    for label in labels:
        cur = await aconn.execute(f"select %{fmt_in}::{name}", [label], binary=fmt_out)
        assert (await cur.fetchone())[0] == enum[label]

    cur = await cur.execute(f"select %{fmt_in}", [list(enum)])
    assert (await cur.fetchone())[0] == list(enum)
