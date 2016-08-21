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
import glob


# Default flags for make
default_make_flags = ["-i", "-j" + str(multiprocessing.cpu_count())]

# Set YCM-Generator directory
# Always obtain the real path to the directory where 'config_gen.py' lives as,
# in some cases, it will be a symlink placed in '/usr/bin' (as is the case
# with the Arch Linux AUR package) and it won't
# be able to find the plugin directory.
ycm_generator_dir = os.path.dirname(os.path.realpath(__file__))


def main():
    # parse command-line args
    parser = argparse.ArgumentParser(description="Automatically generates config files for YouCompleteMe")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show output from build process")
    parser.add_argument("-f", "--force", action="store_true", help="Overwrite the file if it exists.")
    parser.add_argument("-m", "--make", default="make", help="Use the specified executable for make.")
    parser.add_argument("-b", "--build-system", choices=["cmake", "autotools", "qmake", "make"], help="Force use of the specified build system rather than trying to autodetect.")
    parser.add_argument("-c", "--compiler", help="Use the specified executable for clang. It should be the same version as the libclang used by YCM. The executable for clang++ will be inferred from this.")
    parser.add_argument("-C", "--configure_opts", default="", help="Additional flags to pass to configure/cmake/etc. e.g. --configure_opts=\"--enable-FEATURE\"")
    parser.add_argument("-F", "--format", choices=["ycm", "cc"], default="ycm", help="Format of output file (YouCompleteMe or color_coded). Default: ycm")
    parser.add_argument("-M", "--make-flags", help="Flags to pass to make when fake-building. Default: -M=\"{}\"".format(" ".join(default_make_flags)))
    parser.add_argument("-o", "--output", help="Save the config file as OUTPUT. Default: .ycm_extra_conf.py, or .color_coded if --format=cc.")
    parser.add_argument("-x", "--language", choices=["c", "c++"], help="Only output flags for the given language. This defaults to whichever language has its compiler invoked the most.")
    parser.add_argument("--out-of-tree", action="store_true", help="Build autotools projects out-of-tree. This is a no-op for other project types.")
    parser.add_argument("--qt-version", choices=["4", "5"], default="5", help="Use the given Qt version for qmake. (Default: 5)")
    parser.add_argument("-e", "--preserve-environment", action="store_true", help="Pass environment variables to build processes.")
    parser.add_argument("PROJECT_DIR", help="The root directory of the project.")
    args = vars(parser.parse_args())
    project_dir = os.path.abspath(args["PROJECT_DIR"])

    # verify that project_dir exists
    if(not os.path.exists(project_dir)):
        print("ERROR: '{}' does not exist".format(project_dir))
        return 1

    # verify the clang is installed, and infer the correct name for both the C and C++ compilers
    try:
        cc = args["compiler"] or "clang"
        args["cc"] = subprocess.check_output(["which", cc]).strip()
    except subprocess.CalledProcessError:
        print("ERROR: Could not find clang at '{}'. Please make sure it is installed and is either in your path, or specified with --compiler.".format(cc))
        return 1

    try:
        h, t = os.path.split(args["compiler"] or "clang")
        cxx = os.path.join(h, t.replace("clang", "clang++"))
        args["cxx"] = subprocess.check_output(["which", cxx]).strip()
    except subprocess.CalledProcessError:
        print("ERROR: Could not find clang++ at '{}'. Please make sure it is installed and specified appropriately.".format(cxx))
        return 1

    # sanity check - remove this after we add Windows support
    if(sys.platform.startswith("win32")):
        print("ERROR: Windows is not supported")

    # prompt user to overwrite existing file (if necessary)
    config_file = {
        None:  args["output"],
        "cc":  os.path.join(project_dir, ".color_coded"),
        "ycm": os.path.join(project_dir, ".ycm_extra_conf.py"),
    }[args["format"] if args["output"] is None else None]

    if(os.path.exists(config_file) and not args["force"]):
        print("'{}' already exists. Overwrite? [y/N] ".format(config_file)),
        response = sys.stdin.readline().strip().lower()

        if(response != "y" and response != "yes"):
            return 1

    # command-line args to pass to fake_build() using kwargs
    args["make_cmd"] = args.pop("make")
    args["configure_opts"] = shlex.split(args["configure_opts"])
    args["make_flags"] = default_make_flags if args["make_flags"] is None else shlex.split(args["make_flags"])
    force_lang = args.pop("language")
    output_format = args.pop("format")
    del args["compiler"]
    del args["force"]
    del args["output"]
    del args["PROJECT_DIR"]

    generate_conf = {
        "ycm": generate_ycm_conf,
        "cc":  generate_cc_conf,
    }[output_format]

    # temporary files to hold build logs
    with tempfile.NamedTemporaryFile(mode="rw") as c_build_log:
        with tempfile.NamedTemporaryFile(mode="rw") as cxx_build_log:
            # perform the actual compilation of flags
            fake_build(project_dir, c_build_log.name, cxx_build_log.name, **args)
            (c_count, c_skip, c_flags) = parse_flags(c_build_log)
            (cxx_count, cxx_skip, cxx_flags) = parse_flags(cxx_build_log)

            print("Collected {} relevant entries for C compilation ({} discarded).".format(c_count, c_skip))
            print("Collected {} relevant entries for C++ compilation ({} discarded).".format(cxx_count, cxx_skip))

            # select the language to compile for. If -x was used, zero all other options (so we don't need to repeat the error code)
            if(force_lang == "c"):
                cxx_count = 0
            elif(force_lang == "c++"):
                c_count = 0

            if(c_count == 0 and cxx_count == 0):
                print("")
                print("ERROR: No commands were logged to the build logs (C: {}, C++: {}).".format(c_build_log.name, cxx_build_log.name))
                print("Your build system may not be compatible.")

                if(not args["verbose"]):
                    print("")
                    print("Try running with the --verbose flag to see build system output - the most common cause of this is a hardcoded compiler path.")

                c_build_log.delete = False
                cxx_build_log.delete = False
                return 3

            elif(c_count > cxx_count):
                lang, flags = ("c", c_flags)
            else:
                lang, flags = ("c++", cxx_flags)

            generate_conf(["-x", lang] + flags, config_file)
            print("Created {} config file with {} {} flags".format(output_format.upper(), len(flags), lang.upper()))


def fake_build(project_dir, c_build_log_path, cxx_build_log_path, verbose, make_cmd, build_system, cc, cxx, out_of_tree, configure_opts, make_flags, preserve_environment, qt_version):
    '''Builds the project using the fake toolchain, to collect the compiler flags.

    project_dir: the directory containing the source files
    build_log_path: the file to log commands to
    verbose: show the build process output
    make_cmd: the path of the make executable
    cc: the path of the clang executable
    cxx: the path of the clang++ executable
    out_of_tree: perform an out-of-tree build (autotools only)
    configure_opts: additional flags for configure stage
    make_flags: additional flags for make
    preserve_environment: pass environment variables to build processes
    qt_version: The Qt version to use when building with qmake.
    '''

    # TODO: add Windows support
    assert(not sys.platform.startswith("win32"))
    fake_path = os.path.join(ycm_generator_dir, "fake-toolchain", "Unix")

    # environment variables and arguments for build process
    started = time.time()
    FNULL = open(os.devnull, "w")
    proc_opts = {} if verbose else {
        "stdin": FNULL,
        "stdout": FNULL,
        "stderr": FNULL
    }
    proc_opts["cwd"] = project_dir

    if(preserve_environment):
        env = os.environ
    else:
        # Preserve HOME, since Cmake needs it to find some packages and it's
        # normally there anyway. See #26.
        env = dict(map(lambda x: (x, os.environ[x]), ["HOME"]))

    env["PATH"]  = "{}:{}".format(fake_path, os.environ["PATH"])
    env["CC"] = "clang"
    env["CXX"] = "clang++"
    env["YCM_CONFIG_GEN_CC_LOG"] = c_build_log_path
    env["YCM_CONFIG_GEN_CXX_LOG"] = cxx_build_log_path

    # used during configuration stage, so that cmake, etc. can verify what the compiler supports
    env_config = env.copy()
    env_config["YCM_CONFIG_GEN_CC_PASSTHROUGH"] = cc
    env_config["YCM_CONFIG_GEN_CXX_PASSTHROUGH"] = cxx

    # use -i (ignore errors), since the makefile may include scripts which
    # depend upon the existence of various output files
    make_args = [make_cmd] + make_flags

    # Used for the qmake build system below
    pro_files = glob.glob(os.path.join(project_dir, "*.pro"))

    # sanity check - make sure the toolchain is available
    assert os.path.exists(fake_path), "Could not find toolchain at '{}'".format(fake_path)

    # helper function to display exact commands used
    def run(cmd, *args, **kwargs):
        print("$ " + " ".join(cmd))
        subprocess.call(cmd, *args, **kwargs)

    if build_system is None:
        if os.path.exists(os.path.join(project_dir, "CMakeLists.txt")):
            build_system = "cmake"
        elif os.path.exists(os.path.join(project_dir, "configure")):
            build_system = "autotools"
        elif pro_files:
            build_system = "qmake"
        elif any([os.path.exists(os.path.join(project_dir, x)) for x in ["GNUmakefile", "makefile", "Makefile"]]):
            build_system = "make"

    # execute the build system
    if build_system == "cmake":
        # cmake
        # run cmake in a temporary directory, then compile the project as usual
        build_dir = tempfile.mkdtemp()
        proc_opts["cwd"] = build_dir

        # if the project was built in-tree, we need to hide the cache file so that cmake
        # populates the build dir instead of just re-generating the existing files
        cache_path = os.path.join(project_dir, "CMakeCache.txt")

        if(os.path.exists(cache_path)):
            fd, cache_tmp = tempfile.mkstemp()
            os.close(fd)
            shutil.move(cache_path, cache_tmp)
        else:
            cache_tmp = None

        print("Running cmake in '{}'...".format(build_dir))
        sys.stdout.flush()
        run(["cmake", project_dir] + configure_opts, env=env_config, **proc_opts)

        print("\nRunning make...")
        sys.stdout.flush()
        run(make_args, env=env, **proc_opts)

        print("\nCleaning up...")
        print("")
        sys.stdout.flush()
        shutil.rmtree(build_dir)

        if(cache_tmp):
            shutil.move(cache_tmp, cache_path)

    elif build_system == "autotools":
        # autotools
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

    elif build_system == "qmake":
        # qmake
        # make sure there is only one .pro file
        if len(pro_files) != 1:
            print("ERROR: Found {} .pro files (expected one): {}.".format(
                len(pro_files), ', '.join(pro_files)))
            sys.exit(1)

        # run qmake in a temporary directory, then compile the project as usual
        build_dir = tempfile.mkdtemp()
        proc_opts["cwd"] = build_dir
        env_config["QT_SELECT"] = qt_version

        # QMAKESPEC is platform dependent - valid mkspecs are in
        # /usr/share/qt4/mkspecs, /usr/lib64/qt5/mkspecs
        env_config["QMAKESPEC"] = {
            ("Linux",  True):   "unsupported/linux-clang",
            ("Linux",  False):  "linux-clang",
            ("Darwin", True):   "unsupported/macx-clang",
            ("Darwin", False):  "macx-clang",
            ("FreeBSD", False): "unsupported/freebsd-clang",
        }[(os.uname()[0], qt_version == "4")]

        print("Running qmake in '{}' with Qt {}...".format(build_dir, qt_version))
        run(["qmake"] + configure_opts + [pro_files[0]], env=env_config,
            **proc_opts)

        print("\nRunning make...")
        run(make_args, env=env, **proc_opts)

        print("\nCleaning up...")
        print("")
        shutil.rmtree(build_dir)

    elif build_system == "make":
        # make
        # needs to be handled last, since other build systems can generate Makefiles
        print("Preparing build directory...")
        run([make_cmd, "clean"], env=env, **proc_opts)

        print("\nRunning make...")
        run(make_args, env=env, **proc_opts)

    elif(os.path.exists(os.path.join(project_dir, "Make/options"))):
        print("Found OpenFOAM Make/options")

        # OpenFOAM build system
        make_args = ["wmake"]

        # Since icpc could not find directory in which g++ resides,
        # set environmental variables to gcc to make fake_build operate normally.

        env['WM_COMPILER']='Gcc'
        env['WM_CC']='gcc'
        env['WM_CXX']='g++'

        print("\nRunning wmake...")
        run(make_args, env=env, **proc_opts)

    else:
        print("ERROR: Unknown build system")
        sys.exit(2)

    print("Build completed in {} sec".format(round(time.time() - started, 2)))
    print("")


def parse_flags(build_log):
    '''Creates a list of compiler flags from the build log.

    build_log: an iterator of lines
    Returns: (line_count, skip_count, flags)
    flags is a list, and the counts are integers
    '''

    # Used to ignore entries which result in temporary files, or don't fully
    # compile the file
    temp_output = re.compile("(-x assembler)|(-o ([a-zA-Z0-9._].tmp))|(/dev/null)")
    skip_count = 0

    # Flags we want:
    # -includes (-i, -I)
    # -defines (-D)
    # -warnings (-Werror), but no assembler, etc. flags (-Wa,-option)
    # -language (-std=gnu99) and standard library (-nostdlib)
    # -word size (-m64)
    flags_whitelist = ["-[iIDF].*", "-W[^,]*", "-std=[a-z0-9+]+", "-(no)?std(lib|inc)", "-m[0-9]+"]
    flags_whitelist = re.compile("|".join(map("^{}$".format, flags_whitelist)))
    flags = set()
    line_count = 0

    # macro definitions should be handled separately, so we can resolve duplicates
    define_flags = dict()
    define_regex = re.compile("-D([a-zA-Z0-9_]+)=(.*)")

    # Used to only bundle filenames with applicable arguments
    filename_flags = ["-o", "-I", "-isystem", "-iquote", "-include", "-imacros", "-isysroot"]

    # Process build log
    for line in build_log:
        if(temp_output.search(line)):
            skip_count += 1
            continue

        line_count += 1
        words = split_flags(line)

        for (i, word) in enumerate(words):
            if(word[0] != '-' or not flags_whitelist.match(word)):
                continue

            # handle macro definitions
            m = define_regex.match(word)
            if(m):
                if(m.group(1) not in define_flags):
                    define_flags[m.group(1)] = [m.group(2)]
                elif(m.group(2) not in define_flags[m.group(1)]):
                    define_flags[m.group(1)].append(m.group(2))

                continue

            # include arguments for this option, if there are any, as a tuple
            if(i != len(words) - 1 and word in filename_flags and words[i + 1][0] != '-'):
                flags.add((word, words[i + 1]))
            else:
                flags.add(word)

    # Only specify one word size (the largest)
    # (Different sizes are used for different files in the linux kernel.)
    mRegex = re.compile("^-m[0-9]+$")
    word_flags = list([f for f in flags if isinstance(f, basestring) and mRegex.match(f)])

    if(len(word_flags) > 1):
        for flag in word_flags:
            flags.remove(flag)

        flags.add(max(word_flags))

    # Resolve duplicate macro definitions (always choose the last value for consistency)
    for name, values in define_flags.iteritems():
        if(len(values) > 1):
            print("WARNING: {} distinct definitions of macro {} found".format(len(values), name))
            values.sort()

        flags.add("-D{}={}".format(name, values[0]))

    return (line_count, skip_count, sorted(flags))


def generate_cc_conf(flags, config_file):
    '''Generates the .color_coded file

    flags: the list of flags
    config_file: the path to save the configuration file at'''

    with open(config_file, "w") as output:
        for flag in flags:
            if(isinstance(flag, basestring)):
                output.write(flag + "\n")
            else: # is tuple
                for f in flag:
                    output.write(f + "\n")


def generate_ycm_conf(flags, config_file):
    '''Generates the .ycm_extra_conf.py.

    flags: the list of flags
    config_file: the path to save the configuration file at'''

    template_file = os.path.join(ycm_generator_dir, "template.py")

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
    # Note that sys.exit() lets us use None and 0 interchangably
    sys.exit(main())

