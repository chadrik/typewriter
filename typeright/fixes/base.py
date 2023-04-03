"""Fixer that inserts mypy annotations into all methods.

This transforms e.g.

  def foo(self, bar, baz=12):
      return bar + baz

into a type annoted version:

	  def foo(self, bar, baz=12):
	      # type: (Any, int) -> Any            # noqa: F821
	      return bar + baz

or (when setting options['typeright']['annotation_style'] to 'py3'):

	  def foo(self, bar : Any, baz : int = 12) -> Any:
	      return bar + baz


It does not do type inference but it recognizes some basic default
argument values such as numbers and strings (and assumes their type
implies the argument type).

It also uses some basic heuristics to decide whether to ignore the
first argument:

  - always if it's named 'self'
  - if there's a @classmethod decorator

Finally, it knows that __init__() is supposed to return None.
"""

from __future__ import print_function

import os
import re
from contextlib import contextmanager
from lib2to3.fixer_base import BaseFix
from lib2to3.fixer_util import (does_tree_import, find_indentation, syms,
                                touch_import)
from lib2to3.patcomp import compile_pattern
from lib2to3.pgen2 import token
from lib2to3.pytree import Base, Leaf, Node
from typing import (Any, Dict, Iterator, List, Match, Optional, Set, Text,
                    Tuple, Union)
from typing import __all__ as typing_all  # type: ignore

from typeright.fixes.fixer_utils import (create_import,
                                          create_type_checking_import,
                                          get_unprotected_imports,
                                          type_by_import_stmt)

# Taken from mypy codebase:
# https://github.com/python/mypy/blob/745d300b8304c3dcf601477762bf9d70b9a4619c/mypy/main.py#L503

PY_EXTENSIONS = ['.pyi', '.py']
TYPE_REG = re.compile('\s*#\s*type:.*')


def crawl_up(arg):
    # type: (str) -> Tuple[str, str]
    """Given a .py[i] filename, return (root directory, module).
    We crawl up the path until we find a directory without
    __init__.py[i], or until we run out of path components.
    """
    dir, mod = os.path.split(arg)
    mod = strip_py(mod) or mod
    while dir and get_init_file(dir):
        dir, base = os.path.split(dir)
        if not base:
            break
        if mod == '__init__' or not mod:
            mod = base
        else:
            mod = base + '.' + mod
    return dir, mod


def strip_py(arg):
    # type: (str) -> Optional[str]
    """Strip a trailing .py or .pyi suffix.
    Return None if no such suffix is found.
    """
    for ext in PY_EXTENSIONS:
        if arg.endswith(ext):
            return arg[:-len(ext)]
    return None


def get_init_file(dir):
    # type: (str) -> Optional[str]
    """Check whether a directory contains a file named __init__.py[i].
    If so, return the file's name (with dir prefixed).  If not, return
    None.
    This prefers .pyi over .py (because of the ordering of PY_EXTENSIONS).
    """
    for ext in PY_EXTENSIONS:
        f = os.path.join(dir, '__init__' + ext)
        if os.path.isfile(f):
            return f
    return None


def get_funcname(node):
    # type: (Optional[Union[Leaf, Node]]) -> Text
    """Get function name by (approximately) the following rules:

    - function -> function_name
    - method -> ClassName.function_name

    More specifically, we include every class and function name that
    the node is a child of, so nested classes and functions get names like
    OuterClass.InnerClass.outer_fn.inner_fn.
    """
    components = []  # type: List[str]
    while node:
        if node.type in (syms.classdef, syms.funcdef):
            name = node.children[1]
            assert name.type == token.NAME, repr(name)
            assert isinstance(name, Leaf)  # Same as previous, for mypy
            components.append(name.value)
        node = node.parent
    return '.'.join(reversed(components))


def count_args(node, results):
    # type: (Node, Dict[str, Base]) -> Tuple[int, bool, bool, bool]
    """Count arguments and check for self and *args, **kwds.

    Return (selfish, count, star, starstar) where:
    - count is total number of args (including *args, **kwds)
    - selfish is True if the initial arg is named 'self' or 'cls'
    - star is True iff *args is found
    - starstar is True iff **kwds is found
    """
    count = 0
    selfish = False
    star = False
    starstar = False
    args = results.get('args')
    if isinstance(args, Node):
        children = args.children
    elif isinstance(args, Leaf):
        children = [args]
    else:
        children = []
    # Interpret children according to the following grammar:
    # (('*'|'**')? NAME ['=' expr] ','?)*
    skip = False
    previous_token_is_star = False
    for child in children:
        if skip:
            skip = False
        elif isinstance(child, Leaf):
            # A single '*' indicates the rest of the arguments are keyword only
            # and shouldn't be counted as a `*`.
            if child.type == token.STAR:
                previous_token_is_star = True
            elif child.type == token.DOUBLESTAR:
                starstar = True
            elif child.type == token.NAME:
                if count == 0:
                    if child.value in ('self', 'cls'):
                        selfish = True
                count += 1
                if previous_token_is_star:
                    star = True
            elif child.type == token.EQUAL:
                skip = True
            if child.type != token.STAR:
                previous_token_is_star = False
    return count, selfish, star, starstar


def is_type_comment(comment):
    return TYPE_REG.match(comment)


class BaseFixAnnotate(BaseFix):

    # This fixer is compatible with the bottom matcher.
    BM_compatible = True

    # This fixer shouldn't run by default.
    explicit = True

    # The pattern to match.
    PATTERN = """
              funcdef< 'def' name=any parameters=parameters< '(' [args=any] rpar=')' > ':' suite=any+ >
              """

    _maxfixes = os.getenv('MAXFIXES')
    counter = None if not _maxfixes else int(_maxfixes)
    _type_options = None  # type: Optional[Dict[str, Any]]

    @property
    def type_options(self):
        if self._type_options is None:
            self._type_options = self.options.get('typeright', {})
        return self._type_options

    def should_skip(self, node, results):
        if BaseFixAnnotate.counter is not None:
            if BaseFixAnnotate.counter <= 0:
                return True

        # Check if there's already a long-form annotation for some argument.
        parameters = results.get('parameters')
        if parameters is not None:
            for ch in parameters.pre_order():
                if ch.prefix.lstrip().startswith('# type:'):
                    return True

        args = results.get('args')
        if args is not None:
            for ch in args.pre_order():
                if ch.prefix.lstrip().startswith('# type:'):
                    return True

        children = results['suite'][0].children

        # NOTE: I've reverse-engineered the structure of the parse tree.
        # It's always a list of nodes, the first of which contains the
        # entire suite.  Its children seem to be:
        #
        #   [0] NEWLINE
        #   [1] INDENT
        #   [2...n-2] statements (the first may be a docstring)
        #   [n-1] DEDENT
        #
        # Comments before the suite are part of the INDENT's prefix.
        #
        # "Compact" functions (e.g. "def foo(x, y): return max(x, y)")
        # have a different structure (no NEWLINE, INDENT, or DEDENT).

        # Check if there's already an annotation.
        for ch in children:
            if ch.prefix.lstrip().startswith('# type:'):
                return True  # There's already a # type: comment here; don't change anything.

        # Python 3 style return annotation are already skipped by the pattern

        # Python 3 style argument annotation structure
        #
        # Structure of the arguments tokens for one positional argument without default value :
        # + LPAR '('
        # + NAME_NODE_OR_LEAF arg1
        # + RPAR ')'
        #
        # NAME_NODE_OR_LEAF is either:
        # 1. Just a leaf with value NAME
        # 2. A node with children: NAME, ':", node expr or value leaf
        #
        # Structure of the arguments tokens for one args with default value or multiple
        # args, with or without default value, and/or with extra arguments :
        # + LPAR '('
        # + node
        #   [
        #     + NAME_NODE_OR_LEAF
        #      [
        #        + EQUAL '='
        #        + node expr or value leaf
        #      ]
        #    (
        #        + COMMA ','
        #        + NAME_NODE_OR_LEAF positional argn
        #      [
        #        + EQUAL '='
        #        + node expr or value leaf
        #      ]
        #    )*
        #   ]
        #   [
        #     + STAR '*'
        #     [
        #     + NAME_NODE_OR_LEAF positional star argument name
        #     ]
        #   ]
        #   [
        #     + COMMA ','
        #     + DOUBLESTAR '**'
        #     + NAME_NODE_OR_LEAF positional keyword argument name
        #   ]
        # + RPAR ')'

        # Let's skip Python 3 argument annotations
        it = iter(args.children) if args else iter([])
        for ch in it:
            if ch.type == token.STAR:
                # *arg part
                ch = next(it)
                if ch.type == token.COMMA:
                    continue
            elif ch.type == token.DOUBLESTAR:
                # *arg part
                ch = next(it)
            if ch.type > 256:
                # this is a node, therefore an annotation
                assert ch.children[0].type == token.NAME
                return True
            try:
                ch = next(it)
                if ch.type == token.COLON:
                    # this is an annotation
                    return True
                elif ch.type == token.EQUAL:
                    ch = next(it)
                    ch = next(it)
                assert ch.type == token.COMMA
                continue
            except StopIteration:
                break

        return False

    def transform(self, node, results):
        if self.should_skip(node, results):
            return

        # Compute the annotation
        annot = self.make_annotation(node, results)
        if annot is None:
            return
        argtypes, restype = annot

        if self.type_options['annotation_style'] == 'py3':
            self.add_py3_annot(argtypes, restype, node, results)
        else:
            self.add_py2_annot(argtypes, restype, node, results)

        # Common to py2 and py3 style annotations:
        if BaseFixAnnotate.counter is not None:
            BaseFixAnnotate.counter -= 1

        # Also add 'from typing import Any' at the top if needed.
        self.patch_imports(argtypes + [restype], node)

    def add_py3_annot(self, argtypes, restype, node, results):
        # type: (List[str], str, Node, Dict[str, Any]) -> None

        args = results.get('args')  # type: Optional[Node]

        argleaves = []  # type: List[Tuple[str, Leaf]]
        if args is None:
            # function with 0 arguments
            it = iter([])  # type: Iterator[Union[Leaf, Node]]
        elif len(args.children) == 0:
            # function with 1 argument
            it = iter([args])
        else:
            # function with multiple arguments or 1 arg with default value
            it = iter(args.children)

        for ch in it:
            argstyle = 'name'
            if ch.type == token.STAR:
                # *arg part
                argstyle = 'star'
                ch = next(it)
                if ch.type == token.COMMA:
                    continue
            elif ch.type == token.DOUBLESTAR:
                # *arg part
                argstyle = 'keyword'
                ch = next(it)
            assert ch.type == token.NAME
            assert isinstance(ch, Leaf)
            argleaves.append((argstyle, ch))
            try:
                ch = next(it)
                if ch.type == token.EQUAL:
                    ch = next(it)
                    ch = next(it)
                assert ch.type == token.COMMA
                continue
            except StopIteration:
                break

        # when self or cls is not annotated, argleaves == argtypes+1
        argleaves = argleaves[len(argleaves) - len(argtypes):]

        for ch_withstyle, chtype in zip(argleaves, argtypes):
            style, ch = ch_withstyle
            if style == 'star':
                assert chtype[0] == '*'
                assert chtype[1] != '*'
                chtype = chtype[1:]
            elif style == 'keyword':
                assert chtype[0:2] == '**'
                assert chtype[2] != '*'
                chtype = chtype[2:]
            ch.value = '%s: %s' % (ch.value, chtype)

            # put spaces around the equal sign
            if ch.next_sibling and ch.next_sibling.type == token.EQUAL:
                nextch = ch.next_sibling
                if not nextch.prefix[:1].isspace():
                    nextch.prefix = ' ' + nextch.prefix
                nextch_ = nextch.next_sibling
                assert nextch_ is not None
                if not nextch_.prefix[:1].isspace():
                    nextch_.prefix = ' ' + nextch_.prefix

        # Add return annotation
        rpar = results['rpar']
        rpar.value = '%s -> %s' % (rpar.value, restype)

        rpar.changed()

    def use_py2_long_form(self, argtypes, short_str, degen_str):
        # type: (List[str], str, str) -> bool
        if self.type_options['comment_style'] == 'single':
            return False
        elif self.type_options['comment_style'] == 'multi':
            return False
        else:  # auto
            return ((len(short_str) > 64 or len(argtypes) > 5)
                    and len(short_str) > len(degen_str))

    def add_py2_annot(self, argtypes, restype, node, results):
        # type: (List[str], str, Node, Dict[str, Any]) -> None

        children = results['suite'][0].children

        # Insert '# type: {annot}' comment.
        # For reference, see lib2to3/fixes/fix_tuple_params.py in stdlib.
        if len(children) >= 1 and children[0].type != token.NEWLINE:
            # one liner function
            if children[0].prefix.strip() == '':
                children[0].prefix = ''
                children.insert(0, Leaf(token.NEWLINE, '\n'))
                children.insert(
                    1, Leaf(token.INDENT, find_indentation(node) + '    '))
                children.append(Leaf(token.DEDENT, ''))

        if len(children) >= 2 and children[1].type == token.INDENT:
            degen_str = '(...) -> %s' % restype
            short_str = '(%s) -> %s' % (', '.join(argtypes), restype)
            if self.use_py2_long_form(argtypes, short_str, degen_str):
                self.insert_long_form(node, results, argtypes)
                annot_str = degen_str
            else:
                annot_str = short_str

            indent_node = children[1]
            comment, sep, other_comments = indent_node.prefix.partition('\n')
            comment = comment.rstrip() + sep
            annot_str = '# type: %s\n' % (annot_str,)
            if comment == annot_str:
                return

            if comment and not is_type_comment(comment):
                # push existing non-type comment to next line
                annot_str += comment

            indent_node.prefix = indent_node.value + annot_str + other_comments
            indent_node.changed()
        else:
            self.log_message("%s:%d: cannot insert annotation for one-line function" %
                             (self.filename, node.get_lineno()))

    def insert_long_form(self, node, results, argtypes):
        # type: (Node, Dict[str, Any], List[str]) -> None

        argtypes = list(argtypes)  # We destroy it
        args = results['args']
        if isinstance(args, Node):
            children = args.children
        elif isinstance(args, Leaf):
            children = [args]
        else:
            children = []
        # Interpret children according to the following grammar:
        # (('*'|'**')? NAME ['=' expr] ','?)*
        flag = False  # Set when the next leaf should get a type prefix
        indent = ''  # Will be set by the first child

        def set_prefix(child):
            if argtypes:
                arg = argtypes.pop(0).lstrip('*')
            else:
                arg = 'Any'  # Somehow there aren't enough args
            if not arg:
                # Skip self (look for 'check_self' below)
                prefix = child.prefix.rstrip()
            else:
                prefix = '  # type: ' + arg
                old_prefix = child.prefix.strip()
                if old_prefix:
                    assert old_prefix.startswith('#')
                    prefix += '  ' + old_prefix
            child.prefix = prefix + '\n' + indent

        check_self = self.is_method(node)
        for child in children:
            if isinstance(child, Leaf):
                if check_self and child.type == token.NAME:
                    check_self = False
                    if child.value in ('self', 'cls'):
                        argtypes.insert(0, '')
                if not indent:
                    indent = ' ' * child.column
                if child.value == ',':
                    flag = True
                elif flag:
                    set_prefix(child)
                    flag = False

        need_comma = len(children) >= 1 and children[-1].type != token.COMMA
        if need_comma and len(children) >= 2:
            if (children[-1].type == token.NAME and
                    (children[-2].type in (token.STAR, token.DOUBLESTAR))):
                need_comma = False
        if need_comma:
            children.append(Leaf(token.COMMA, u","))
        # Find the ')' and insert a prefix before it too.
        parameters = args.parent
        close_paren = parameters.children[-1]
        assert close_paren.type == token.RPAR, close_paren
        set_prefix(close_paren)
        assert not argtypes, argtypes

    def patch_imports(self, types, node):
        for typ in types:
            if 'Any' in typ:
                touch_import('typing', 'Any', node)
                break

    def make_annotation(self, node, results):
        # type: (Node, Dict[str, Any]) -> Optional[Tuple[List[str], str]]
        """Return the type annotations.

        Given the current Note and the dictionary parsed from PATTERN
        return the annoations for the arguments and return types as strings
        """
        raise NotImplementedError

    # The parse tree has a different shape when there is a single
    # decorator vs. when there are multiple decorators.
    DECORATED = "decorated< (d=decorator | decorators< dd=decorator+ >) funcdef >"
    decorated = compile_pattern(DECORATED)

    def get_decorators(self, node):
        """Return a list of decorators found on a function definition.

        This is a list of strings; only simple decorators
        (e.g. @staticmethod) are returned.

        If the function is undecorated or only non-simple decorators
        are found, return [].
        """
        if node.parent is None:
            return []
        results = {}
        if not self.decorated.match(node.parent, results):
            return []
        decorators = results.get('dd') or [results['d']]
        decs = []
        for d in decorators:
            for child in d.children:
                if isinstance(child, Leaf) and child.type == token.NAME:
                    decs.append(child.value)
        return decs

    def is_method(self, node):
        """Return whether the node occurs (directly) inside a class."""
        node = node.parent
        while node is not None:
            if node.type == syms.classdef:
                return True
            if node.type == syms.funcdef:
                return False
            node = node.parent
        return False

    RETURN_EXPR = "return_stmt< 'return' any >"
    return_expr = compile_pattern(RETURN_EXPR)

    def has_return_exprs(self, node):
        """Traverse the tree below node looking for 'return expr'.

        Return True if at least 'return expr' is found, False if not.
        (If both 'return' and 'return expr' are found, return True.)
        """
        results = {}
        if self.return_expr.match(node, results):
            return True
        for child in node.children:
            if child.type not in (syms.funcdef, syms.classdef):
                if self.has_return_exprs(child):
                    return True
        return False

    YIELD_EXPR = "yield_expr< 'yield' [any] >"
    yield_expr = compile_pattern(YIELD_EXPR)

    def is_generator(self, node):
        """Traverse the tree below node looking for 'yield [expr]'."""
        results = {}
        if self.yield_expr.match(node, results):
            return True
        for child in node.children:
            if child.type not in (syms.funcdef, syms.classdef):
                if self.is_generator(child):
                    return True
        return False


class BaseFixAnnotateFromSignature(BaseFixAnnotate):

    line_drift = 5
    safe_imports = set(['typing'])

    def __init__(self, options, log):
        super(BaseFixAnnotateFromSignature, self).__init__(options, log)

        self.needed_imports = set()  # type: Set[Tuple[str, str]]
        self.needed_type_checking_imports = set()  # type: Set[Tuple[str, str]]

    @classmethod
    @contextmanager
    def max_line_drift_set(cls, max_drift):
        old_drift = cls.line_drift
        cls.line_drift = max_drift
        try:
            yield
        finally:
            cls.line_drift = old_drift

    def add_import(self, mod, name, in_type_checking=False):
        """
        Adds potential import according to the 'in_type_checking' flag. If true, and if the potential
        import is not in safe_imports, then we assume this potential import is liable to cause an
        import cycle and should therefore be added under a TYPE_CHECKING block. If false, we just
        assume that isn't a concern and we add the import to the top level of the file.
        """
        if mod == self.current_module():
            return

        if in_type_checking and mod not in self.safe_imports:
            # Pass to the type checking queue
            self.needed_type_checking_imports.add((mod, name))
            return

        self.needed_imports.add((mod, name))

    def touch_typing_import(self, word, node):
        # type: (str, Node) -> None
        """
        Checks whether there exists import for type <word> and if not adds it to the instance
        import list

        Parameters
        -----------
        word : str
        node : Node
        """
        if word in typing_all:
            if not type_by_import_stmt('typing', word, node):
                # No import statement was found, should import
                self.add_import('typing', word)

    def patch_imports(self, types, node):
        if self.needed_imports:
            for mod, name in sorted(self.needed_imports):
                create_import(mod, name, node)
        if self.needed_type_checking_imports:
            for mod, name in sorted(self.needed_type_checking_imports):
                create_type_checking_import(mod, name, node)
        self.needed_imports.clear()
        self.needed_type_checking_imports.clear()

    def set_filename(self, filename):
        super(BaseFixAnnotateFromSignature, self).set_filename(filename)
        self._current_module = crawl_up(filename)[1]

    def current_module(self):
        # type: () -> str
        """Return the dotted path of the module currently being transformed"""
        return self._current_module

    def get_types(self, node, results, funcname):
        # type: (Node, Dict[str, Any], str) -> Optional[Tuple[List[str], str]]
        """Return types for `funcname`."""
        raise NotImplementedError

    def make_annotation(self, node, results):
        # type: (Node, Dict[str, Any]) -> Optional[Tuple[List[str], str]]
        name = results['name']
        assert isinstance(name, Leaf), repr(name)
        assert name.type == token.NAME, repr(name)
        funcname = get_funcname(node)

        def make(node, results, funcname):
            # type: (Node, Any, str) -> Optional[Tuple[List[str], str]]
            sig_data = self.get_types(node, results, funcname)
            if sig_data:
                arg_types, ret_type = sig_data
                return self.process_types(node, results, arg_types, ret_type)
            return None

        res = make(node, results, funcname)
        # If we couldn't find an annotation and this is a classmethod or
        # staticmethod, try again with just the funcname, since the
        # type collector can't figure out class names for those.
        # (We try with the full name above first so that tools that *can* figure
        # that out, like dmypy suggest, can use it.)
        if not res:
            decs = self.get_decorators(node)
            if 'staticmethod' in decs or 'classmethod' in decs:
                res = make(node, results, name.value)
        return res

    def process_types(self, node, results, arg_types, ret_type):
        # type: (Node, Dict[str, Any], List[str], str) -> Optional[Tuple[List[str], str]]
        """Process type annotations to handle star args, self-type, and imports."""
        # Passes 1-2 don't always understand *args or **kwds,
        # so add '*Any' or '**Any' at the end if needed.
        count, selfish, star, starstar = count_args(node, results)
        for arg_type in arg_types:
            if arg_type.startswith('**'):
                starstar = False
            elif arg_type.startswith('*'):
                star = False
        if star:
            arg_types.append('*Any')
        if starstar:
            arg_types.append('**Any')
        # Pass 1 omits the first arg iff it's named 'self' or 'cls',
        # even if it's not a method, so insert `Any` as needed
        # (but only if it's not actually a method).
        if selfish and len(arg_types) == count - 1:
            if self.is_method(node):
                count -= 1  # Leave out the type for 'self' or 'cls'
            else:
                arg_types.insert(0, 'Any')
        # If after those adjustments the count is still off,
        # print a warning and skip this node.
        if len(arg_types) != count:
            self.log_message("%s:%d: source has %d args, annotation has %d -- skipping" %
                             (self.filename, node.get_lineno(), count, len(arg_types)))
            return None

        arg_types = [self.update_type_names(arg_type, node) for arg_type in arg_types]
        # Avoid common error "No return value expected"
        if ret_type == 'None' and self.has_return_exprs(node):
            ret_type = 'Optional[Any]'
        # Special case for generators.
        if (self.is_generator(node) and
                not (ret_type == 'Iterator' or ret_type.startswith('Iterator['))):
            if ret_type.startswith('Optional['):
                assert ret_type[-1] == ']'
                ret_type = ret_type[9:-1]
            ret_type = 'Iterator[%s]' % ret_type
        ret_type = self.update_type_names(ret_type, node)
        return arg_types, ret_type

    def update_type_names(self, type_str, node):
        # type: (str, Node) -> str
        """Fixup module names and add necessary imports."""
        # Replace e.g. `List[pkg.mod.SomeClass]` with
        # `List[SomeClass]` and remember to import it.
        return re.sub(r'[\w.:]+', lambda m: self.type_updater(m, node), type_str)

    def type_updater(self, match, node):
        # type: (Match, Node) -> str
        # If import does not exist yet, replace `pkg.mod.SomeClass` with `SomeClass`
        # and remember to import it. Otherwise replace `pkg.mod.SomeClass` with the name
        # bound to its import
        word = match.group()
        if word == '...':
            return word
        if '.' not in word and ':' not in word:
            # Assume it's either builtin or from `typing`
            self.touch_typing_import(word, node)
            return word
        # If there is a :, treat that as the separator between the
        # module and the class.  Otherwise assume everything but the
        # last element is the module.
        if ':' in word:
            mod, name = word.split(':')
            to_import = name.split('.', 1)[0]
        else:
            mod, name = word.rsplit('.', 1)
            to_import = name

        # Get the typename we need to use to be valid for a current import statement
        result = type_by_import_stmt(mod, to_import, node)

        if result is not None:
            # There exists a current import statement this type is valid for
            # We know this module has already been imported
            return result

        in_type_checking = True
        # Get a list of cached imports from this node's root
        unprotected_imports = get_unprotected_imports(node)
        if mod in unprotected_imports:
            # If this mod was already imported in the original file, its safe to import from again
            in_type_checking = False

        # There exists no import statement for this type, add one
        self.add_import(mod, to_import, in_type_checking=in_type_checking)

        return name
