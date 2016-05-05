
let s:config_gen = expand("<sfile>:p:h:h") . "/config_gen.py"

command! -nargs=? -complete=file_in_path -bang CCGenerateConfig call s:GenerateConfig("cc", <bang>0, "<args>")
command! -nargs=? -complete=file_in_path -bang YcmGenerateConfig call s:GenerateConfig("ycm", <bang>0, "<args>")

function! s:GenerateConfig(fmt, overwrite, flags)
    let l:cmd = "! " . s:config_gen . " -F " . a:fmt . " " . a:flags

    if a:overwrite
        let l:cmd = l:cmd . " -f"
    endif

    " Only append the working directory if the last option is a flag
    let l:split_flags = split(a:flags)
    if len(l:split_flags) == 0 || l:split_flags[-1] =~ "^-"
        let l:cmd = l:cmd . " " . shellescape(getcwd())
    endif

    " Disable interactive prompts for consistency with Neovim
    execute l:cmd . " </dev/null"
endfunction

