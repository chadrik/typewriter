from __future__ import absolute_import, print_function

import json
import re
import shlex
import subprocess
from lib2to3.pytree import Node
from typing import Any, Dict, List, Optional, Tuple

from .fix_annotate_json import BaseFixAnnotateFromSignature

REG = re.compile(r'`-?\d+')


def cleanup(s, node):
    if s == 'Tuple[]':
        # this gets generated for statements like `return ()`
        # FIXME: touch_import('typing', 'Any')
        return 'Tuple[Any, ...]'
    else:
        # fix 'T`1' -> 'T'
        return REG.sub('', s)


class FixAnnotateCommand(BaseFixAnnotateFromSignature):
    """Inserts annotations based on a command run in a subprocess for each
    location.  The command is expected to output a json string in the same
    format output by `dmypy suggest` and `pyannotate_tool --type-info`
    """

    def get_command(self, funcname, filename, lineno):
        # type: (str, str, int) -> List[str]
        command = self.type_options['command']
        return shlex.split(command.format(filename=filename, lineno=lineno,
                                          funcname=funcname))

    def get_types(self, node, results, funcname):
        # type: (Node, Dict[str, Any], str) -> Optional[Tuple[List[str], str]]
        cmd = self.get_command(funcname, self.filename, node.get_lineno())
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as err:
            # dmypy suggest exits 2 anytime it can't generate a suggestion,
            # even for somewhat expected cases like when --no-any is enabled:
            if err.returncode != 2:
                self.log_message("Line %d: Failed calling %r: %s" %
                                 (node.get_lineno(), cmd,
                                  err.output.rstrip().encode()))
            return None
        except OSError as err:
            self.log_message("Line %d: Failed calling %r: %s" %
                             (node.get_lineno(), cmd, err))
            return None

        data = json.loads(out)
        signature = data[0]['signature']
        return [cleanup(arg, node) for arg in signature['arg_types']], \
            cleanup(signature['return_type'], node)
