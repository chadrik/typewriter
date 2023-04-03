""" Test suite for the code in fixer_utils """

# Local imports
from lib2to3.fixer_util import Attr, Call, Comma, Name, is_import, syms
from lib2to3.pgen2 import token
from lib2to3.pytree import Leaf, Node
from lib2to3.tests.support import TestCase
from lib2to3.tests.test_util import parse
from typing import NamedTuple

from .. import fixer_utils


def _to_binding(node, type):
    if node.type == type:
        return node
    if node.type == token.NAME:
        return None
    for child in node.children:
        if child.type == type:
            return child
        res = _to_binding(child, type)
        if res is not None and res.type == type:
            return res


class Test_get_import_info(TestCase):
    def get_import_info(self, string):
        node = parse(string)
        for type in [syms.import_name, syms.import_from]:
            n = _to_binding(node, type)
            if n is not None:
                node = n
                break
        return fixer_utils.get_import_info(node)

    def test(self):
        passing_tests = (({'': [('b', 'b')]}, "import b"),
                         ({'': [('b', 'c')]}, "import b as c"),
                         ({"a": [('b', 'a.b')]}, "import a.b"),
                         ({"a.b": [('c', 'a.b.c')]}, "import a.b.c"),
                         ({"a": [('b', 'c')]}, "import a.b as c"),
                         ({"a.x": [('b', 'c')]}, "import a.x.b as c"),
                         ({"a": [('b', 'b')]}, "from a import b"),
                         ({"a": [('b', 'b'), ('c', 'c'), ('d', 'd')]}, "from a import b, c, d"),
                         ({"a": [('b', 'b'), ('c', 'c'), ('d', 'd')]}, "from a import (b, c, d)"),
                         ({"a": [('b', 'b'), ('c', 'c'), ('d', 'd')]}, "from a import (b,\nc,\nd)"),
                         ({"a": [('b', 'c')]}, "from a import b as c"),
                         ({"a.x": [('b', 'b')]}, "from a.x import b"),
                         ({"a.x": [('b', 'c')]}, "from a.x import b as c"),
                         ({"a": [('b', 'a.b')], "x": [('c', 'x.c')], "y": [('d', 'y.d')]},
                          "import a.b, x.c, y.d"),
                         ({"typing": [('Any', 'Any'), ('Callable', 'Callable'),
                                      ('Deque', 'Deque'), ('Generic', 'Generic'),
                                      ('Iterable', 'Iterable'), ('Iterator', 'Iterator'),
                                      ('List', 'List'), ('Optional', 'Optional'),
                                      ('Tuple', 'Tuple'), ('TypeVar', 'TypeVar'),
                                      ('Union', 'Union'), ('overload', 'overload')]},
                          """from typing import (Any, Callable, Deque, Generic, Iterable, Iterator, List,
                                                 Optional, Tuple, TypeVar, Union, overload)"""))

        for imports, stmt in passing_tests:
            print(stmt)
            n = self.get_import_info(stmt)
            self.assertTrue(n.imports)
            for key in imports.keys():
                self.assertTrue(n.imports.get(key))
                ref = set(imports.get(key))
                res = n.imports.get(key)
                self.assertTrue(ref == res)


class Test_find_import_info(TestCase):
    def find_import_info(self, package, name, string):
        node = parse(string)
        return fixer_utils.find_import_info(package, name, node)

    def test(self):
        package, name, binding, string = ('mod2', 'AnotherClass', 'bar',
                                          """
                                          # Attempt to disguise as mod2.AnotherClass - before real import
                                          import something as AnotherClass
                                          import AnotherClass
                                          import AnotherClass as other
                                          import mod3.AnotherClass
                                          import mod3.AnotherClass as thing
                                          import mod2.stuff as AnotherClass
                                          import mod3.mod2.AnotherClass
                                          import mod3.mod2.AnotherClass as ox
                                          import mod3.mod2.dingo as AnotherClass
                                          from something import geese as AnotherClass
                                          from AnotherClass import goober
                                          from AnotherClass import goober as gobble
                                          from mod3 import AnotherClass
                                          from mod3 import AnotherClass as bucket
                                          from mod2 import stuff as AnotherClass
                                          from mod3.mod2 import AnotherClass
                                          from mod3.mod2 import AnotherClass as trex
                                          from mod3.mod2 import dingo as AnotherClass

                                          # real import
                                          import mod2.AnotherClass as bar

                                          # Attempt to disguise as mod2.AnotherClass - after real import
                                          import something2 as AnotherClass
                                          import AnotherClass
                                          import AnotherClass as other2
                                          import mod4.AnotherClass
                                          import mod4.AnotherClass as thing2
                                          import mod2.stuff2 as AnotherClass
                                          import mod4.mod2.AnotherClass
                                          import mod4.mod2.AnotherClass as ox2
                                          import mod4.mod2.dingo2 as AnotherClass
                                          from something2 import geese2 as AnotherClass
                                          from AnotherClass import goober2
                                          from AnotherClass import goober2 as gobble2
                                          from mod4 import AnotherClass
                                          from mod4 import AnotherClass as bucket2
                                          from mod4 import stuff2 as AnotherClass
                                          from mod4.mod2 import AnotherClass
                                          from mod4.mod2 import AnotherClass as trex2
                                          from mod4.mod2 import dingo2 as AnotherClass""")

        res = self.find_import_info(package, name, string)
        self.assertTrue(res)
        self.assertTrue(res.package == package)
        self.assertTrue(res.entry == name)
        self.assertTrue(res.binding == binding)


class Test_create_type_checking_import(TestCase):
    def create_type_checking_import(self, package, name, string):
        node = parse(string)
        fixer_utils.create_type_checking_import(package, name, node)
        return node

    def test(self):
        string = """
        import a
        import b.a as c
        import c.d as e
        from X import Y

        import Z as W

        import typing.TYPE_CHECKING
        if typing.TYPE_CHECKING:
            from bar import R
            from bar import S
            from bar import T

        import mod as bar
        import foo
        from foo.mod2 import MyClass
        """

        ref = """
        import a
        import b.a as c
        import c.d as e
        from X import Y

        import Z as W

        import typing.TYPE_CHECKING
        if typing.TYPE_CHECKING:
            from bar import R
            from bar import S
            from bar import T
            from bar import TestImport

        import mod as bar
        import foo
        from foo.mod2 import MyClass
        """
        ref = parse(ref)

        res = self.create_type_checking_import("bar", "TestImport", string)
        self.assertTrue(res)
        self.assertTrue(res == ref)
