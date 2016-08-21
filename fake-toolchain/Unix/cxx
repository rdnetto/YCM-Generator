#!/bin/sh

if [ ! -z "$YCM_CONFIG_GEN_CC_PASSTHROUGH" ]; then
    # Cmake determines compiler properties by compiling a test file, so call clang for this case
    $YCM_CONFIG_GEN_CXX_PASSTHROUGH $@

elif [ "$1" = "-v" ] || [ "$1" = "--version" ]; then
    # Needed to enable clang-specific options for certain build systems (e.g. linux)
    $YCM_CONFIG_GEN_CXX_PASSTHROUGH $@

else
    echo "$@" >> $YCM_CONFIG_GEN_CXX_LOG
fi

