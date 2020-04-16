from __future__ import absolute_import, print_function

import json
import shlex
import subprocess

from .fix_annotate_json import BaseFixAnnotateFromSignature, FixAnnotateJson as _FixAnnotateJson

class FixAnnotateCommand(BaseFixAnnotateFromSignature):
    """Inserts annotations based on a command run in a subprocess for each
    location.  The command is expected to output a json string in the same
    format output by `dmypy suggest` and `pyannotate_tool --type-info`

    The fixer is run after FixAnnotateJson so that if an annotation is provided
    explicitly that fixer will win out.
    """
    # run after FixAnnotateJson
    run_order = _FixAnnotateJson.run_order + 1

    command = None

    @classmethod
    def set_command(cls, command):
        cls.command = command

    def get_command(self, filename, lineno):
        return shlex.split(self.command.format(filename=filename, lineno=lineno))

    def get_types(self, node, results, funcname):
        cmd = self.get_command(self.filename, node.get_lineno())
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as err:
            self.log_message("Line %d: Failed calling `%s`: %s" %
                             (node.get_lineno(), self.command,
                              err.output.rstrip()))
            return None

        data = json.loads(out)
        signature = data[0]['signature']
        return signature['arg_types'], signature['return_type']