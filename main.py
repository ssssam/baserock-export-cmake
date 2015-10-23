#!/usr/bin/env python


import morphlib

import argparse
import logging
import os
import sys


CACHE_DIR = '/home/shared/baserock-chroot-build/cache'

def argument_parser():
    parser = argparse.ArgumentParser(
        description="Baserock -> CMake converter")
    parser.add_argument(
        'definition_file', type=str, metavar='DEFINITION_FILE')
    return parser


def work_around_bad_morphlib_api():
    # This should be unnecessary once we have a better library for parsing
    # definitions! Until then ...
    class FakeApp(object):
        settings = {'no-git-update': True}
        def status(*args, **kwargs): pass
    resolver = morphlib.repoaliasresolver.RepoAliasResolver(aliases=[])
    lrc = morphlib.localrepocache.LocalRepoCache(
        FakeApp(), os.path.join(CACHE_DIR, 'gits'), resolver)
    return lrc


def main():
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

    args = argument_parser().parse_args()

    lrc = work_around_bad_morphlib_api()

    # FIXME: morphlib limitations means the definitions must be in a
    # git repo
    definitions_repo_dir = morphlib.util.find_root(
        os.path.dirname(args.definition_file), '.git')
    definition_file = os.path.relpath(
        args.definition_file, start=definitions_repo_dir)

    definitions_repo = morphlib.definitions_repo.open(
        os.path.dirname(args.definition_file))
    source_pool_context = definitions_repo.source_pool(
        lrc=lrc, rrc=None, cachedir=CACHE_DIR, ref='HEAD',
        system_filename=definition_file)
    with source_pool_context as source_pool:
        pass


main()
