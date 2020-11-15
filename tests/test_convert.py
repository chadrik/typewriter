from __future__ import absolute_import, print_function

import logging

import pytest

from typewriter.__main__ import _main as main
from typewriter.fixes.fix_annotate_docs import FixAnnotateDocs

# def convert_string(input):
#     tool = RefactoringTool(get_fixers_from_package("doc484.fixes"))
#     tree = tool.refactor_string(input, '<test.py>')
#     return str(tree)


@pytest.mark.parametrize("config", ['test1', 'test2'])
@pytest.mark.parametrize("format", ['numpydoc', 'googledoc', 'restdoc', 'agnostic'])
def test_cli(format, config, pytestconfig, tmpdir, caplog):
    FixAnnotateDocs.format_name = None
    FixAnnotateDocs.default_return_type = None

    fixturedir = pytestconfig.rootdir.join('tests', 'fixtures')

    configdir = fixturedir.join('configs', config)
    results = fixturedir.join('results', '%s.%s.py' % (format, config))
    source = fixturedir.join('formats', (format + '.py'))
    # change directory so we can control discovery of setup.cfg
    configdir.chdir()
    dest = tmpdir.join((format + '.py'))

    # pytest calls basicConfig before main() gets a chance to.
    # by calling basicConfig, main sets up the root logger and loglevel for
    # all of lib2to3: it defaults to INFO, but --verbose sets it to DEBUG.
    caplog.set_level(logging.INFO)
    # also write unchanged files so that the agnostic tests write something to diff
    errors = main(["--write", "--write-unchanged-files",
                   "--annotation-style=py2",
                   "--py2-comment-style=single",
                   "--doc-format=auto",
                   "--quiet",
                   "--output-dir", str(tmpdir), str(source)])

    assert errors == []

    assert dest.exists()

    with dest.open() as f:
        destlines = f.read()

    if results.exists():
        with results.open() as f:
            expectedlines = f.read()
    else:
        print(destlines)
        expectedlines = ''

    assert expectedlines == destlines
