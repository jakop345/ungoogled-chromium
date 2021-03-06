#!/usr/bin/env python3

# ungoogled-chromium: A Google Chromium variant for removing Google integration and
# enhancing privacy, control, and transparency
# Copyright (C) 2016  Eloston
#
# This file is part of ungoogled-chromium.
#
# ungoogled-chromium is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ungoogled-chromium is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ungoogled-chromium.  If not, see <http://www.gnu.org/licenses/>.

'''
Script to ease updating to a new version of Chromium

This script is hacky. Tested on Debian.
'''

import pathlib
import os
import re
import sys

if not pathlib.Path("buildlib").is_dir():
    print("ERROR: Run this in the same directory as 'buildlib'")
    exit(1)

sys.path.insert(1, str(pathlib.Path.cwd().resolve()))

import buildlib
import buildlib.common
import buildlib.linux

def generate_cleaning_list(sandbox_path, list_file):
    exclude_matches = [
        "components/dom_distiller/core/data/distillable_page_model.bin",
        "components/dom_distiller/core/data/distillable_page_model_new.bin",
        "components/dom_distiller/core/data/long_page_model.bin",
        "*.ttf",
        "*.png",
        "*.jpg",
        "*.webp",
        "*.gif",
        "*.ico",
        "*.mp3",
        "*.wav",
        "*.icns",
        "*.woff",
        "*.woff2",
        "*Makefile",
        "*makefile",
        "*.xcf",
        "*.cur",
        "*.pdf",
        "*.ai",
        "*.h",
        "*.c",
        "*.cpp",
        "*.cc",
        "*.mk",
        "*.bmp",
        "*.py",
        "*.xml",
        "*.html",
        "*.js",
        "*.json",
        "*.txt",
        "*.TXT",
        "*.xtb"
    ]
    include_matches = [
        "components/domain_reliability/baked_in_configs/*"
    ]
    # From: http://stackoverflow.com/questions/898669/how-can-i-detect-if-a-file-is-binary-non-text-in-python
    textchars = bytearray({7,8,9,10,12,13,27} | set(range(0x20, 0x100)) - {0x7f})
    is_binary_string = lambda bytes: bool(bytes.translate(None, textchars))

    cleaning_list = set()
    old_dir = str(pathlib.Path.cwd())
    os.chdir(str(sandbox_path))
    try:
        for i in pathlib.Path().rglob("*"):
            if not i.is_file():
                continue
            found_match = False
            for pattern in include_matches:
                if i.match(pattern):
                    cleaning_list.add(str(i))
                    break
            if found_match:
                continue
            for pattern in exclude_matches:
                if i.match(pattern):
                    found_match = True
                    break
            if not found_match:
                with i.open("rb") as f:
                    if is_binary_string(f.read()):
                        cleaning_list.add(str(i))
    finally:
        os.chdir(old_dir)
    cleaning_list = sorted(cleaning_list)
    with list_file.open("w") as f:
        f.write("\n".join(cleaning_list))
    return cleaning_list

def check_regex_match(file_path, parsed_regex_list):
    with file_path.open("rb") as f:
        content = f.read()
        for regex in parsed_regex_list:
            if not regex.search(content) is None:
                return True
    return False

def generate_domain_substitution_list(sandbox_path, list_file, regex_defs):
    exclude_left_matches = [
        "components/test/",
        "net/http/transport_security_state_static.json"
    ]
    include_matches = [
        "*.h",
        "*.hh",
        "*.hpp",
        "*.hxx",
        "*.cc",
        "*.cpp",
        "*.cxx",
        "*.c",
        "*.h",
        "*.json",
        "*.js",
        "*.html",
        "*.htm",
        "*.py*",
        "*.grd",
        "*.sql",
        "*.idl",
        "*.mk",
        "*.gyp*",
        "Makefile",
        "makefile",
        "*.txt",
        "*.xml",
        "*.mm",
        "*.jinja*"
    ]

    parsed_regex_list = set()
    with regex_defs.open(mode="rb") as f:
        for expression in f.read().splitlines():
            if not expression == "":
                parsed_regex_list.add(re.compile(expression.split(b'#')[0]))

    domain_substitution_list = set()
    old_dir = str(pathlib.Path.cwd())
    os.chdir(str(sandbox_path))
    try:
        for i in pathlib.Path().rglob("*"):
            if not i.is_file():
                continue
            if i.is_symlink():
                continue
            for include_pattern in include_matches:
                if i.match(include_pattern):
                    found_match = False
                    for exclude_pattern in exclude_left_matches:
                        if str(i).startswith(exclude_pattern):
                            found_match = True
                            break
                    if found_match:
                        break
                    elif check_regex_match(i, parsed_regex_list):
                        domain_substitution_list.add(str(i))
                        break
    finally:
        os.chdir(old_dir)
    domain_substitution_list = sorted(domain_substitution_list)
    with list_file.open("w") as f:
        f.write("\n".join(domain_substitution_list))

def main():
    builder = buildlib.linux.LinuxStaticBuilder()
    builder.run_source_cleaner = False
    logger = builder.logger
    builder.check_build_environment()
    logger.info("Setting up Chromium source in build sandbox...")
    builder.setup_chromium_source()

    logger.info("Generating cleaning list...")
    cleaning_list = generate_cleaning_list(builder._sandbox_dir, (buildlib.common.Builder._resources / buildlib.common.CLEANING_LIST))

    logger.info("Removing files in cleaning list...")
    for i in cleaning_list:
        if (builder._sandbox_dir / pathlib.Path(i)).exists():
            (builder._sandbox_dir / pathlib.Path(i)).unlink()
        else:
            logger.error("File does not exist: {}".format(str(i)))

    logger.info("Generating domain substitution list...")
    generate_domain_substitution_list(builder._sandbox_dir, (buildlib.common.Builder._resources / buildlib.common.DOMAIN_SUBSTITUTION_LIST), (buildlib.common.Builder._resources / buildlib.common.DOMAIN_REGEX_LIST)) # TODO: Autogenerate platform domain substutition list when platforms have their own domain substitutions

    logger.info("Running domain substitution...")
    builder.setup_build_sandbox()

    logger.info("Done.")

    return 0

if __name__ == "__main__":
    exit(main())
