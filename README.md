# typeright: Generate Python Type Annotations

Insert PEP 484 type annotations into your python source code.

## Options

typeright currently supports 4 approaches (aka "fixers") for inserting
annotations, listed below.

Multiple fixers can be used in tandem: if an annotation exists, or is
newly added by a previous fixer, all subsequent fixers will skip the location.
The one exception to this is the docstring fixer, which will overwrite existing
annotations if they do not agree with the types found in the docstrings, if any.
In other words, when enabled, the docstrings are considered the source of truth for types.

The fixers are listed below in the order that they are called.

### Read types from a json file

```
json file options:
  Read type info from a json file

  --type-info FILE      JSON input file
  --max-line-drift N    Maximum allowed line drift when inserting annotation (can be useful for custom codecs)
  --uses-signature      JSON input uses a signature format
  -s, --only-simple     Only annotate functions with trivial types
```

If you have a tool that is able to generate type information, you can output
it in a format compatible with typeright and it will insert them as annotations.
The most common case for this would be if you're using
[PyAnnotate](https://github.com/dropbox/pyannotate) to inspect types at
runtime (this project is itself a fork of PyAnnotate, focused solely on annotation
generation).  Another scenario might be generating type info based on doxygen
xml files for a C extension, and adding these to stubs created by mypy's `stubgen`
tool.

### Generate types from a command

```
command options:
  Generate type info by calling an external program

  --command COMMAND, -c COMMAND
                        Command to generate JSON info for a call site

```

With this option, you can use the mypy daemon, `dmypy`, to generate annotations.
This tool will analyze your code to determine likely types for a function
based on the types of objects passed to it throughout your code.

To use this, first start the mypy daemon:

```
dmypy run
```

Next, invoke `typeright` and pass it the command to run:

```
typeright --command='dmypy suggest --json {filename}:{lineno}' path/
```

It will run the given command on any function in `path/` that does not have annotations.
I prefer to also pass `--no-any` to ensure high quality suggestions only.

### Convert types from docstrings

```
docstring options:
  Generate type info by parsing docstrings

  --doc-format {auto,google,numpy,off,rest}
                        Specify the docstring convention used within files to be converted ('auto' automatically determines the format by inspecting each docstring but it is faster and more reliable to specify this explicitly)
  --doc-default-return-type TYPE
                        Default type to use for undocumented return values (defaults to 'Any'
```

Maintaining types in docstrings can be desirable for a few reasons:

- Your project has existing docstrings with types that are already mostly correct
- You find it easier to maintain and comprehend types specified alongside the
  description of an argument

typeright can parse the three major docstring conventions to find type info: [numpy](http://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_numpy.html#example-numpy), [google](http://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html) and [restructuredText](https://thomas-cokelaer.info/tutorials/sphinx/docstring_python.html#template-py-source-file)

Regardless of the docstring convention you choose, the types declared within your
docstrings should following the guidelines in [PEP 484](https://www.python.org/dev/peps/pep-0484/),
especially use of the [`typing`](https://docs.python.org/3/library/typing.html)
module, where necessary.

### Set all types to Any

One approach to typing an exiting project is to start by blanketing your code
with types, so that you can enable `mypy --disallow-untyped-defs`
straight out of the gate. This gets the boilerplate out of the way, and
"encourages" developers to add types to all new modules.

```
any options:
  -a, --auto-any        Annotate everything with 'Any'
```

### Output format options

There are options to control how to generate the type annotations:

```
output format options:
  --annotation-style {auto,py2,py3}
                        Choose annotation style, py2 for Python 2 with comments, py3 for Python 3 with annotation syntax. The default will be determined by the version of the current python interpreter
  --py2-comment-style {auto,multi,single}
                        Choose comment style, multi adds a comment per argument, single produces one type comment for all arguments, and auto chooses between the two styles based on the number of arguments and length of comments
```

### Other options

```
other options:
  -p, --print-function  Assume print is a function
  -w, --write           Write output files
  -j N, --processes N   Use N parallel processes (default no parallelism)
  -v, --verbose         More verbose output
  -q, --quiet           Don't show diffs
  -o OUTPUT_DIR, --output-dir OUTPUT_DIR
                        Put output files in this directory instead of overwriting the input files
  -W, --write-unchanged-files
                        Also write files even if no changes were required (useful with --output-dir); implies -w.
```

## Configuration

typeright will read defaults from a configuration file named `typeright.ini`,
or `setup.cfg` in the current directory.

For example:

```ini
[typeright]
files = typeright

command = dmypy suggest --json --no-any {filename}:{lineno}
docstring_format = numpy
write = true
```

## Installation

This should work for Python 2.7 as well as for Python 3.6 and higher.

```
pip install typeright
```

## Using as a pre-commit hook

We use [pre-commit](https://pre-commit.com/) to fixup code prior to committing
or pushing.

To set it up, `cd` to this repo and run:
```
pip install pre-commit
pre-commit install
```

To manually run pre-commit on staged files:

```
pre-commit run
```

To manually run pre-commit on all files:
```
pre-commit run -a
```

## Testing

To run the unit tests, use pytest:

```
pytest
```

## Acknowledgments

This project was forked from PyAnnotate, after some encouragement from
Guido van Rossum, because PyAnnotate is no longer being actively maintained.

Here are the original acknowledgments:

- Tony Grue
- Sergei Vorobev
- Jukka Lehtosalo
- Guido van Rossum

## Licence etc.

1. License: Apache 2.0.
2. Copyright attribution: Copyright (c) 2017 Dropbox, Inc, and Chad Dombrova 2020.
