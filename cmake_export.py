import morphlib

import collections
import os

CMAKE_SETUP = """cmake_minimum_required(VERSION 3.3)

include(ExternalProject)

set(GIT_BASEROCK git://git.baserock.org/baserock)
set(GIT_UPSTREAM git://git.baserock.org/delta)

"""


def format_cmake_command(command, args=[], keyword_args={}):
    def escape(string):
        return string.replace('\\', '\\\\')

    first_line = command + '('
    first_line += ' '.join(escape(arg) + ' ' for arg in args).strip()

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
        # See "Definitions File Syntax -- Repo URLs" at
        # <http://wiki.baserock.org/definitions/current/#index5h3>
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
        return ' '.join([s.name for s in dep_sources])

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
        keyword = '%s_COMMAND' % step.upper()
        sequence = command_sequence(source, step)
        if len(sequence) == 0:
            # If we don't supply any command, the default is to try and
            # configure/build/install with CMake, rather than to do nothing.
            keyword_args[keyword] = 'echo no-op'
        else:
            command = ' && '.join(sequence)
            if can_inline_command_in_cmake(command):
                keyword_args[keyword] = command
            else:
                script_name = '%s-%s.sh' % (source.name, step)
                keyword_args[keyword] = 'sh ${CMAKE_CURRENT_SOURCE_DIR}/' + script_name
                with open(os.path.join(scripts_dir, script_name), 'w') as f:
                    f.write('# %s commands for %s\n' % (step, source.name))
                    for command in sequence:
                        f.write(command + '\n')

    keyword_args['DEPENDS'] =depends(source)

    text = format_cmake_command(
        'ExternalProject_Add', args=[source.name], keyword_args=keyword_args)

    cmakelists_stream.write(text)
    cmakelists_stream.write('\n')


def do_export_for_one_component(source, component_dir):
    component_cmakelists = os.path.join(component_dir, 'CMakeLists.txt')

    with open(component_cmakelists, 'w') as f:
        write_cmake_target_for_source(
            source, cmakelists_stream=f,
            scripts_dir=component_dir)


def do_export(root_artifact, group_name, output_dir):
    component_base_dir = os.path.join(output_dir, group_name)

    if not os.path.exists(component_base_dir):
        os.makedirs(component_base_dir)

    toplevel_cmakelists = os.path.join(component_base_dir, 'CMakeLists.txt')

    with open(toplevel_cmakelists, 'w') as f:
        f.write(CMAKE_SETUP)

        order = morphlib.buildcommand.BuildCommand.get_ordered_sources(
            root_artifact.walk())

        for source in order:
            component_name = source.name
            component_dir = os.path.join(component_base_dir, component_name)

            if not os.path.exists(component_dir):
                os.mkdir(component_dir)

            do_export_for_one_component(source, component_dir)

            f.write('add_subdirectory(%s)\n' % component_name)


