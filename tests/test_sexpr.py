from nagra.sexpr import AST, Env
from nagra import Table


def test_sexpr():
    # Simple dot reference
    expr = "ham.spam"
    ast = AST.parse(expr)
    assert str(ast.tokens) == "[<VarToken ham.spam>]"

    # With int literal
    expr = "(= ham.spam 1)"
    ast = AST.parse(expr)
    assert str(ast.tokens) == "[<BuiltinToken =>, <VarToken ham.spam>, <IntToken 1>]"

    # With string literal
    expr = "(= ham.spam 'one')"
    ast = AST.parse(expr)
    assert str(ast.tokens) == "[<BuiltinToken =>, <VarToken ham.spam>, <StrToken one>]"

    # With placeholder
    expr = "(= ham.spam {})"
    ast = AST.parse(expr)
    assert str(ast.tokens) == "[<BuiltinToken =>, <VarToken ham.spam>, <ParamToken >]"


def test_find_relations():
    expr = "(= ham.spam foo.bar)"
    ast = AST.parse(expr)
    assert list(ast.relations()) == ["ham.spam", "foo.bar"]


def test_simple_eval():
    table = Table("spam", {"a": "bool"})
    expr = "a"
    ast = AST.parse(expr)
    env = Env(table)
    assert ast.eval(env) == '"spam"."a"'

    expr = "(= a 1)"
    ast = AST.parse(expr)
    env = Env(table)
    assert ast.eval(env) == '"spam"."a" = 1'

    expr = "(= a (= 1 1))"
    ast = AST.parse(expr)
    env = Env(table)
    assert ast.eval(env) == '"spam"."a" = (1 = 1)'


def test_join_eval():
    table = Table(
        "person",
        columns={
            "name": "varchar",
            "parent": "int",
        },
        foreign_keys={
            "parent": "person",
        },
        natural_key=["name"],
    )

    # Unique  join
    env = Env(table=table)
    expr = "(and (= parent.name 'Roger')"
    ast = AST.parse(expr)
    res = ast.eval(env)
    assert env.refs == {
        ("parent",): "parent_0",
    }
    assert res == """("parent_0"."name" = 'Roger')"""

    # Double join with two different depth
    env = Env(table=table)
    expr = "(and (= parent.name 'Roger') (= parent.parent.name 'George')"
    ast = AST.parse(expr)
    res = ast.eval(env)
    assert env.refs == {
        ("parent",): "parent_0",
        ("parent", "parent"): "parent_1",
    }
    assert res == """("parent_0"."name" = 'Roger') AND ("parent_1"."name" = 'George')"""

    # Double join with same depth
    env = Env(table=table)
    expr = "(and (= parent.name 'Roger') (= parent.id 1)"
    ast = AST.parse(expr)
    res = ast.eval(env)
    assert env.refs == {
        ("parent",): "parent_0",
    }
    assert res == """("parent_0"."name" = 'Roger') AND ("parent_0"."id" = 1)"""
