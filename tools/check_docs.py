"""Offline checks for tracked documentation links and basic Mermaid fences/types."""
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote,urlsplit

ROOT=Path(__file__).resolve().parents[1]


def inspect(text,path,tracked):
    errors=[];fence=None;diagram=False
    for number,line in enumerate(text.splitlines(),1):
        marker=re.match(r'^\s*(`{3,}|~{3,})(\w*)',line)
        if marker:
            if fence is None:fence=marker[1][0];diagram=marker[2]=='mermaid'
            elif marker[1][0]==fence:fence=None;diagram=False
            continue
        if fence:
            if diagram and line.strip() and not line.lstrip().startswith('%%'):
                if not re.match(r'\s*(flowchart|graph|sequenceDiagram|erDiagram|classDiagram|stateDiagram-v2|gantt|pie|journey|mindmap|timeline)\b',line):
                    errors.append(f'{path}:{number}: unsupported Mermaid declaration')
                diagram=False
            continue
        for link in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^"]*")?\)',line):
            target=urlsplit(link.strip('<>'))
            if target.scheme or target.netloc or not target.path:continue
            resolved=(ROOT/path).parent/unquote(target.path)
            try:name=resolved.resolve().relative_to(ROOT).as_posix()
            except ValueError:errors.append(f'{path}:{number}: link escapes repository');continue
            if name not in tracked and not any(p.startswith(name+'/') for p in tracked):
                errors.append(f'{path}:{number}: missing tracked link {name}')
    if fence:errors.append(f'{path}: unclosed fenced block')
    return errors


def main():
    tracked=set(subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines())
    paths=sorted(p for p in tracked if p.endswith('.md'))
    errors=[]
    for path in paths:errors.extend(inspect((ROOT/path).read_text(encoding='utf-8'),path,tracked))
    print(json.dumps({'documents':len(paths),'errors':errors,'scope':'Offline relative-file links and Mermaid fence/declaration checks; not full Mermaid rendering or external-link validation.'},indent=2))
    return bool(errors)


if __name__=='__main__':raise SystemExit(main())
