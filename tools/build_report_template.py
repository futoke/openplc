"""Build the editable DOCX template from Markdown; Python standard library only."""
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile
import re

ROOT = Path(__file__).resolve().parents[1]
NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def plain(text):
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', text)
    return text.replace('**', '').replace('`', '')


def paragraph(text, style='Normal'):
    return (f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>'
            f'<w:r><w:t xml:space="preserve">{escape(plain(text))}</w:t></w:r></w:p>')


def table(rows):
    xml = ['<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/>'
           '<w:tblBorders>' + ''.join(
               f'<w:{side} w:val="single" w:sz="4" w:color="B8C4D0"/>'
               for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'))
           + '</w:tblBorders></w:tblPr>']
    for i, row in enumerate(rows):
        xml.append('<w:tr>' + ('<w:trPr><w:tblHeader/></w:trPr>' if i == 0 else ''))
        for cell in row:
            shading = '<w:shd w:fill="E8EEF4"/>' if i == 0 else ''
            xml.append('<w:tc><w:tcPr>' + shading + '</w:tcPr>'
                       + paragraph(cell, 'TableText') + '</w:tc>')
        xml.append('</w:tr>')
    return ''.join(xml) + '</w:tbl>'


def build():
    source = (ROOT / 'docs/REPORT-TEMPLATE.md').read_text(encoding='utf-8')
    body, rows = [], []
    for line in source.splitlines():
        if line.startswith('|'):
            cells = [cell.strip() for cell in line.strip('|').split('|')]
            if not all(re.fullmatch(r':?-+:?', cell) for cell in cells):
                rows.append(cells)
            continue
        if rows:
            body.append(table(rows))
            rows = []
        if not line.strip() or line == '---':
            continue
        if line.startswith('# '):
            body.append(paragraph(line[2:], 'Title'))
        elif line.startswith('## '):
            body.append(paragraph(line[3:], 'Heading1'))
        elif line.startswith('- '):
            body.append(paragraph('• ' + line[2:]))
        else:
            body.append(paragraph(line))
    if rows:
        body.append(table(rows))
    document = (f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{NS}">'
                '<w:body>' + ''.join(body) +
                '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1417"/>'
                '</w:sectPr></w:body></w:document>')
    styles = f'''<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="{NS}">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>
<w:sz w:val="24"/><w:lang w:val="ru-RU"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/>
<w:pPr><w:keepNext/></w:pPr><w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>
<w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr>
<w:rPr><w:b/><w:sz w:val="28"/><w:color w:val="214A6B"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="TableText"><w:name w:val="Table Text"/><w:basedOn w:val="Normal"/>
<w:pPr><w:spacing w:after="80"/></w:pPr><w:rPr><w:sz w:val="22"/></w:rPr></w:style>
</w:styles>'''
    types = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>'''
    root_rels = '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''
    doc_rels = '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''
    target = ROOT / 'docs/REPORT-TEMPLATE.docx'
    with ZipFile(target, 'w', ZIP_DEFLATED) as archive:
        for name, content in {
            '[Content_Types].xml': types, '_rels/.rels': root_rels,
            'word/document.xml': document, 'word/styles.xml': styles,
            'word/_rels/document.xml.rels': doc_rels,
        }.items():
            archive.writestr(name, content.encode('utf-8'))
    print(target)


if __name__ == '__main__':
    build()
