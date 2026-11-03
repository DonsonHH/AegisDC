"""Reader-facing explanations shared by the HTML and binary-free text export."""
import html


def intro(kind,key,number,guide):
    label='图' if kind=='figure' else '表'
    return ('<div class="exhibit-intro" data-guide-'+kind+'="'+key+'">'
            '<p class="exhibit-title"><span class="exhibit-number">'+label+' '+str(number)+'</span> '
            '<strong>'+html.escape(guide['title'])+'</strong></p>'
            '<p class="exhibit-purpose">'+html.escape(guide['purpose'])+'</p></div>')


def reading_notes(guide):
    return ('<div class="reading-notes"><p><strong>↳ 怎么看：</strong>'+html.escape(guide['read'])+'</p>'
            '<p><strong>◇ 读到什么：</strong>'+html.escape(guide['takeaway'])+'</p></div>')


def table_guide(key,number,guide):
    return '<div class="table-guide" id="table-'+key+'">'+intro('table',key,number,guide)+reading_notes(guide)+'</div>'


def symbol_guide(symbols):
    items=''.join('<div><dt>'+html.escape(row['symbol'])+'</dt><dd>'+html.escape(row['meaning'])+'</dd></div>' for row in symbols)
    return '<aside class="symbol-guide" id="reading-symbols" aria-label="图表常见符号"><dl>'+items+'</dl></aside>'
