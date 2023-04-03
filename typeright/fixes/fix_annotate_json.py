"""Fixer that inserts mypy annotations from json file into code.

This fixer consumes json from TYPE_COLLECTION_JSON env variable in the following format:

[
    {
        "path": "/Users/svorobev/src/client/build_number/__init__.py",
        "func_name": "is_test",
        "arg_types": ["int", "str"],
        "ret_type": "Any"
    },
    ...
]

(The old format with "type_comment" instead of "arg_types" and
"ret_type" is also still supported.)
"""

from __future__ import print_function

import json  # noqa
import os
from lib2to3.pytree import Base, Leaf, Node
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from typing import Text
except ImportError:
    # In Python 3.5.1 stdlib, typing.py does not define Text
    Text = str  # type: ignore

from .base import BaseFixAnnotateFromSignature


class FixAnnotateJson(BaseFixAnnotateFromSignature):

    def get_types(self, node, results, funcname):
        # type: (Union[Leaf, Node], Dict[str, Any], str) -> Optional[Tuple[List[str], str]]
        data = self.type_options['type_info']
        top_dir = self.type_options['top_dir']
        # FIXME: this lookup code is inefficient and fragile.  We should restructure
        #  the json to be keyed by (funcname, rel path), and compute a rel path from self.filename.
        # We are using relative paths in the JSON.
        items = [
            it for it in data
            if it['func_name'] == funcname and
            (it['path'] == self.filename or
                os.path.join(top_dir, it['path']) == os.path.abspath(self.filename))
        ]
        if len(items) > 1:
            # this can happen, because of
            # 1) nested functions
            # 2) method decorators
            # as a cheap and dirty solution we just return the nearest one by the line number
            # (keep the commented-out log_message call in case we need to come back to this)
            # self.log_message("%s:%d: duplicate signatures for %s (at lines %s)" %
            # (items[0]['path'], node.get_lineno(), items[0]['func_name'],
            # ", ".join(str(it['line']) for it in items)))
            items.sort(key=lambda it: abs(node.get_lineno() - it['line']))
        if items:
            it = items[0]
            # If the line number is too far off, the source probably drifted
            # since the trace was collected; it's better to skip this node.
            # (Allow some drift, since decorators also cause an offset.)
            if abs(node.get_lineno() - it['line']) >= self.line_drift:
                self.log_message("%s:%d: '%s' signature from line %d too far away -- skipping" %
                                 (self.filename, node.get_lineno(), it['func_name'], it['line']))
                return None
            if 'signature' in it:
                return it['signature']['arg_types'], it['signature']['return_type']
        return None
