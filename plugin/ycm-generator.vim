
let s:config_gen = expand("<sfile>:p:h:h") . "/config_gen.py"

command -nargs=0 YcmGenerateConfig call s:YcmGenerateConfig()

function s:YcmGenerateConfig()
    let l:cmd = "! " . s:config_gen . " " . getcwd()
    execute l:cmd
endfunction

