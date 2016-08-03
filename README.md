# YCM-Generator
This is a script which generates a list of compiler flags from a project with an arbitrary build system. It can be used to:

* generate a ```.ycm_extra_conf.py``` file for use with [YouCompleteMe](https://github.com/Valloric/YouCompleteMe)
* generate a ```.color_coded``` file for use with [color_coded](https://github.com/jeaye/color_coded)

It works by building the project with a fake toolchain, which simply and filters compiler flags to be stored in the resulting file.

It is reasonably fast, taking ~10 seconds to generate a configuration file for the Linux kernel.

## Installation
Add ```NeoBundle 'rdnetto/YCM-Generator'``` to your vimrc (or the equivalent for your plugin manager).

For [vim-plug](https://github.com/junegunn/vim-plug) users, add ```Plug 'rdnetto/YCM-Generator', { 'branch': 'stable'}``` to your vimrc.

Alternatively, Arch Linux users can install YCM-Generator using the (unofficial) [AUR package](https://aur4.archlinux.org/packages/ycm-generator-git/).

## Usage
Run ```./config_gen.py PROJECT_DIRECTORY```, where ```PROJECT_DIRECTORY``` is the root directory of your project's build system (i.e. the one containing the root Makefile, etc.)

You can also invoke it from within Vim using the ```:YcmGenerateConfig``` or ```:CCGenerateConfig``` commands to generate a config file for the current directory. These commands accept the same arguments as ```./config_gen.py```, but do not require the project directory to be specified (it defaults to the current working directory).

## Requirements and Limitations
* Requirements:
    + Python 2
    + Clang

* Supported build systems:
    + make
    + cmake
    + qmake
    + autotools

Your build system should support specifying the compiler through the ```CC```/```CXX``` environment variables, or not use an absolute path to the compiler.

Some flags present in the resulting configuration file may be mutually exclusive with each other - reading the generated file prior to use is recommended.

The script assumes that executables with the names `clang` and `clang++` exist in your `PATH`. This has been known to cause issues under Ubuntu, where the C++ compiler may be called `clang++-3.6` (see #50).

## Documentation & Support
* run ```./config_gen.py --help``` to see the complete list of supported options.
* if you receive the error message ```ERROR: No commands were logged to the build logs```, try using the ```--verbose``` flag to see any error messages
    + some build systems require certain environment variables to be set. Note that these will *not* be used by YCM-Generator by default, unless `--preserve-environment` is used
    + if you open an issue regarding this error message, please include the output when running with ```--verbose``` and a link to the project repo (if possible)

## Development
Patches are welcome. Please submit pull requests against the ```develop``` branch.

### Windows support
The script is currently supported under Unices (Linux, NixOS<sup>[1]</sup>, BSD, OS X) only.
Implementing Windows support consists of porting the contents of ```fake-toolchain/Unix```.
If you are interested in implementing/testing this, please open a pull request.

<sup>[1]</sup> May require `--preserve-environment` - see [#19](https://github.com/rdnetto/YCM-Generator/issues/19)

### Test Cases
The following projects are used for testing:

| Project                                                                   | Build system      | Notes  |
| ------------------------------------------------------------------------- | ----------------- | ------ |
| [Linux kernel](https://git.kernel.org)                                    | Kbuild (Make)     |        |
| [Vim-qt](https://bitbucket.org/equalsraf/vim-qt.git)                      | Autotools         |        |
| [Clementine](https://github.com/clementine-player/Clementine.git)         | Cmake             |        |
| [ExtPlane](https://github.com/vranki/ExtPlane.git)                        | Qmake             | Should be tested with both versions of Qt. |
| [OpenFOAM](https://github.com/OpenFOAM/OpenFOAM-3.0.x.git)                | wmake             |        |

## License
YCM-Generator is published under the GNU GPLv3.

