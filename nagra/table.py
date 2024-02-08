from functools import lru_cache
from typing import Dict, List

from nagra import execute
from nagra.schema import Schema
from nagra.delete import Delete
from nagra.select import Select
from nagra.upsert import Upsert
from nagra.transaction import Transaction


_SQLITE_TYPE_MAP = {
    "varchar": "text",
    "int": "integer",
}



class Table:
    def __init__(
        self,
        name: str,
        columns: Dict,
        natural_key: List = None,
        foreign_keys: Dict = None,
    ):
        self.name = name
        self.columns = columns
        self.natural_key = natural_key or list(columns)
        self.foreign_keys = foreign_keys or {}
        self.schema = Schema.default
        self.schema.add(self.name, self)

    @classmethod
    def get(self, name):
        """
        Shortcut method to Schema.default().get()
        """
        return Schema.default.get(name)

    def select(self, *columns, where=None):
        if not columns:
            columns = list(self.default_columns())
        slct = Select(self, *columns)
        if where:
            slct.where(where)
        return slct

    def join(self, env):
        for prefix, alias in env.refs.items():
            # Find alias of previous join in the chain
            *head, tail = prefix
            prev_table = env.refs[tuple(head)] if head else self.name
            # Identify last table & column of the chain
            ftable, join_col = self.join_on(prefix)
            yield (ftable.name, alias, prev_table, join_col)

    def default_columns(self, nk_only=False):
        columns = self.natural_key if nk_only else self.columns
        for column in columns:
            if column not in self.foreign_keys:
                yield column
                continue

            ftable = self.schema.get(self.foreign_keys[column])
            yield from (f"{column}.{k}" for k in ftable.default_columns(nk_only=True))

    @lru_cache
    def join_on(self, path):
        if len(path) == 1:
            join_col = path[0]
            table = self
            ftable = self.schema.get(self.foreign_keys[join_col])
            return ftable, join_col
        ftable, _ = self.join_on(path[:-1])
        table = ftable
        join_col = path[-1]
        ftable = self.schema.get(table.foreign_keys[join_col])
        return ftable, join_col

    def delete(self, where=None):
        delete = Delete(self)
        if where:
            delete.where(where)
        return delete

    def upsert(self, *columns):
        return Upsert(self, *columns)

    def insert(self, *columns):
        """
        Provide an insert-only statement (won't raise error if
        record already exists)
        """
        return Upsert(self, *columns).insert_only()

    def suggest(self, column, like=None):
        """
        Return a iterator over the possible values of columns. Use
        like in a where condition if given.
        """
        if "." not in column:
            raise NotImplementedError("TODO")
        local_col, remote_col = column.split(".", 1)
        cond = []
        if like:
            cond.append("(like " + remote_col + " {})")

        ftable = Schema.get(self.foreign_keys[local_col])
        select = ftable.select(remote_col).where(*cond)  # TODO group by remote_col!
        # TODO sort results
        if like:
            cur = execute(select.stm(), (like,))
            return (x for x, in cur)
        return (x for x, in select)

    def ctypes(self):
        if Transaction.flavor == "sqlite":
            return {
                c: _SQLITE_TYPE_MAP.get(d, d) for c, d in self.columns.items()
            }
        return self.columns
