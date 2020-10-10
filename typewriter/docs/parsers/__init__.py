from __future__ import absolute_import, print_function

from typing import Optional, NamedTuple

Arg = NamedTuple('Arg', [
    ('type', Optional[str]),
    ('line', int),
])
