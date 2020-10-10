# flake8: noqa
# Our flake extension misfires on type comments in strings below.

import json
import os
import tempfile

from typewriter.fixes.fix_annotate_json import BaseFixAnnotateFromSignature, FixAnnotateJson
from typewriter.fixes.tests import base_py2


class TestFixAnnotateJson(base_py2.AnnotateFromSignatureTestCase):

    def setUp(self):
        super(TestFixAnnotateJson, self).setUp(
            fix_list=["annotate_json"],
            fixer_pkg="typewriter",
            options={'annotation_style': 'py2', 'comment_style': 'auto'},
        )
        # See https://bugs.python.org/issue14243 for details
        self.tf = tempfile.NamedTemporaryFile(mode='w', delete=False)
        FixAnnotateJson.stub_json_file = self.tf.name
        FixAnnotateJson.stub_json = None

    def tearDown(self):
        FixAnnotateJson.stub_json = None
        FixAnnotateJson.stub_json_file = None
        self.tf.close()
        os.remove(self.tf.name)
        super(TestFixAnnotateJson, self).tearDown()

    def setTestData(self, data):
        json.dump(data, self.tf)
        self.tf.close()
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
