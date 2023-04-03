# flake8: noqa
# Our flake extension misfires on type comments in strings below.

import json
import os
import tempfile

from typeright.fixes.fix_annotate_json import (BaseFixAnnotateFromSignature,
                                                FixAnnotateJson)
from typeright.fixes.tests import base_py2


class TestFixAnnotateJson(base_py2.AnnotateFromSignatureTestCase):

    def setUp(self):
        super(TestFixAnnotateJson, self).setUp(
            fix_list=["annotate_json"],
            fixer_pkg="typeright",
            options={
                'typeright': {
                    'annotation_style': 'py2',
                    'comment_style': 'auto',
                    'top_dir': '',
                },
            },
        )

    def setTestData(self, data):
        self.filename = data[0]["path"]
        self.refactor.options['typeright']['type_info'] = data

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

    def test_line_number_drift_allowed(self):
        self.setTestData(
            [{"func_name": "yep",
              "path": "<string>",
              "line": 10,
              "signature": {
                  "arg_types": ["int"],
                  "return_type": "int"},
              }])
        a = """\
            def yep(a):
                return a
            """
        b = """\
            def yep(a):
                # type: (int) -> int
                return a
            """
        with BaseFixAnnotateFromSignature.max_line_drift_set(10):
            self.check(a, b)
