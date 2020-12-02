"""
Typewriter specific fixer utility functions
"""

from lib2to3.fixer_util import (FromImport, Leaf, Newline, Node,
                                does_tree_import, find_root, is_import, syms,
                                token)
from typing import Optional


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

    if does_tree_import(package, name, root):
        # name is being imported directly in the form of
        # from <package> import <name>
        return name

    if does_tree_import(None, package, root):
        # Mod is being imported in the form of
        # import <package>
        return '.'.join((package, name))

    return None  # return None to signal there is not yet an import statement


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
