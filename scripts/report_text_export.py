"""Export the resolved report prose without embedding binary or SVG markup."""
import hashlib
import json
import re
import zipfile


def identity(path):
    return {'path':path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def export_review_text(source,figure_notes,labels,paper,resolve_link,html_sha256):
    def figure(name):
        target=resolve_link('figures/supervisor-report/'+name+'.svg',current=True)
        return '\n\n[图：'+figure_notes[name]+']('+target+')\n\n'
    text=re.sub(r'\{\{FIGURE:([a-z0-9-]+)\}\}',lambda m:figure(m[1]),source)
    text=re.sub(r'\{\{PAIR:([a-z0-9-]+),([a-z0-9-]+)\}\}',lambda m:figure(m[1])+figure(m[2]),text)
    text=text.replace('<!-- optional-case:start -->','').replace('<!-- optional-case:end -->','')
    text=re.sub(r'href="([^"]+)"',lambda m:'href="'+resolve_link(m[1])+'"',text)
    text=re.sub(r'(?<!!)\[([^\]\n]+)\]\(([^)\n]+)\)',lambda m:'['+m[1]+']('+resolve_link(m[2])+')',text)
    assert '{{' not in text and 'data:image' not in text and '<svg' not in text
    parts=re.split(r'<!-- section:([a-z-]+) -->',text)
    assert parts[1::2]==list(labels)
    prefix='> 正文审阅版：正文、公式和数值表与单文件HTML同源；图版保留SVG链接，便于文本工具读取。\n\n'
    full=prefix+re.sub(r'<!-- section:([a-z-]+) -->',lambda m:'<a id="'+m[1]+'"></a>',text)
    full_path=paper/'supervisor-report-text.md';full_path.write_text(full,encoding='utf-8',newline='\n')
    folder=paper/'text-review';folder.mkdir(exist_ok=True)
    sections=[]
    for number,index in enumerate(range(1,len(parts),2),1):
        section,body=parts[index:index+2]
        path=folder/f'{number:02}-{section}.md'
        path.write_text(prefix+'<a id="'+section+'"></a>\n\n'+body.strip()+'\n',encoding='utf-8',newline='\n')
        sections.append(dict(identity(path),section=section,title=labels[section]))
    manifest={'derived_from_html_sha256':html_sha256,'scope':'Resolved report prose, formulas and numeric tables; all31figures linked rather than embedded.',
              'full':dict(identity(full_path),path='paper/'+full_path.name),'sections':sections,
              'no_base64':True,'section_bytes_max':max(r['bytes'] for r in sections)}
    manifest_path=folder/'manifest.json';manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    archive_path=paper/'generated/supervisor-text-review.zip'
    with zipfile.ZipFile(archive_path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        entries={'report-full.md':full_path.read_bytes(),'manifest.json':manifest_path.read_bytes()}
        entries.update({r['path']:(folder/r['path']).read_bytes() for r in sections})
        for name,raw in entries.items():
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,raw)
    return dict(manifest,archive=dict(identity(archive_path),path=archive_path.relative_to(paper.parent).as_posix()))
