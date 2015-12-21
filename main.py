#!/usr/bin/env python

'''Sam's Impractical Baserock Definitions to CMake Exporter.'''


import morphlib

import argparse
import os

import cmake_export


CACHE_DIR = '/home/shared/baserock-chroot-build/cache'


def argument_parser():
    '''Create commandline argument parser object.'''
    parser = argparse.ArgumentParser(
        description="Baserock -> CMake converter")
    parser.add_argument(
        'definition_file', type=str, metavar='DEFINITION_FILE')
    parser.add_argument(
        'output_dir', type=str, metavar='OUTPUT_DIR')
    return parser


def work_around_bad_morphlib_api():
    '''Various workarounds to pretend that 'morphlib' is a reusable library.

    This should be unnecessary once we have a dedicated Python library for
    parsing Baserock definitions!

    '''
    class FakeApp(object):
        settings = {'no-git-update': True}
        def status(*args, **kwargs): pass
    resolver = morphlib.repoaliasresolver.RepoAliasResolver(aliases=[])
    lrc = morphlib.localrepocache.LocalRepoCache(
        FakeApp(), os.path.join(CACHE_DIR, 'gits'), resolver)
    return lrc


def main():
    #logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

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
        # This is all from morphlib list_artifacts plugin ... no need to
        # duplicate it all here
        resolver = morphlib.artifactresolver.ArtifactResolver()
        root_artifacts = resolver.resolve_root_artifacts(source_pool)

        def find_artifact_by_name(artifacts_list, filename):
            for a in artifacts_list:
                if a.source.filename == filename:
                    return a
            raise ValueError

        toplevel_group_artifact = find_artifact_by_name(root_artifacts,
                                              definition_file)
        toplevel_group_name = toplevel_group_artifact.source.morphology['name']
        cmake_export.do_export(toplevel_group_artifact, toplevel_group_name,
                               args.output_dir)


main()
