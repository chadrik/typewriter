# flake8: noqa
# Our flake extension misfires on type comments in strings below.

import json
import subprocess
from typewriter.fixes.fix_annotate_command import FixAnnotateCommand
from typewriter.fixes.tests import base_py2

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch


class TestFixAnnotateCommand(base_py2.AnnotateFromSignatureTestCase):

    def setUp(self):
        super(TestFixAnnotateCommand, self).setUp(
            fix_list=["annotate_command"],
            fixer_pkg="typewriter",
            options={'annotation_style': 'py2', 'comment_style': 'auto'},
        )
        self.patcher = None
        FixAnnotateCommand.set_command("fake {funcname} {filename}")

    def tearDown(self):
        FixAnnotateCommand.command = None
        if self.patcher is not None:
            self.patcher.stop()
            self.patcher = None
        super(TestFixAnnotateCommand, self).tearDown()

    def setTestData(self, data):
        self.filename = data[0]["path"]

        by_func = {d['func_name']: json.dumps([d]) for d in data}

        def check_output(cmd, **kwargs):
            try:
                return by_func[cmd[1]]
            except KeyError:
                raise subprocess.CalledProcessError(
                    2, cmd, output='No guesses that match criteria!')

        self.patcher = patch('subprocess.check_output', new=check_output)
        self.patcher.start()
