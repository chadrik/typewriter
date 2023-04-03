from __future__ import absolute_import, print_function

from lib2to3 import pytree
from lib2to3.fixer_util import does_tree_import, syms
from lib2to3.pgen2 import token
from lib2to3.pytree import Node
from typing import Any, Dict, List, Match, Optional, Tuple, cast

from ..docs import formats
from .base import get_funcname, typing_all
from .fix_annotate_json import BaseFixAnnotateFromSignature

SPECIAL_METHOD_RETURN = {
    '__init__': 'None'
}


def _get_type(typ, default='Any'):
    # type: (Optional[str], str) -> str
    return default if typ is None else typ


def find_classdef(node):
    # type: (pytree.Node) -> Optional[List[pytree.Node]]
    """
    Parameters
    ----------
    node : pytree.Node

    Returns
    -------
    Optional[List[pytree.Node]]
    """
    while True:
        parent = node.parent
        if parent is None:
            return None
        elif parent.type == syms.classdef:
            # return the suite as list
            for child in parent.children:
                if child.type == syms.suite:
                    return [cast(Node, child)]
            else:
                raise RuntimeError("could not find suite")
        node = parent


def get_docstring(suite):
    # type: (list) -> Tuple[Optional[str], int]
    """
    Get docstring data from a lib2t3 suite object

    Parameters
    ----------
    suite : list

    Returns
    -------
    docstring : Optional[str]
    lineno : int
    """
    assert isinstance(suite, list)
    if suite[0].children[1].type == token.INDENT:
        indent_node = suite[0].children[1]
        doc_node = suite[0].children[2]
    else:
        # e.g. "def foo(...): x = 5; y = 7"
        return None, -1

    if isinstance(doc_node, pytree.Node) and \
            doc_node.children[0].type == token.STRING:
        leaf = doc_node.children[0]
        if not isinstance(leaf, pytree.Leaf):
            raise RuntimeError
        doc = leaf.value
        # convert '"docstring"' to 'docstring'
        # FIXME: something better than eval
        return eval(doc), leaf.lineno
    else:
        # no docstring
        return None, -1


def keep_arg(i, arg_name, typ):
    # type: (int, str, Optional[str]) -> bool
    """
    Return whether `arg_name` should be included in the type annotation.

    Parameters
    ----------
    i : int
        position within the arg list
    arg_name : str
    typ : Optional[str]
        type of the arg

    Returns
    -------
    bool
    """
    # we can't *easily* tell from here if the current func is a
    # method, but the below is a pretty good assurance that we can skip
    # the current arg.
    # there is nothing wrong with including self or cls, but pep484
    # supports omitting it for brevity.
    return not (i == 0 and arg_name in {'self', 'cls'} and typ is None)


class FixAnnotateDocs(BaseFixAnnotateFromSignature):
    """Inserts annotations by parsing docstrings."""

    def get_format(self):
        # type: () -> str
        """
        Returns
        -------
        str
        """
        return self.type_options['doc_format']

    def get_default_return_type(self):
        # type: () -> str
        """
        Returns
        -------
        str
        """
        return self.type_options['doc_default_return_type']

    def parse_docstring(self, docstring, line):
        # type: (str, int) -> Tuple[Dict[str, str], Optional[str]]
        """
        Parameters
        ----------
        docstring : str
        line : int

        Returns
        -------
        args : Dict[str, str]
        result : Optional[str]
        """
        if docstring:
            params, result = formats.parse_docstring(docstring, line=line,
                                                     format_name=self.get_format(),
                                                     filename=self.filename)
            return ({k: v.type for k, v in params.items() if v.type},
                    result.type if result else None)
        else:
            return {}, None

    def should_skip(self, node, results):
        return False

    def type_updater(self, match, node):
        # type: (Match, Node) -> str
        # Replace `pkg.mod.SomeClass` with `SomeClass`
        # and remember to import it.
        word = match.group()
        if does_tree_import(None, word, node):
            # Check whether there already exists an import binding for this
            return word
        # If not, assume it's either builtin or from `typing`
        self.touch_typing_import(word, node)
        return word

    def make_annotation(self, node, results):
        # type: (Node, Dict[str, Any]) -> Optional[Tuple[List[str], str]]
        suite = results["suite"]

        docstring, line = get_docstring(suite)

        args = results.get("args")
        name_node = results["name"]

        funcname = get_funcname(node)
        short_funcname = funcname.rsplit('.')[-1]

        class_suite = find_classdef(name_node)
        is_method = class_suite is not None

        if docstring is None and short_funcname == '__init__' and class_suite is not None:
            # fall back to the class docstring
            docstring, line = get_docstring(class_suite)

        if docstring is None:
            return None

        arg_types = []  # type: List[str]
        argtype_map, ret_type = self.parse_docstring(docstring, line)

        if not argtype_map and not ret_type:
            # if the user has provided type annoations, we always use them
            return None

        if is_method and short_funcname in SPECIAL_METHOD_RETURN:
            default_return = SPECIAL_METHOD_RETURN[short_funcname]
        else:
            default_return = self.get_default_return_type()

        ret_type = _get_type(ret_type, default_return)

        if args:
            # if args.type == syms.tfpdef:
            #     pass
            if args.type == syms.typedargslist:
                arg_list = []  # type: List[str]
                kind_list = []  # type: List[str]
                consume = True
                kind = ''
                for arg in args.children:
                    if consume and arg.type == token.NAME:
                        arg_list.append(arg.value)
                        kind_list.append(kind)
                        consume = False
                    elif consume and arg.type == token.STAR:
                        kind = '*'
                    elif consume and arg.type == token.DOUBLESTAR:
                        kind = '**'
                    elif arg.type == token.COMMA:
                        consume = True
                        kind = ''
            elif args.type == token.NAME:
                arg_list = [args.value]
                kind_list = ['']
            else:
                raise TypeError(args)

            for i, (arg_name, kind) in enumerate(zip(arg_list, kind_list)):
                typ = argtype_map.get(arg_name)
                if typ is None and formats.default_arg_types:
                    typ = formats.default_arg_types.get(arg_name)
                if not is_method or keep_arg(i, arg_name, typ):
                    arg_types.append(kind + _get_type(typ).strip('*'))

        arg_types = [self.update_type_names(arg_type, node) for arg_type in arg_types]
        ret_type = self.update_type_names(ret_type, node)
        return arg_types, ret_type
