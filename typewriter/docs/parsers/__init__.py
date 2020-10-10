from __future__ import absolute_import, print_function

from typing import NamedTuple, Optional

Arg = NamedTuple('Arg', [
    ('type', Optional[str]),
    ('line', int),
])
