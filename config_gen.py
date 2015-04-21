#!/usr/bin/env python2

import sys
import os
import os.path
import re
import argparse
import datetime
import multiprocessing
import shlex
import shutil
import tempfile
import time
import subprocess


# Default flags for make
default_make_flags = ["-i", "-j" + str(multiprocessing.cpu_count())]


def main():
    # parse command-line args
    parser = argparse.ArgumentParser(description="Automatically generates config files for YouCompleteMe")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show output from build process")
    parser.add_argument("-m", "--make", default="make", help="Use the specified executable for make.")
    parser.add_argument("-c", "--compiler", help="Use the specified executable for clang. It should be the same version as the libclang used by YCM.")
    parser.add_argument("-C", "--configure_opts", default="", help="Additional flags to pass to configure/cmake/etc. e.g. --configure_opts=\"--enable-FEATURE\"")
    parser.add_argument("-M", "--make-flags", help="Flags to pass to make when fake-building. Default: -M=\"{}\"".format(" ".join(default_make_flags)))
    parser.add_argument("-o", "--output", help="Save the config file as OUTPUT instead of .ycm_extra_conf.py.")
    parser.add_argument("--out-of-tree", action="store_true", help="Build autotools projects out-of-tree. This is a no-op for other project types.")
    parser.add_argument("PROJECT_DIR", help="The root directory of the project.")
    args = vars(parser.parse_args())
    project_dir = os.path.abspath(args["PROJECT_DIR"])

    # verify that project_dir exists
    if(not os.path.exists(project_dir)):
        print("ERROR: '{}' does not exist".format(project_dir))
        sys.exit(1)
        return

    # verify the clang is installed
    try:
        args["compiler"] = subprocess.check_output(["which", args["compiler"] or "clang"]).strip()
    except subprocess.CalledProcessError:
        print("ERROR: Could not find clang. Please make sure it is installed and is either in your path, or specified with --compiler.")
        sys.exit(1)
        return

    # sanity check - remove this after we add Windows support
    if(sys.platform.startswith("win32")):
        print("ERROR: Windows is not supported")

    # prompt user to overwrite existing file (if necessary)
    config_file = os.path.join(project_dir, ".ycm_extra_conf.py") if args["output"] is None else args["output"]

    if(os.path.exists(config_file)):
        print("'{}' already exists. Overwrite? [y/N] ".format(config_file)),
        response = sys.stdin.readline().strip().lower()

        if(response != "y" and response != "yes"):
            sys.exit(1)
            return

    # temporary file to hold build log
    (build_log, build_log_path) = tempfile.mkstemp(text=True)
    build_log = os.fdopen(build_log, "rw")

    # pass command-line args to fake_build() using kwargs
    args["make_cmd"] = args.pop("make")
    args["compiler_cmd"] = args.pop("compiler")
    args["configure_opts"] = shlex.split(args["configure_opts"])
    args["make_flags"] = default_make_flags if args["make_flags"] is None else shlex.split(args["make_flags"])
    del args["PROJECT_DIR"]
    del args["output"]

    # perform the actual compilation of flags
    fake_build(project_dir, build_log_path, **args)
    flags = parse_flags(build_log, build_log_path)
    generate_conf(flags, config_file)

    # cleanup
    build_log.close()
    os.remove(build_log_path)


def fake_build(project_dir, build_log_path, verbose, make_cmd, compiler_cmd, out_of_tree, configure_opts, make_flags):
    '''Builds the project using the fake toolchain, to collect the compiler flags.

    project_dir: the directory containing the source files
    build_log_path: the file to log commands to
    verbose: show the build process output
    make_cmd: the path of the make executable
    compiler_cmd: the path of the clang executable
    out_of_tree: perform an out-of-tree build (autotools only)
    configure_opts: additional flags for configure stage
    make_flags: additional flags for make
    '''

    # TODO: add Windows support
    assert(not sys.platform.startswith("win32"))
    fake_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "fake-toolchain", "Unix"))

    # environment variables and arguments for build process
    started = time.time()
    FNULL = open(os.devnull, "w")
    proc_opts = {} if verbose else {
        "stdin": FNULL,
        "stdout": FNULL,
        "stderr": FNULL
    }
    proc_opts["cwd"] = project_dir
    env = {
        "PATH": "{}:{}".format(fake_path, os.environ["PATH"]),
        "CC": "clang",
        "CXX": "clang",
        "YCM_CONFIG_GEN_CC_LOG": build_log_path,
    }
    # used during configuration stage, so that cmake, etc. can verify what the compiler supports
    env_config = env.copy()
    env_config["YCM_CONFIG_GEN_CC_PASSTHROUGH"] = compiler_cmd

    # use -i (ignore errors), since the makefile may include scripts which
    # depend upon the existence of various output files
    make_args = [make_cmd] + make_flags

    # helper function to display exact commands used
    def run(cmd, *args, **kwargs):
        print("$ " + " ".join(cmd))
        subprocess.call(cmd, *args, **kwargs)

    # execute the build system
    if(os.path.exists(os.path.join(project_dir, "CMakeLists.txt"))):
        # Cmake
        # run cmake in a temporary directory, then compile the project as usual
        build_dir = tempfile.mkdtemp()
        proc_opts["cwd"] = build_dir

        print("Running cmake in '{}'...".format(build_dir))
        run(["cmake", project_dir] + configure_opts, env=env_config, **proc_opts)

        print("\nRunning make...")
        run(make_args, env=env, **proc_opts)

        print("\nCleaning up...")
        print("")
        shutil.rmtree(build_dir)

    elif(os.path.exists(os.path.join(project_dir, "configure"))):
        # Autotools
        # perform build in-tree, since not all projects handle out-of-tree builds correctly

        if(out_of_tree):
            build_dir = tempfile.mkdtemp()
            proc_opts["cwd"] = build_dir
            print("Configuring autotools in '{}'...".format(build_dir))
        else:
            print("Configuring autotools...")

        run([os.path.join(project_dir, "configure")] + configure_opts, env=env_config, **proc_opts)

        print("\nRunning make...")
        run(make_args, env=env, **proc_opts)

        print("\nCleaning up...")

        if(out_of_tree):
            print("")
            shutil.rmtree(build_dir)
        else:
            run([make_cmd, "maintainer-clean"], env=env, **proc_opts)

    elif(os.path.exists(os.path.join(project_dir, "Makefile"))):
        # Make
        # needs to be handled last, since other build systems can generate Makefiles
        print("Preparing build directory...")
        run([make_cmd, "clean"], env=env, **proc_opts)

        print("\nRunning make...")
        run(make_args, env=env, **proc_opts)

    else:
        print("ERROR: Unknown build system")
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
    flags_whitelist = ["-[iID].*", "-W[^,]*", "-std=[a-z0-9+]+", "-(no)?std(lib|inc)", "-m[0-9]+"]
    flags_whitelist = re.compile("|".join(map("^{}$".format, flags_whitelist)))
    flags = set()
    empty_log = True

    # Used to only bundle filenames with applicable arguments
    filename_flags = ["-o", "-I", "-isystem", "-include"]

    # Process build log
    for line in build_log:
        empty_log = False

        if(temp_output.search(line)):
            continue

        words = split_flags(line)

        for (i, word) in enumerate(words):
            if(word[0] != '-' or not flags_whitelist.match(word)):
                continue

            # include arguments for this option, if there are any, as a tuple
            if(i != len(words) - 1 and word in filename_flags and words[i + 1][0] != '-'):
                flags.add((word, words[i + 1]))
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
    word_flags = list([f for f in flags if isinstance(f, basestring) and mRegex.match(f)])

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
                    for flag in flags:
                        if(isinstance(flag, basestring)):
                            output.write("    '{}',\n".format(flag))
                        else: # is tuple
                            output.write("    '{}', '{}',\n".format(*flag))

                else:
                    # copy template
                    output.write(line)


def split_flags(line):
    '''Helper method that splits a string into flags.
    Flags are space-seperated, except for spaces enclosed in quotes.
    Returns a list of flags'''

    # Pass 1: split line using whitespace
    words = line.strip().split()

    # Pass 2: merge words so that the no. of quotes is balanced
    res = []

    for w in words:
        if(len(res) > 0 and unbalanced_quotes(res[-1])):
            res[-1] += " " + w
        else:
            res.append(w)

    return res


def unbalanced_quotes(s):
    '''Helper method that returns True if the no. of single or double quotes in s is odd.'''

    single = 0
    double = 0

    for c in s:
        if(c == "'"):
            single += 1
        elif(c == '"'):
            double += 1

    return (single % 2 == 1 or double % 2 == 1)


if(__name__ == "__main__"):
    main()

