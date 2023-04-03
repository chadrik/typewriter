# flake8: noqa
# Our flake extension misfires on type comments in strings below.

from lib2to3.tests.test_fixers import FixerTestCase


class AnnotateFromSignatureTestCase(FixerTestCase):

    def setTestData(self, data):
        raise NotImplementedError

    def test_basic(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 3,
              "signature": {
                  "arg_types": ["Foo", "Bar"],
                  "return_type": "Any"},
              }])
        a = """\
            class Foo: pass
            class Bar: pass
            def nop(foo, bar):
                return 42
            """
        b = """\
            from typing import Any
            class Foo: pass
            class Bar: pass
            def nop(foo, bar):
                # type: (Foo, Bar) -> Any
                return 42
            """
        self.check(a, b)

    def test_decorator_func(self):
        self.setTestData(
            [{"func_name": "foo",
              "path": "<string>",
              "line": 2,
              "signature": {
                  "arg_types": [],
                  "return_type": "int"},
              }])
        a = """\
            @dec
            def foo():
                return 42
            """
        b = """\
            @dec
            def foo():
                # type: () -> int
                return 42
            """
        self.check(a, b)

    def test_decorator_method(self):
        self.setTestData(
            [{"func_name": "Bar.foo",
              "path": "<string>",
              "line": 3,
              "signature": {
                  "arg_types": [],
                  "return_type": "int"},
              }])
        a = """\
            class Bar:
                @dec
                @dec2
                def foo(self):
                    return 42
            """
        b = """\
            class Bar:
                @dec
                @dec2
                def foo(self):
                    # type: () -> int
                    return 42
            """
        self.check(a, b)

    def test_nested_class_func(self):
        self.setTestData(
            [{"func_name": "A.B.foo",
              "path": "<string>",
              "line": 3,
              "signature": {
                  "arg_types": ['str'],
                  "return_type": "int"},
              }])
        a = """\
            class A:
                class B:
                    def foo(x):
                        return 42
            """
        b = """\
            class A:
                class B:
                    def foo(x):
                        # type: (str) -> int
                        return 42
            """
        self.check(a, b)

    def test_nested_func(self):
        self.setTestData(
            [{"func_name": "A.foo.bar",
              "path": "<string>",
              "line": 3,
              "signature": {
                  "arg_types": [],
                  "return_type": "int"},
              }])
        a = """\
            class A:
                def foo():
                    def bar():
                        return 42
            """
        b = """\
            class A:
                def foo():
                    def bar():
                        # type: () -> int
                        return 42
            """
        self.check(a, b)

    def test_keyword_only_argument(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 3,
              "signature": {
                  "arg_types": ["Foo", "Bar"],
                  "return_type": "Any"},
              }])
        a = """\
            class Foo: pass
            class Bar: pass
            def nop(foo, *, bar):
                return 42
            """
        b = """\
            from typing import Any
            class Foo: pass
            class Bar: pass
            def nop(foo, *, bar):
                # type: (Foo, Bar) -> Any
                return 42
            """
        self.check(a, b)

    def test_add_typing_import(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              # Check with and without 'typing.' prefix
              "signature": {
                  "arg_types": ["List[typing.AnyStr]", "Callable[[], int]"],
                  "return_type": "object"},
              }])
        a = """\
            def nop(foo, bar):
                return 42
            """
        b = """\
            from typing import AnyStr
            from typing import Callable
            from typing import List
            def nop(foo, bar):
                # type: (List[AnyStr], Callable[[], int]) -> object
                return 42
            """
        self.check(a, b)

    def test_typing_import_parens(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              # Check with and without 'typing.' prefix
              "signature": {
                  "arg_types": ["List[typing.AnyStr]", "Callable[[], int]"],
                  "return_type": "object"},
              }])
        a = """\
            from typing import (AnyStr, Callable, List)
            def nop(foo, bar):
                return 42
            """
        b = """\
            from typing import (AnyStr, Callable, List)
            def nop(foo, bar):
                # type: (List[AnyStr], Callable[[], int]) -> object
                return 42
            """
        self.check(a, b)

    def test_add_other_import(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "mod1.py",
              "line": 1,
              "signature": {
                  "arg_types": ["mod1.MyClass", "mod2.OtherClass"],
                  "return_type": "mod3.AnotherClass"},
              }])
        a = """\
            from mod3 import AnotherClass
            def nop(foo, bar):
                return AnotherClass()
            class MyClass: pass
            """
        b = """\
            from mod3 import AnotherClass
            from typing import TYPE_CHECKING
            if TYPE_CHECKING:
                from mod2 import OtherClass
            def nop(foo, bar):
                # type: (MyClass, OtherClass) -> AnotherClass
                return AnotherClass()
            class MyClass: pass
            """
        self.check(a, b)

    def test_add_other_import_safe(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "mod1.py",
              "line": 1,
              "signature": {
                  "arg_types": ["mod1.MyClass", "mod3.OtherClass"],
                  "return_type": "mod3.AnotherClass"},
              }])
        a = """\
            from mod3 import AnotherClass
            def nop(foo, bar):
                return AnotherClass()
            class MyClass: pass
            """
        b = """\
            from mod3 import AnotherClass
            from mod3 import OtherClass
            def nop(foo, bar):
                # type: (MyClass, OtherClass) -> AnotherClass
                return AnotherClass()
            class MyClass: pass
            """
        self.check(a, b)

    def test_type_by_import(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "mod1.py",
              "line": 1,
              "signature": {
                  "arg_types": ["mod1.MyClass"],
                  "return_type": "mod2.AnotherClass"},
              }])
        a = """\
            import mod2
            def nop(foo):
                return mod2.AnotherClass()
            class MyClass: pass
            """
        b = """\
            import mod2
            def nop(foo):
                # type: (MyClass) -> mod2.AnotherClass
                return mod2.AnotherClass()
            class MyClass: pass
            """
        self.check(a, b)

    def test_type_by_mod_import_as(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "mod1.py",
              "line": 1,
              "signature": {
                  "arg_types": ["mod1.MyClass"],
                  "return_type": "mod2.AnotherClass"},
              }])
        a = """\
            import mod2 as bar
            def nop(foo):
                return bar.AnotherClass()
            class MyClass: pass
            """
        b = """\
            import mod2 as bar
            def nop(foo):
                # type: (MyClass) -> bar.AnotherClass
                return bar.AnotherClass()
            class MyClass: pass
            """
        self.check(a, b)

    def test_type_by_dotted_import_as(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "mod1.py",
              "line": 1,
              "signature": {
                  "arg_types": ["mod1.MyClass"],
                  "return_type": "pkg.mod2.AnotherClass"},
              }])
        a = """\
            import pkg.mod2.AnotherClass as bar
            def nop(foo):
                return bar()
            class MyClass: pass
            """
        b = """\
            import pkg.mod2.AnotherClass as bar
            def nop(foo):
                # type: (MyClass) -> bar
                return bar()
            class MyClass: pass
            """
        self.check(a, b)

    def test_type_by_dotted_import_mod_as(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "mod1.py",
              "line": 1,
              "signature": {
                  "arg_types": ["mod1.MyClass"],
                  "return_type": "pkg.mod2.AnotherClass"},
              }])
        a = """\
            import pkg.mod2 as bar
            def nop(foo):
                return bar.AnotherClass()
            class MyClass: pass
            """
        b = """\
            import pkg.mod2 as bar
            def nop(foo):
                # type: (MyClass) -> bar.AnotherClass
                return bar.AnotherClass()
            class MyClass: pass
            """
        self.check(a, b)

    def test_type_by_import_as(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "mod1.py",
              "line": 1,
              "signature": {
                  "arg_types": ["mod1.MyClass"],
                  "return_type": "mod2.AnotherClass"},
              }])
        a = """\
            from mod2 import AnotherClass as bar
            def nop(foo):
                return bar()
            class MyClass: pass
            """
        b = """\
            from mod2 import AnotherClass as bar
            def nop(foo):
                # type: (MyClass) -> bar
                return bar()
            class MyClass: pass
            """
        self.check(a, b)

    def test_type_by_from_import_as_with_dotted_package(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "mod1.py",
              "line": 1,
              "signature": {
                  "arg_types": ["mod1.MyClass"],
                  "return_type": "pkg.mod2.AnotherClass"},
              }])
        a = """\
            from pkg.mod2 import AnotherClass as bar
            def nop(foo):
                return bar()
            class MyClass: pass
            """
        b = """\
            from pkg.mod2 import AnotherClass as bar
            def nop(foo):
                # type: (MyClass) -> bar
                return bar()
            class MyClass: pass
            """
        self.check(a, b)

    def test_parentheses_import(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "mod1.py",
              "line": 1,
              "signature": {
                  "arg_types": ["mod2.MyClass"],
                  "return_type": "mod2.AnotherClass"},
              }])
        a = """\
            from mod2 import (AnotherClass,
                              MyClass)
            def nop(foo):
                return AnotherClass()
            class MyClass: pass
            """
        b = """\
            from mod2 import (AnotherClass,
                              MyClass)
            def nop(foo):
                # type: (MyClass) -> AnotherClass
                return AnotherClass()
            class MyClass: pass
            """
        self.check(a, b)

    def test_type_checking_import(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "mod1.py",
              "line": 1,
              "signature": {
                  "arg_types": ["mod2.MyClass"],
                  "return_type": "mod3.AnotherClass"},
              }])
        a = """\
            from mod3 import AnotherClass
            from typing import TYPE_CHECKING
            if TYPE_CHECKING:
                import X
            def nop(foo):
                return AnotherClass()
            class MyClass: pass
            """
        b = """\
            from mod3 import AnotherClass
            from typing import TYPE_CHECKING
            if TYPE_CHECKING:
                import X
                from mod2 import MyClass
            def nop(foo):
                # type: (MyClass) -> AnotherClass
                return AnotherClass()
            class MyClass: pass
            """
        self.check(a, b)

    def test_type_checking_from_import(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "mod1.py",
              "line": 1,
              "signature": {
                  "arg_types": ["mod2.MyClass"],
                  "return_type": "mod3.AnotherClass"},
              }])
        a = """\
            from mod3 import AnotherClass
            from typing import TYPE_CHECKING
            if TYPE_CHECKING:
                import X
            def nop(foo):
                return AnotherClass()
            class MyClass: pass
            """
        b = """\
            from mod3 import AnotherClass
            from typing import TYPE_CHECKING
            if TYPE_CHECKING:
                import X
                from mod2 import MyClass
            def nop(foo):
                # type: (MyClass) -> AnotherClass
                return AnotherClass()
            class MyClass: pass
            """
        self.check(a, b)

    def test_add_kwds(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": ["int"],
                  "return_type": "object"},
              }])
        a = """\
            def nop(foo, **kwds):
                return 42
            """
        b = """\
            from typing import Any
            def nop(foo, **kwds):
                # type: (int, **Any) -> object
                return 42
            """
        self.check(a, b)

    def test_dont_add_kwds(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": ["int", "**AnyStr"],
                  "return_type": "object"},
              }])
        a = """\
            def nop(foo, **kwds):
                return 42
            """
        b = """\
            from typing import AnyStr
            def nop(foo, **kwds):
                # type: (int, **AnyStr) -> object
                return 42
            """
        self.check(a, b)

    def test_add_varargs(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": ["int"],
                  "return_type": "object"},
              }])
        a = """\
            def nop(foo, *args):
                return 42
            """
        b = """\
            from typing import Any
            def nop(foo, *args):
                # type: (int, *Any) -> object
                return 42
            """
        self.check(a, b)

    def test_dont_add_varargs(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": ["int", "*int"],
                  "return_type": "object"},
              }])
        a = """\
            def nop(foo, *args):
                return 42
            """
        b = """\
            def nop(foo, *args):
                # type: (int, *int) -> object
                return 42
            """
        self.check(a, b)

    def test_return_expr_not_none(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": [],
                  "return_type": "None"},
              }])
        a = """\
            def nop():
                return 0
            """
        b = """\
            from typing import Any
            from typing import Optional
            def nop():
                # type: () -> Optional[Any]
                return 0
            """
        self.check(a, b)

    def test_return_expr_none(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": [],
                  "return_type": "None"},
              }])
        a = """\
            def nop():
                return
            """
        b = """\
            def nop():
                # type: () -> None
                return
            """
        self.check(a, b)

    def test_generator_optional(self):
        self.setTestData(
            [{"func_name": "gen",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": [],
                  "return_type": "Optional[int]"},
              }])
        a = """\
            def gen():
                yield 42
            """
        b = """\
            from typing import Iterator
            def gen():
                # type: () -> Iterator[int]
                yield 42
            """
        self.check(a, b)

    def test_generator_plain(self):
        self.setTestData(
            [{"func_name": "gen",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": [],
                  "return_type": "int"},
              }])
        a = """\
            def gen():
                yield 42
            """
        b = """\
            from typing import Iterator
            def gen():
                # type: () -> Iterator[int]
                yield 42
            """
        self.check(a, b)

    def test_not_generator(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": [],
                  "return_type": "int"},
              }])
        a = """\
            def nop():
                def gen():
                    yield 42
            """
        b = """\
            def nop():
                # type: () -> int
                def gen():
                    yield 42
            """
        self.check(a, b)

    def test_add_self(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": [],
                  "return_type": "int"},
              }])
        a = """\
            def nop(self):
                pass
            """
        b = """\
            from typing import Any
            def nop(self):
                # type: (Any) -> int
                pass
            """
        self.check(a, b)

    def test_dont_add_self(self):
        self.setTestData(
            [{"func_name": "C.nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": [],
                  "return_type": "int"},
              }])
        a = """\
            class C:
                def nop(self):
                    pass
            """
        b = """\
            class C:
                def nop(self):
                    # type: () -> int
                    pass
            """
        self.check(a, b)

    def test_too_many_types(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": ["int"],
                  "return_type": "int"},
              }])
        a = """\
            def nop():
                pass
            """
        self.warns(a, a, "source has 0 args, annotation has 1 -- skipping", unchanged=True)

    def test_too_few_types(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": [],
                  "return_type": "int"},
              }])
        a = """\
            def nop(a):
                pass
            """
        self.warns(a, a, "source has 1 args, annotation has 0 -- skipping", unchanged=True)

    def test_classmethod(self):
        # Class methods need to work without a class name
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 3,
              "signature": {
                  "arg_types": ["int"],
                  "return_type": "int"}
              }])
        a = """\
            class C:
                @classmethod
                def nop(cls, a):
                    return a
            """
        b = """\
            class C:
                @classmethod
                def nop(cls, a):
                    # type: (int) -> int
                    return a
            """
        self.check(a, b)

    def test_classmethod_named(self):
        # Class methods also should work *with* a class name
        self.setTestData(
            [{"func_name": "C.nop",
              "path": "<string>",
              "line": 3,
              "signature": {
                  "arg_types": ["int"],
                  "return_type": "int"}
              }])
        a = """\
            class C:
                @classmethod
                def nop(cls, a):
                    return a
            """
        b = """\
            class C:
                @classmethod
                def nop(cls, a):
                    # type: (int) -> int
                    return a
            """
        self.check(a, b)

    def test_staticmethod(self):
        # Static methods need to work without a class name
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 3,
              "signature": {
                  "arg_types": ["int"],
                  "return_type": "int"}
              }])
        a = """\
            class C:
                @staticmethod
                def nop(a):
                    return a
            """
        b = """\
            class C:
                @staticmethod
                def nop(a):
                    # type: (int) -> int
                    return a
            """
        self.check(a, b)

    def test_staticmethod_named(self):
        # Static methods also should work *with* a class name
        self.setTestData(
            [{"func_name": "C.nop",
              "path": "<string>",
              "line": 3,
              "signature": {
                  "arg_types": ["int"],
                  "return_type": "int"}
              }])
        a = """\
            class C:
                @staticmethod
                def nop(a):
                    return a
            """
        b = """\
            class C:
                @staticmethod
                def nop(a):
                    # type: (int) -> int
                    return a
            """
        self.check(a, b)

    def test_long_form(self):
        self.maxDiff = None
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": ["int", "int", "int",
                                "str", "str", "str",
                                "Optional[bool]", "Union[int, str]", "*Any"],
                  "return_type": "int"},
              }])
        a = """\
            def nop(a, b, c,  # some comment
                    d, e, f,  # multi-line
                              # comment
                    g=None, h=0, *args):
                return 0
            """
        b = """\
            from typing import Any
            from typing import Optional
            from typing import Union
            def nop(a,  # type: int
                    b,  # type: int
                    c,  # type: int  # some comment
                    d,  # type: str
                    e,  # type: str
                    f,  # type: str  # multi-line
                              # comment
                    g=None,  # type: Optional[bool]
                    h=0,  # type: Union[int, str]
                    *args  # type: Any
                    ):
                # type: (...) -> int
                return 0
            """
        self.check(a, b)

    def test_long_form_method(self):
        self.maxDiff = None
        self.setTestData(
            [{"func_name": "C.nop",
              "path": "<string>",
              "line": 2,
              "signature": {
                  "arg_types": ["int", "int", "int",
                                "str", "str", "str",
                                "Optional[bool]", "Union[int, str]", "*Any"],
                  "return_type": "int"},
              }])
        a = """\
            class C:
                def nop(self, a, b, c,  # some comment
                              d, e, f,  # multi-line
                                        # comment
                              g=None, h=0, *args):
                    return 0
            """
        b = """\
            from typing import Any
            from typing import Optional
            from typing import Union
            class C:
                def nop(self,
                        a,  # type: int
                        b,  # type: int
                        c,  # type: int  # some comment
                        d,  # type: str
                        e,  # type: str
                        f,  # type: str  # multi-line
                                        # comment
                        g=None,  # type: Optional[bool]
                        h=0,  # type: Union[int, str]
                        *args  # type: Any
                        ):
                    # type: (...) -> int
                    return 0
            """
        self.check(a, b)

    def test_long_form_classmethod(self):
        self.maxDiff = None
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 3,
              "signature": {
                  "arg_types": ["int", "int", "int",
                                "str", "str", "str",
                                "Optional[bool]", "Union[int, str]", "*Any"],
                  "return_type": "int"},
              }])
        a = """\
            class C:
                @classmethod
                def nop(cls, a, b, c,  # some comment
                        d, e, f,
                        g=None, h=0, *args):
                    return 0
            """
        b = """\
            from typing import Any
            from typing import Optional
            from typing import Union
            class C:
                @classmethod
                def nop(cls,
                        a,  # type: int
                        b,  # type: int
                        c,  # type: int  # some comment
                        d,  # type: str
                        e,  # type: str
                        f,  # type: str
                        g=None,  # type: Optional[bool]
                        h=0,  # type: Union[int, str]
                        *args  # type: Any
                        ):
                    # type: (...) -> int
                    return 0
            """
        self.check(a, b)
        # Do the same test for staticmethod
        a = a.replace('classmethod', 'staticmethod')
        b = b.replace('classmethod', 'staticmethod')
        self.check(a, b)

    def test_long_form_trailing_comma(self):
        self.maxDiff = None
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 3,
              "signature": {
                  "arg_types": ["int", "int", "int",
                                "str", "str", "str",
                                "Optional[bool]", "Union[int, str]"],
                  "return_type": "int"},
              }])
        a = """\
            def nop(a, b, c,  # some comment
                    d, e, f,
                    g=None, h=0):
                return 0
            """
        b = """\
            from typing import Optional
            from typing import Union
            def nop(a,  # type: int
                    b,  # type: int
                    c,  # type: int  # some comment
                    d,  # type: str
                    e,  # type: str
                    f,  # type: str
                    g=None,  # type: Optional[bool]
                    h=0,  # type: Union[int, str]
                    ):
                # type: (...) -> int
                return 0
            """
        self.check(a, b)

    def test_one_liner(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": ["int"],
                  "return_type": "int"},
              }])
        a = """\
            def nop(a):   return a
            """
        b = """\
            def nop(a):
                # type: (int) -> int
                return a
            """
        self.check(a, b)

    def test_variadic(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": ["Tuple[int, ...]"],
                  "return_type": "int"},
              }])
        a = """\
            def nop(a):   return 0
            """
        b = """\
            from typing import Tuple
            def nop(a):
                # type: (Tuple[int, ...]) -> int
                return 0
            """
        self.check(a, b)

    def test_nested(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 1,
              "signature": {
                  "arg_types": ["foo:A.B"],
                  "return_type": "None"},
              }])
        a = """\
            def nop(a):
                pass
            """
        b = """\
            from typing import TYPE_CHECKING
            if TYPE_CHECKING:
                from foo import A
            def nop(a):
                # type: (A.B) -> None
                pass
            """
        self.check(a, b)
