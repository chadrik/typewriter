"""
Typewriter specific fixer utility functions
"""

from functools import cache
from lib2to3.fixer_util import (FromImport, Leaf, Newline, Node,
                                does_tree_import, find_root, is_import,
                                make_suite, syms, token)
from typing import Dict, NamedTuple, Optional, Set, Union


def type_by_import_stmt(package, name, node):
    # type: (str, str, Node) -> Optional[str]
    """
    Return name that needs to be annotated based on available imports

    Parameters
    -------------
    package : str
    name : str
        Name of type being imported
    node : Node

    Returns
    -------------
    Optional[str]
        Returns valid name for type if current import statement exists, or None is there is no
        import statement
    """
    root = find_root(node)

    import_info = find_import_info(package, name, root)

    if import_info:
        # name is being imported directly in the form of
        # from <package> import <name>
        return import_info.binding

    split_path = package.rsplit('.', 1)
    if len(split_path) > 1:
        # We have a package of the form 'pkg.mod'
        pkg = split_path[0]
        mod = split_path[1]
    else:
        # We have a package of the form 'mod'
        pkg = ''
        mod = package
    module_import_info = find_import_info(pkg, mod, root)

    if module_import_info:
        return '.'.join((module_import_info.binding, name))

    return None


def create_import(package, name, node):
    # type: (str, str, Node) -> None
    """
    Create import statement of the form `from <package> import <name>`

    Parameters
    -------------
    package : str
    name : str
        Name of type being imported
    node : Node
    """

    def is_import_stmt(node):
        return (node.type == syms.simple_stmt and node.children and
                is_import(node.children[0]))

    root = find_root(node)

    # figure out where to insert the new import.  First try to find
    # the first import and then skip to the last one.
    insert_pos = offset = 0
    for idx, node in enumerate(root.children):
        if not is_import_stmt(node):
            continue
        for offset, node2 in enumerate(root.children[idx:]):
            if not is_import_stmt(node2):
                break
        insert_pos = idx + offset
        break

    # if there are no imports where we can insert, find the docstring.
    # if that also fails, we stick to the beginning of the file
    if insert_pos == 0:
        for idx, node in enumerate(root.children):
            if (node.type == syms.simple_stmt and node.children and
                    node.children[0].type == token.STRING):
                insert_pos = idx + 1
                break

    if package is None:
        import_ = Node(syms.import_name, [
            Leaf(token.NAME, "import"),
            Leaf(token.NAME, name, prefix=" ")
        ])
    else:
        import_ = FromImport(package, [Leaf(token.NAME, name, prefix=" ")])

    children = [import_, Newline()]
    root.insert_child(insert_pos, Node(syms.simple_stmt, children))


def touch_import(package, name, node):
    # type: (str, str, Node) -> str
    """
    Almost the same as lib2to3/fixer_util's touch_import, but broken into helper functions.
    The difference between the lib2to3's function and ours is that this function assumes a
    statement of the form:
        `import mod`
    is a sufficient import for type `mod.Name`.

    To not obfuscate which type of import statement currently exists (and by proxy which form the
    typename needs to be written in to be valid), we return the valid form of the typename.

    So for the example above, touch_import would return
        `mod.Name`
    but if instead there was an import statement of the form
        `from mod import Name`
    then this function would simply return
        `Name`

    Parameters
    -------------
    package : str
    name : str
        Name of the type being imported
    node : Node

    Return
    -------------
    str
        The typename that will be defined by either the already existing or created import
        statement
    """
    result = type_by_import_stmt(package, name, node)

    if result is not None:
        # If there is already an import statement
        return result

    create_import(package, name, node)
    return name


_block_syms = {syms.funcdef, syms.classdef, syms.trailer}


def _find(name, node):
    nodes = [node]
    while nodes:
        node = nodes.pop()
        if node.type > 256 and node.type not in _block_syms:
            nodes.extend(node.children)
        elif node.type == token.NAME and node.value.strip() == name:
            return node
    return None


ImportPairing = NamedTuple("ImportPairing", [
    ("entry", str),
    ("binding_name", str)
])

ImportNodeInfo = NamedTuple("ImportNodeInfo", [
    ("imports", Dict[str, Set[ImportPairing]]),
    ("node", Node)
])

ImportInfo = NamedTuple("ImportInfo", [
    ("entry", str),
    ("package", str),
    ("binding", str)
])


def find_import_info(package, name, node):
    # type: (str, str, Node) -> Optional[ImportInfo]
    """
    Finds the import statement for <name> regardless of whether <name> is the binding name
        ex where name='a':
        import a => match AND import a as b => match BUT import b as a => None

    Parameters
    -----------
    package : str
    name : str
    node : Node

    Return
    -----------
    Optional[ImportInfo]
    """
    for child in node.children:
        if is_import(child):
            ret = get_import_info(child)
            imports = ret.imports.get(package)
            if imports is None:
                return None
            import_ = next((x for x in imports if x.entry == name), None)
            if import_:
                return ImportInfo(import_.entry, package, import_.binding_name)
        elif child.type == syms.simple_stmt:
            res = find_import_info(package, name, child)
            if res is None:
                continue
            else:
                return res
    return None


def decompose_name(node):
    """
    NOTE: Per the lib2to3 grammar:
            dotted_name: NAME ('.' NAME)*
          This means that dotted_name can be either dotted or not dotted, i.e. it's a generalized
          form of NAME. So this function will cover both cases.

    Given a dotted_name node this will return a tuple of the form (pkg, name, full_string) where
    all are str
        ex: a.b.c => (a.b, c, a.b.c)
            b.c => (b, c, b.c)
            c => (None, c, c)
    otherwise it will return None for each field
    """
    if node.type == token.NAME:
        # node is just a name, no dots
        return '', node.value, node.value

    if node.children:
        # Right most node will be the name, i.e. a.b.c = ['a','.','b','.','c']
        name_node = node.children[-1]
        package_nodes = node.children[:-2]
        name = str(name_node).strip()
        package = ''.join(str(n).strip() for n in package_nodes)
        full = ''.join(str(n).strip() for n in node.children)
        return package, name, full

    return None, None, None


def get_import_info(node):
    """
    Wraps the cachable get_import_info in order to convert the node into a hashable node before
    attempting to cache
    """
    node = HashableNode(node)
    return _get_import_info_cachable(node)


class HashableNode(object):
    """
    Hashable wrapper for node and leaf objects in order to cache
    """

    def __init__(self, node):
        # type: (Union[Node, Leaf]) -> None
        """
        Parameters
        -----------
        node : Union[Node, Leaf]
        """
        self.node = node

    def __hash__(self):
        return hash((self.node.get_lineno(),
                     self.node.depth(),
                     self.node.__str__()))


@cache
def _get_import_info_cachable(hashable_node):
    # type: (HashableNode) -> ImportNodeInfo
    """
    We cache using hashable_node as a key and analyze hashable_node.node

    If node is a valid import_stmt, this will return a named tuple for each component of the
    statement
        ex: from a.b import c as d, e  => (imports={'a.b': [(import_name='c',
                                                             binding_name='d'),
                                                            (import_name='e',
                                                             binding_name='e')]},
                                           node=node)

    Since we will regularly iterate over the list import node for their information when
    searching for binding or import matches, we cache the results of this function for
    quick and non-redundant lookups

    Parameters
    -----------
    hashable_node : HashableNode

    Return
    -----------
    ImportNodeInfo
    """
    # Get the node from the hashable_node wrapper
    node = hashable_node.node

    def handle_name(node):
        if node.type in (syms.dotted_as_name, syms.import_as_name):
            # [Grammar] dotted_as_name: dotted_name ['as' NAME]
            package = import_name = binding_name = None
            name = node.children[0]
            binding_name = str(node.children[2]).strip()
            if name.type in (syms.dotted_name, token.NAME):
                # [Grammar] dotted_name: NAME ('.' NAME)*
                # We don't need the third field since we know the alias will be the binding_name
                package, import_name, _ = decompose_name(name)
            return package, import_name, binding_name
        # If there was no "as", we know this is dotted_name
        # [Grammar] dotted_name: NAME ('.' NAME)*
        return decompose_name(node)

    package = None
    imports = dict()  # type: Dict[str, Set[ImportPairing]]
    if node.type == syms.import_name:
        # [Grammar]: import_name: 'import' dotted_as_names
        as_name = node.children[1]
        if as_name.type in (syms.dotted_as_names, syms.import_as_names):
            # [Grammar]: dotted_as_names: dotted_as_name (',' dotted_as_name)*
            as_names = [child for child in as_name.children if str(child).strip() != ',']
        else:
            as_names = [as_name]
        for child in as_names:
            package, import_name, binding_name = handle_name(child)
            imports.setdefault(package, set()).add(ImportPairing(import_name, binding_name))
    elif node.type == syms.import_from:
        # [Grammar]:
        # import_from: ('from' ('.'* dotted_name | '.'+)
        #   'import' ('*' | '(' import_as_names ')' | import_as_names))
        package = str(node.children[1]).strip()
        if str(node.children[3]).strip() == '(':
            # This means we are dealing with an import statement containing parentheses
            # ex: from a import (b, c, d)
            import_as_name = node.children[4]
        else:
            import_as_name = node.children[3]
        if import_as_name.type == syms.import_as_names:
            as_names = [child for child in import_as_name.children if str(child).strip() != ',']
        else:
            as_names = [import_as_name]
        for child in as_names:
            _, import_name, binding_name = handle_name(child)
            imports.setdefault(package, set()).add(ImportPairing(import_name, binding_name))

    return ImportNodeInfo(imports, node)
