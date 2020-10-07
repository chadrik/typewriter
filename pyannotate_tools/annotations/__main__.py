from __future__ import print_function

import argparse
import json
import logging
import os
import re
import sys
from lib2to3.main import StdoutRefactoringTool
from os.path import expanduser, expandvars
from typing import Any, Dict, List, Optional

import six.moves.configparser as configparser

from pyannotate_tools.annotations.main import generate_annotations_json_string, unify_type_comments
from pyannotate_tools.docs import formats
from pyannotate_tools.fixes.base import BaseFixAnnotateFromSignature, crawl_up
from pyannotate_tools.fixes.fix_annotate_any import FixAnnotateAny
from pyannotate_tools.fixes.fix_annotate_command import FixAnnotateCommand
from pyannotate_tools.fixes.fix_annotate_docs import FixAnnotateDocs
from pyannotate_tools.fixes.fix_annotate_json import FixAnnotateJson

NAME = 'pyannotate'
CONFIG_FILES = [NAME + '.ini', 'setup.cfg']


def get_parser():
    parser = argparse.ArgumentParser()

    parser.add_argument('files', nargs='*', metavar="FILE",
                        help="Files and directories to update with annotations")

    # json --
    json_group = parser.add_argument_group('json file options',
                                           "Read type info from a json file")
    json_group.add_argument('--type-info', metavar="FILE",
                            help="JSON input file")
    json_group.add_argument('--max-line-drift', type=int, default=5, metavar="N",
                            help="Maximum allowed line drift when inserting annotation"
                                 " (can be useful for custom codecs)")
    json_group.add_argument('-d', '--dump', action='store_true',
                            help="Dump raw type annotations and exit "
                                 "(filter by files, default all)")
    json_group.add_argument('--uses-signature', action='store_true',
                            help="JSON input uses a signature format")
    json_group.add_argument('-s', '--only-simple', action='store_true',
                            help="Only annotate functions with trivial types")

    # command --
    cmd_group = parser.add_argument_group('command options',
                                          "Generate type info by calling an "
                                          "external program")
    cmd_group.add_argument('--command', '-c', metavar="COMMAND",
                           help="Command to generate JSON info for a call site")

    # doc --
    doc_group = parser.add_argument_group('docstring options',
                                          "Generate type info by parsing docstrings")
    doc_group.add_argument("--doc-format",
                           choices=sorted(list(formats.format_map.keys()) + ['auto', 'off']),
                           help="Specify the docstring convention used within "
                                "files to be converted ('auto' automatically "
                                "determines the format by inspecting each docstring "
                                "but it is faster and more reliable to specify this "
                                "explicitly)")
    doc_group.add_argument("--doc-default-return-type",
                           default='Any', metavar="TYPE",
                           help="Default type to use for undocumented return "
                                "values (defaults to 'Any'")

    # any --
    any_group = parser.add_argument_group('any options')
    any_group.add_argument('-a', '--auto-any', action='store_true',
                           help="Annotate everything with 'Any'")

    # format --
    format_group = parser.add_argument_group('output format options')
    format_group.add_argument('--annotation-style', default='auto',
                              choices=['auto', 'py2', 'py3'],
                              help="Choose annotation style, py2 for Python 2 with "
                                   "comments, py3 for Python 3 with annotation "
                                   "syntax. The default will be determined by the "
                                   "version of the current python interpreter")
    format_group.add_argument('--py2-comment-style', default='auto',
                              choices=['auto', 'multi', 'single'],
                              help="Choose comment style, multi adds a comment per "
                                   "argument, single produces one type comment for "
                                   "all arguments, and auto chooses between the two "
                                   "styles based on the number of arguments and "
                                   "length of comments")

    # other --
    other_group = parser.add_argument_group('other options')
    other_group.add_argument('-p', '--print-function', action='store_true',
                             help="Assume print is a function")
    other_group.add_argument('-w', '--write', action='store_true',
                             help="Write output files")
    other_group.add_argument('-j', '--processes', type=int, default=1, metavar="N",
                             help="Use N parallel processes (default no parallelism)")
    other_group.add_argument('-v', '--verbose', action='store_true',
                             help="More verbose output")
    other_group.add_argument('-q', '--quiet', action='store_true',
                             help="Don't show diffs")
    other_group.add_argument("-o", "--output-dir", type=str, default="",
                             metavar="FOLDER",
                             help="Put output files in this directory "
                                  "instead of overwriting the input files.")
    other_group.add_argument("-W", "--write-unchanged-files", action='store_true',
                             help="Also write files even if no changes were required"
                                  " (useful with --output-dir); implies -w.")
    return parser


def load_config(arg_parser):
    # type: (argparse.ArgumentParser) -> Dict
    """Use the ArgumentParser to extract values set in a config file.

    These are used to set the defaults on the parser before calling
    parse_args(), which ensures that arguments specified on the command line
    have a higher priority than those set in the config file.
    """
    SPLIT = re.compile('[,\n]+')
    paths = [expanduser(expandvars(path)) for path in CONFIG_FILES]
    config_parser = configparser.RawConfigParser()
    config_parser.read(paths)
    defaults = {}
    if config_parser.has_section(NAME):
        for action in arg_parser._actions:
            if action.dest in defaults:
                # some arguments may refer to the same destination
                continue
            try:
                if isinstance(action, argparse._HelpAction):
                    continue
                elif isinstance(action, (argparse._StoreFalseAction,
                                         argparse._StoreTrueAction,
                                         argparse._StoreAction,
                                         argparse._StoreConstAction)):
                    if action.type is int:
                        val = config_parser.getint(NAME, action.dest)  # type: Any
                    elif action.type is bool:
                        val = config_parser.getboolean(NAME, action.dest)
                    elif action.type is float:
                        val = config_parser.getfloat(NAME, action.dest)
                    else:
                        val = config_parser.get(NAME, action.dest)
                        if action.nargs in {'*', '+'}:
                            val = [x for x in SPLIT.split(val) if x]
                else:
                    raise TypeError(action)
            except configparser.NoOptionError:
                continue
            defaults[action.dest] = val

    return defaults


class ModifiedRefactoringTool(StdoutRefactoringTool):
    """Class that gives a nicer error message for bad encodings."""

    def refactor_file(self, filename, write=False, doctests_only=False):
        try:
            super(ModifiedRefactoringTool, self).refactor_file(
                filename, write=write, doctests_only=doctests_only)
        except SyntaxError as err:
            if str(err).startswith("unknown encoding:"):
                self.log_error("Can't parse %s: %s", filename, err)
            else:
                raise


def dump_annotations(type_info, files):
    """Dump annotations out of type_info, filtered by files.

    If files is non-empty, only dump items either if the path in the
    item matches one of the files exactly, or else if one of the files
    is a path prefix of the path.
    """
    with open(type_info) as f:
        data = json.load(f)
    for item in data:
        path, line, func_name = item['path'], item['line'], item['func_name']
        if files and path not in files:
            for f in files:
                if path.startswith(os.path.join(f, '')):
                    break
            else:
                continue  # Outer loop
        print("%s:%d: in %s:" % (path, line, func_name))
        type_comments = item['type_comments']
        signature = unify_type_comments(type_comments)
        arg_types = signature['arg_types']
        return_type = signature['return_type']
        print("    # type: (%s) -> %s" % (", ".join(arg_types), return_type))


def _main(args_override=None):
    # type: (Optional[List[str]]) -> List[str]

    parser = get_parser()
    defaults = load_config(parser)
    parser.set_defaults(**defaults)
    # Parse command line.
    args = parser.parse_args(args_override)

    if not args.files and not args.dump:
        parser.error("At least one file/directory is required")

    annotation_style = args.annotation_style
    if annotation_style == 'auto':
        annotation_style = 'py%d' % sys.version_info[0]

    # Set up logging handler.
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(format='%(message)s', level=level)

    if args.dump:
        dump_annotations(args.type_info, args.files)
        return []

    input_base_dir = crawl_up(os.path.abspath(args.files[0]))[0]

    if args.output_dir:
        input_base_dir = input_base_dir.rstrip(os.sep)
        logging.info('Output in %r will mirror the input directory %r layout.',
                     args.output_dir, input_base_dir)

    if args.write_unchanged_files:
        if not args.write:
            logging.warn("--write-unchanged-files/-W implies -w.")
        args.write = True

    fixers = []  # type: List[str]

    def add_fixer(fixer_cls):
        fixer_cls.run_order = BaseFixAnnotateFromSignature.run_order + len(fixers)
        fixers.append(fixer_cls.__module__)

    if args.type_info:
        # Produce nice error message if type_info.json not found.
        try:
            with open(args.type_info) as f:
                contents = f.read()
        except IOError as err:
            sys.exit("Can't open type info file: %s" % err)

        # Run pass 2 with output into a variable.
        if args.uses_signature:
            data = json.loads(contents)  # type: List[Any]
        else:
            data = generate_annotations_json_string(
                args.type_info,
                only_simple=args.only_simple)

        # Run pass 3 with input from that variable.
        FixAnnotateJson.init_stub_json_from_data(data, args.files)
        add_fixer(FixAnnotateJson)

    if args.command:
        FixAnnotateCommand.set_command(args.command)
        add_fixer(FixAnnotateCommand)

    if args.doc_format not in {None, 'off'}:
        FixAnnotateDocs.set_format(args.doc_format)
        FixAnnotateDocs.set_default_return_type(args.doc_default_return_type)
        add_fixer(FixAnnotateDocs)

    if args.auto_any:
        add_fixer(FixAnnotateAny)

    flags = {
        'write_unchanged_files': args.write_unchanged_files,
        'print_function': args.print_function,
        'annotation_style': annotation_style,
        'comment_style': args.py2_comment_style
    }
    rt = ModifiedRefactoringTool(
        fixers=fixers,
        options=flags,
        explicit=fixers,
        nobackups=True,
        show_diffs=not args.quiet,
        input_base_dir=input_base_dir,
        output_dir=args.output_dir,
    )
    if not rt.errors:
        with BaseFixAnnotateFromSignature.max_line_drift_set(args.max_line_drift):
            rt.refactor(args.files, write=args.write, num_processes=args.processes)
        if args.processes == 1:
            rt.summarize()
        else:
            logging.info("(In multi-process per-file warnings are lost)")
    if not args.write:
        logging.info("NOTE: this was a dry run; use -w to write files")
    return rt.errors


def main(args=None):
    errors = _main(args)
    # Return error status (0 if rt.errors is zero)
    return int(bool(errors))


if __name__ == '__main__':
    sys.exit(main())
