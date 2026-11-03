"""Export the resolved report prose without embedding binary or SVG markup."""
import hashlib
import json
import re
import zipfile
import html
import time
from report_reading_guides import intro, reading_notes


def identity(path):
    return {'path':path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def split_chapter(body,limit=21600):
    """Keep complete subsections and their evidence together in small reader files."""
    units=re.split(r'(?m)(?=^#{3,4} |^<h[34]\b)',body)
    chunks=[];current=''
    for unit in units:
        assert len(unit.encode('utf-8'))<=limit,'A subsection exceeds the text-review limit; split that subsection explicitly.'
        if current and len((current+unit).encode('utf-8'))>limit:
            chunks.append(current);current=''
        current+=unit
    if current:chunks.append(current)
    return chunks


def export_review_text(source,figure_notes,labels,paper,resolve_link,html_sha256,reading_guides,figure_order):
    def figure(name):
        target=resolve_link('figures/supervisor-report/'+name+'.svg',current=True)
        guide=reading_guides['figures'][name]
        return ('\n\n<a id="figure-'+name+'"></a>\n\n'+intro('figure',name,figure_order.index(name)+1,guide)
                +'\n\n[查看图版]('+target+')\n\n'+reading_notes(guide)+'<p class="exhibit-source">'+html.escape(figure_notes[name])+'</p>\n\n')
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
    records=[];chapters=[]
    for number,index in enumerate(range(1,len(parts),2),1):
        section,body=parts[index:index+2];chunks=split_chapter(body)
        names=[]
        for part,chunk in enumerate(chunks,1):
            name=f'{number:02}-{section}'+(f'-part{part:02}' if part>1 else '')+'.md'
            names.append(name);records.append({'section':section,'body':chunk,'path':name,'part':part,'parts':len(chunks)})
        chapters.append({'section':section,'title':labels[section],'files':names})
    anchor_files={}
    for row in records:
        anchors=re.findall(r'\bid="([^"]+)"',row['body'])
        if row['part']==1:anchors.insert(0,row['section'])
        for anchor in anchors:
            assert anchor not in anchor_files or anchor_files[anchor]==row['path']
            anchor_files[anchor]=row['path']
    sections=[]
    for row in records:
        section,body=row['section'],row['body'];path=folder/row['path']
        def fragment(target):
            anchor=target[1:];assert anchor in anchor_files,anchor
            return ('' if anchor_files[anchor]==path.name else anchor_files[anchor])+'#'+anchor
        body=re.sub(r'\]\((#[^)\n]+)\)',lambda m:']('+fragment(m[1])+')',body)
        body=re.sub(r'href="(#[^"]+)"',lambda m:'href="'+fragment(m[1])+'"',body)
        part_note='> '+labels[section]+f" · 第{row['part']}/{row['parts']}部分。\n\n"
        chapter=next(c for c in chapters if c['section']==section)
        if row['part']<row['parts']:part_note+='[下一部分]('+chapter['files'][row['part']]+')\n\n'
        anchor='<a id="'+section+'"></a>\n\n' if row['part']==1 else ''
        path.write_text(prefix+part_note+anchor+body.strip()+'\n',encoding='utf-8',newline='\n')
        assert path.stat().st_size<24000,path.name
        sections.append(dict(identity(path),section=section,title=labels[section],part=row['part'],parts=row['parts']))
    old_manifest=folder/'manifest.json'
    if old_manifest.exists():
        old=json.loads(old_manifest.read_text(encoding='utf-8'))
        expected={row['path'] for row in sections}
        for row in old['sections']:
            stale=folder/row['path']
            assert stale.resolve().parent==folder.resolve()
            if stale.name not in expected and stale.exists():
                retired=paper.parent/'.work/retired-text-review';retired.mkdir(parents=True,exist_ok=True)
                stale.rename(retired/(stale.stem+'-'+str(time.time_ns())+stale.suffix))
    manifest={'derived_from_html_sha256':html_sha256,'scope':'Resolved report prose, formulas and numeric tables; all31figures linked rather than embedded.',
              'full':dict(identity(full_path),path='paper/'+full_path.name),'chapters':chapters,'sections':sections,
              'archive_full_path':'report-full.md','local_anchor_files':anchor_files,
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
