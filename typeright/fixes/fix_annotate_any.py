from __future__ import absolute_import, print_function

import re
from lib2to3.pgen2 import token
from lib2to3.pytree import Leaf, Node

from .base import BaseFixAnnotate


class FixAnnotateAny(BaseFixAnnotate):
    """Fixer that inserts Any for all types"""

    def make_annotation(self, node, results):
        name = results['name']
        assert isinstance(name, Leaf), repr(name)
        assert name.type == token.NAME, repr(name)
        decorators = self.get_decorators(node)
        is_method = self.is_method(node)
        if name.value == '__init__' or not self.has_return_exprs(node):
            restype = 'None'
        else:
            restype = 'Any'
        args = results.get('args')
        argtypes = []
        if isinstance(args, Node):
            children = args.children
        elif isinstance(args, Leaf):
            children = [args]
        else:
            children = []
        # Interpret children according to the following grammar:
        # (('*'|'**')? NAME ['=' expr] ','?)*
        stars = inferred_type = ''
        in_default = False
        at_start = True
        for child in children:
            if isinstance(child, Leaf):
                if child.value in ('*', '**'):
                    stars += child.value
                elif child.type == token.NAME and not in_default:
                    if not is_method or not at_start or 'staticmethod' in decorators:
                        inferred_type = 'Any'
                    else:
                        # Always skip the first argument if it's named 'self'.
                        # Always skip the first argument of a class method.
                        if child.value == 'self' or 'classmethod' in decorators:
                            pass
                        else:
                            inferred_type = 'Any'
                elif child.value == '=':
                    in_default = True
                elif in_default and child.value != ',':
                    if child.type == token.NUMBER:
                        if re.match(r'\d+[lL]?$', child.value):
                            inferred_type = 'int'
                        else:
                            inferred_type = 'float'  # TODO: complex?
                    elif child.type == token.STRING:
                        if child.value.startswith(('u', 'U')):
                            inferred_type = 'unicode'
                        else:
                            inferred_type = 'str'
                    elif child.type == token.NAME and child.value in ('True', 'False'):
                        inferred_type = 'bool'
                elif child.value == ',':
                    if inferred_type:
                        argtypes.append(stars + inferred_type)
                    # Reset
                    stars = inferred_type = ''
                    in_default = False
                    at_start = False
        if inferred_type:
            argtypes.append(stars + inferred_type)
        return argtypes, restype
