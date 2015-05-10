
let s:config_gen = expand("<sfile>:p:h:h") . "/config_gen.py"

command! -nargs=? YcmGenerateConfig call s:YcmGenerateConfig("<args>")

function! s:YcmGenerateConfig(flags)
    let l:cmd = "! " . s:config_gen . " " . a:flags

    " Only append the working directory if the last option is not a flag
    let l:split_flags = split(a:flags)
    if len(l:split_flags) == 0 || l:split_flags[-1] =~ "^-"
        let l:cmd = l:cmd . " " . getcwd()
    endif

    execute l:cmd
endfunction

