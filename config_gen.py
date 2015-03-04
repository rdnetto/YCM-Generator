#!/usr/bin/env python2

import sys
import os
import os.path
import re
import datetime
import multiprocessing
import tempfile
import time
import subprocess


def main():
    # display usage info
    if(len(sys.argv) != 2):
        print "USAGE: ./config_gen.py PROJECT_DIR"
        sys.exit(1)
        return
    else:
        project_dir = os.path.abspath(sys.argv[1])

        if(not os.path.exists(project_dir)):
            print("ERROR: '{}' does not exist".format(project_dir))
            sys.exit(1)
            return

    # sanity check - remove this after we add Windows support
    if(sys.platform.startswith("win32")):
        print("ERROR: Windows is not supported")

    # prompt user to overwrite existing file (if necessary)
    config_file = os.path.join(project_dir, ".ycm_extra_conf.py")

    if(os.path.exists(config_file)):
        print("'{}' already exists. Overwrite? [y/N]".format(config_file))
        response = sys.stdin.readline().strip().lower()

        if(response != "y" and response != "yes"):
            sys.exit(1)
            return

    # temporary file to hold build log
    (build_log, build_log_path) = tempfile.mkstemp(text=True)
    build_log = os.fdopen(build_log, "rw")

    fake_build(project_dir, build_log_path)
    flags = parse_flags(build_log, build_log_path)
    generate_conf(flags, config_file)

    # cleanup
    build_log.close()
    os.remove(build_log_path)


def fake_build(project_dir, build_log_path):
    '''Builds the project using the fake toolchain, to collect the compiler flags.'''

    # TODO: add Windows support
    assert(not sys.platform.startswith("win32"))
    fake_path = os.path.join(os.path.dirname(__file__), "fake-toolchain", "Unix")

    # environment variables for build process
    started = time.time()
    env = {"PATH" : "{}:{}".format(fake_path, os.environ["PATH"]),
           "CC" : "clang",
           "CXX" : "clang",
           "YCM_CONFIG_GEN_LOG" : build_log_path,
          }

    # execute the build system
    if(os.path.exists(os.path.join(project_dir, "Makefile"))):
        print "Running make..."

        # use --ignore-errors, since the makefile may include scripts which
        # depend upon the existence of various output files
        args = ["make", "--ignore-errors", "-j" + str(multiprocessing.cpu_count())]

        with open(os.devnull, "w") as FNULL:
            subprocess.call(["make", "clean"], stdin=FNULL, stdout=FNULL, stderr=FNULL, cwd=project_dir, env=env)
            subprocess.call(args, stdin=FNULL, stdout=FNULL, stderr=FNULL, cwd=project_dir, env=env)

    else:
        print "ERROR: Unknown build system"
        sys.exit(2)

    print("Build completed in {} sec".format(round(time.time() - started, 2)))


def parse_flags(build_log, build_log_path):
    '''Creates a list of compiler flags from the build log.
    build_log: an iterator of lines
    Returns: a list of flags'''

    # Used to ignore entries which result in temporary files, or don't fully
    # compile the file
    temp_output = re.compile("-S|-E|-x assembler|-o ([a-zA-Z0-9._].tmp)|(/dev/null)")

    # Flags we want:
    # -includes (-i, -I)
    # -defines (-D)
    # -warnings (-Werror), but no assembler, etc. flags (-Wa,-option)
    # -language (-std=gnu99) and standard library (-nostdlib)
    # -word size (-m64)
    flags_whitelist = ["-[iID].*", "-W[^,]*", "-.*std.*", "-m[0-9]+"]
    flags_whitelist = re.compile("|".join(map("^{}$".format, flags_whitelist)))
    flags = set()
    empty_log = True


    # Process build log
    for line in build_log:
        empty_log = False

        if(temp_output.search(line)):
            continue

        words = line.split()

        for (i, word) in enumerate(words):
            if(word[0] != '-' or not flags_whitelist.match(word)):
                continue

            # include arguments for this option, if there are any
            if(i != len(words) - 1 and words[i + 1][0] != '-'):
                flags.add(word + ' ' + words[i + 1])
            else:
                flags.add(word)

    # sanity check
    if(empty_log):
        print("ERROR: No commands were logged to the build log ({}).".format(build_log_path))
        print("Your build system may not be compatible.")
        sys.exit(3)

    # Only specify one word size (the largest)
    # (Different sizes are used for different files in the linux kernel.)
    mRegex = re.compile("^-m[0-9]+$")
    word_flags = list([f for f in flags if mRegex.match(f)])

    if(len(word_flags) > 1):
        for flag in word_flags:
            flags.remove(flag)

        flags.add(max(word_flags))

    return sorted(flags)


def generate_conf(flags, config_file):
    '''Generates the .ycm_extra_conf.py.

    flags: the list of flags
    config_file: the path to save the configuration file at'''

    template_file = os.path.join(os.path.dirname(__file__), "template.py")

    with open(template_file, "r") as template:
        with open(config_file, "w") as output:
            output.write("# Generated by YCM Generator at {}\n\n".format(str(datetime.datetime.today())))

            for line in template:
                if(line == "    # INSERT FLAGS HERE\n"):
                    # insert generated code
                    output.writelines("    '{}',\n".format(flag) for flag in flags)
                else:
                    # copy template
                    output.write(line)



if(__name__ == "__main__"):
    main()

