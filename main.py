#!/usr/bin/env python

'''Sam's Impractical Baserock Definitions to CMake Exporter.'''


import morphlib

import argparse
import collections
import logging
import os
import sys


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


CMAKE_SETUP = """
cmake_minimum_required(VERSION 3.3)

include(ExternalProject)

set(GIT_BASEROCK git://git.baserock.org/baserock)
set(GIT_UPSTREAM git://git.baserock.org/delta)

"""


def format_cmake_command(command, args = [], keyword_args = {}):
    def escape(string):
        return string.replace('\\', '\\\\')

    first_line = ' '.join([command + '('] + [escape(arg) for arg in args])

    if len(keyword_args) == 0:
        first_line += ')\n'
        return first_line
    else:
        lines = [first_line]
        for key, value in keyword_args.items():
            lines.append('    %s' % key)
            lines.append('        %s' % escape(value))
        lines.append('    )')
        return '\n'.join(lines)


def write_cmake_target_for_source(source, cmakelists_stream, scripts_dir):
    def resolve_repo_alias(repo_url):
        mapping = {
            'baserock:': '${GIT_BASEROCK}/',
            'upstream:': '${GIT_UPSTREAM}/',
        }
        for key, value in mapping.items():
            if repo_url.startswith(key):
                return value + repo_url[len(key):]
        return repo_url

    def depends(source):
        dep_sources = set()
        for dep_artifact in source.dependencies:
            dep_sources.add(dep_artifact.source)
        return ' '.join([source.name for source in dep_sources])

    def command_sequence(source, step):
        pre = source.morphology.get('pre-%s-commands' % step, [])
        commands = source.morphology.get('%s-commands' % step, [])
        post = source.morphology.get('post-%s-commands' % step, [])

        return pre + commands + post

    def can_inline_command_in_cmake(command):
        MAX_LENGTH = 255
        AWKWARD_CHARS = ['(', ')', '\\']
        if len(command) > MAX_LENGTH:
            return False
        else:
            for char in AWKWARD_CHARS:
                if char in command:
                    return False
        return True

    keyword_args = collections.OrderedDict()

    keyword_args['GIT_REPOSITORY'] = resolve_repo_alias(source.repo_name)
    keyword_args['GIT_TAG'] = source.sha1

    for step in ['configure', 'build', 'install']:
        sequence = command_sequence(source, step)
        if len(sequence) > 0:
            command = ' && '.join(sequence)
            if can_inline_command_in_cmake(command):
                keyword_args['%s_COMMAND' % step.upper()] = command
            else:
                script_name = '%s-%s.sh' % (source.name, step)
                keyword_args['%s_COMMAND' % step.upper()] = script_name
                with open(os.path.join(scripts_dir, script_name), 'w') as f:
                    f.write('# %s commands for %s\n' % (step, source.name))
                    for command in sequence:
                        f.write(command + '\n')

    keyword_args['DEPENDS'] =  depends(source)

    text = format_cmake_command(
        'ExternalProject_Add', args=[source.name], keyword_args=keyword_args)

    cmakelists_stream.write(text)
    cmakelists_stream.write('\n')


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

        root_artifact = find_artifact_by_name(root_artifacts,
                                              definition_file)

        with open(os.path.join(args.output_dir, 'CMakeLists.txt'), 'w') as f:
            f.write(CMAKE_SETUP)

            order = morphlib.buildcommand.BuildCommand.get_ordered_sources(
                root_artifact.walk())

            for source in order:
                write_cmake_target_for_source(source, cmakelists_stream=f,
                                              scripts_dir=args.output_dir)
                f.write('\n')

main()
