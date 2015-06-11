# YCM-Generator
This is a script which generates a list of compiler flags from a project with an arbitrary build system. It can be used to:

* generate a ```.ycm_extra_conf.py``` file for use with [YouCompleteMe](https://github.com/Valloric/YouCompleteMe)
* generate a ```.color_coded``` file for use with [color_coded](https://github.com/jeaye/color_coded)

It works by building the project with a fake toolchain, which simply and filters compiler flags to be stored in the resulting file.

It is reasonably fast, taking ~10 seconds to generate a configuration file for the Linux kernel.

## Usage
Run ```./config_gen.py PROJECT_DIRECTORY```, where ```PROJECT_DIRECTORY``` is the root directory of your project's build system (i.e. the one containing the root Makefile, etc.)

YCM-Generator can also be used as a Vim plugin. Once installed with Vundle/NeoBundle/etc., use the ```:YcmGenerateConfig``` or ```:CCGenerateConfig``` command to generate a config file for the current directory. This command accepts the same arguments as ```./config_gen.py```, but does not require the project directory to be specified (it defaults to the current working directory).

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

# Documentation & Support
* run ```./config_gen.py --help``` to see the complete list of supported options.
* if you receive the error message ```ERROR: No commands were logged to the build logs```, try using the ```--verbose``` flag to see any error messages
    + if you open an issue regarding this error message, please include the output when running with ```--verbose``` and a link to the project repo (if possible)

## Development
Patches are welcome. Please submit pull requests against the ```develop``` branch.

### Windows support
The script is currently supported under Unices (Linux, BSD, OS X) only.
Implementing Windows support consists of porting the contents of ```fake-toolchain/Unix```.
If you are interested in implementing/testing this, please open a pull request.

## License
YCM-Generator is published under the GNU GPLv3.

