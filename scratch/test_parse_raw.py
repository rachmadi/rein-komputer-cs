import re

def parse_raw_tool_call(text: str):
    """
    Mengurai panggilan alat mentah dari token Ollama seperti:
    katalog{kategori:<|"|>monitor<|"|>,kata_kunci:<|"|>24 inci<|"|>}<tool_call|><|tool_response>
    """
    m = re.search(r"(katalog|pengetahuan)\s*\{(.*?)\}", text, re.DOTALL)
    if not m:
        return None
    fn_name = m.group(1)
    body = m.group(2).strip()
    args = {}
    pair_pattern = re.compile(
        r'([a-zA-Z0-9_]+)\s*:\s*(?:<\|"\|>(.*?)<\|"\|>|"([^"]*)"|\'([^\']*)\'|([^,}]+))'
    )
    for match in pair_pattern.finditer(body):
        k = match.group(1)
        v = match.group(2) if match.group(2) is not None else (
            match.group(3) if match.group(3) is not None else (
                match.group(4) if match.group(4) is not None else match.group(5)
            )
        )
        if v is not None:
            v = v.strip()
            if v.isdigit():
                v = int(v)
            args[k] = v
    if not args and body:
        return None
    return fn_name, args

s1 = 'katalog{kategori:<|"|>monitor<|"|>,kata_kunci:<|"|>24 inci<|"|>}<tool_call|><|tool_response>'
s2 = 'katalog{kategori:<|"|>monitor<|"|>}<tool_call|><|tool_response>'
s_invalid = 'bukan_alat{kunci:nilai}<tool_call|>'
s_broken = '<tool_call|> rusak <|'

print("s1:", parse_raw_tool_call(s1))
print("s2:", parse_raw_tool_call(s2))
print("s_invalid:", parse_raw_tool_call(s_invalid))
print("s_broken:", parse_raw_tool_call(s_broken))
