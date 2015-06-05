
let s:config_gen = expand("<sfile>:p:h:h") . "/config_gen.py"

command! -nargs=? CCGenerateConfig call s:GenerateConfig("cc", "<args>")
command! -nargs=? YcmGenerateConfig call s:GenerateConfig("ycm", "<args>")

function! s:GenerateConfig(fmt, flags)
    let l:cmd = "! " . s:config_gen . " -F " . a:fmt . " " . a:flags

    " Only append the working directory if the last option is a flag
    let l:split_flags = split(a:flags)
    if len(l:split_flags) == 0 || l:split_flags[-1] =~ "^-"
        let l:cmd = l:cmd . " " . fnameescape(getcwd())
    endif

    execute l:cmd
endfunction

