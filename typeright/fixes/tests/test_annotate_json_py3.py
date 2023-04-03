# flake8: noqa
# Our flake extension misfires on type comments in strings below.

import json
import os
import tempfile

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from typeright.fixes.fix_annotate_json import (BaseFixAnnotateFromSignature,
                                                FixAnnotateJson)
from typeright.fixes.tests import base_py3


class TestFixAnnotateJson(base_py3.AnnotateFromSignatureTestCase):

    def setUp(self):
        super(TestFixAnnotateJson, self).setUp(
            fix_list=["annotate_json"],
            fixer_pkg="typeright",
            options={
                'typeright': {
                    'annotation_style': 'py3',
                    'top_dir': '',
                },
            },
        )

    def setTestData(self, data):
        self.refactor.options['typeright']['type_info'] = data
        self.filename = data[0]["path"]

    def test_line_number_drift(self):
        self.setTestData(
            [{"func_name": "nop",
              "path": "<string>",
              "line": 10,
              "signature": {
                  "arg_types": [],
                  "return_type": "int"},
              }])
        a = """\
            def nop(a):
                pass
            """
        self.warns(a, a, "signature from line 10 too far away -- skipping", unchanged=True)

    @patch('typeright.fixes.fix_annotate_json.BaseFixAnnotateFromSignature.set_filename')
    def test_set_filename(self, mocked_set_filename):
        self.filename = "/path/to/fileA.py"
        # trigger the fixer to run, with no expected changes
        self.unchanged("")
        mocked_set_filename.assert_called_with("/path/to/fileA.py")

        self.filename = "/path/to/fileB.py"
        # trigger the fixer to run, with no expected changes
        self.unchanged("")
        mocked_set_filename.assert_called_with("/path/to/fileB.py")
