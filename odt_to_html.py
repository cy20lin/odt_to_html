#!/usr/bin/env python3
"""
ODT to HTML Converter

Converts OpenDocument Text (.odt) files to standalone HTML with embedded resources.
All images and media are embedded as base64 data URIs for single-file portability.

Usage:
    python odt_to_html.py <input.odt> <output.html>
"""

import argparse
import base64
import mimetypes
import re
import sys
import zipfile
from html import escape
from pathlib import Path
from xml.etree import ElementTree as ET

# ODF XML namespaces
NAMESPACES = {
    'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
    'style': 'urn:oasis:names:tc:opendocument:xmlns:style:1.0',
    'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
    'table': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0',
    'draw': 'urn:oasis:names:tc:opendocument:xmlns:drawing:1.0',
    'fo': 'urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0',
    'xlink': 'http://www.w3.org/1999/xlink',
    'svg': 'urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'meta': 'urn:oasis:names:tc:opendocument:xmlns:meta:1.0',
}

# Register namespaces for ElementTree
for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)


class ODTConverter:
    """Converts ODT files to HTML with embedded resources."""
    
    def __init__(self, odt_path: str):
        self.odt_path = Path(odt_path)
        self.resources: dict[str, bytes] = {}
        self.styles: dict[str, dict] = {}
        self.list_styles: dict[str, dict] = {}
        
    def convert(self) -> str:
        """Convert the ODT file to HTML string."""
        if not self.odt_path.exists():
            raise FileNotFoundError(f"ODT file not found: {self.odt_path}")
        
        if not zipfile.is_zipfile(self.odt_path):
            raise ValueError(f"Invalid ODT file (not a valid ZIP archive): {self.odt_path}")
        
        with zipfile.ZipFile(self.odt_path, 'r') as odt_zip:
            # Load all resources (images, etc.)
            self._load_resources(odt_zip)
            
            # Parse styles
            if 'styles.xml' in odt_zip.namelist():
                styles_xml = odt_zip.read('styles.xml').decode('utf-8')
                self._parse_styles(styles_xml)
            
            # Parse automatic styles from content.xml
            content_xml = odt_zip.read('content.xml').decode('utf-8')
            self._parse_styles(content_xml)
            
            # Convert content to HTML
            html_body = self._convert_content(content_xml)
        
        return self._wrap_html(html_body)
    
    def _load_resources(self, odt_zip: zipfile.ZipFile) -> None:
        """Load all embedded resources from the ODT archive."""
        for name in odt_zip.namelist():
            if name.startswith('Pictures/') or name.startswith('media/'):
                self.resources[name] = odt_zip.read(name)
    
    def _parse_styles(self, xml_content: str) -> None:
        """Parse style definitions from XML content."""
        root = ET.fromstring(xml_content)
        
        # Find all style definitions
        for style in root.iter(f"{{{NAMESPACES['style']}}}style"):
            style_name = style.get(f"{{{NAMESPACES['style']}}}name")
            if not style_name:
                continue
            
            style_props = {}
            
            # Get text properties
            text_props = style.find(f"{{{NAMESPACES['style']}}}text-properties")
            if text_props is not None:
                self._extract_text_properties(text_props, style_props)
            
            # Get paragraph properties
            para_props = style.find(f"{{{NAMESPACES['style']}}}paragraph-properties")
            if para_props is not None:
                self._extract_paragraph_properties(para_props, style_props)
            
            # Get table properties
            table_props = style.find(f"{{{NAMESPACES['style']}}}table-properties")
            if table_props is not None:
                self._extract_table_properties(table_props, style_props)
            
            # Get table cell properties
            cell_props = style.find(f"{{{NAMESPACES['style']}}}table-cell-properties")
            if cell_props is not None:
                self._extract_cell_properties(cell_props, style_props)
            
            self.styles[style_name] = style_props
        
        # Parse list styles
        for list_style in root.iter(f"{{{NAMESPACES['text']}}}list-style"):
            style_name = list_style.get(f"{{{NAMESPACES['style']}}}name")
            if style_name:
                self.list_styles[style_name] = self._parse_list_style(list_style)
    
    def _parse_list_style(self, list_style: ET.Element) -> dict:
        """Parse a list style definition."""
        levels = {}
        
        for child in list_style:
            level = child.get(f"{{{NAMESPACES['text']}}}level", "1")
            tag = child.tag.split('}')[-1]
            
            if tag == 'list-level-style-bullet':
                levels[level] = {'type': 'bullet', 'char': child.get(f"{{{NAMESPACES['text']}}}bullet-char", '•')}
            elif tag == 'list-level-style-number':
                num_format = child.get(f"{{{NAMESPACES['style']}}}num-format", '1')
                levels[level] = {'type': 'number', 'format': num_format}
            else:
                levels[level] = {'type': 'bullet'}
        
        return levels
    
    def _extract_text_properties(self, props: ET.Element, style_dict: dict) -> None:
        """Extract text formatting properties."""
        # Font weight (bold)
        font_weight = props.get(f"{{{NAMESPACES['fo']}}}font-weight")
        if font_weight == 'bold':
            style_dict['font-weight'] = 'bold'
        
        # Font style (italic)
        font_style = props.get(f"{{{NAMESPACES['fo']}}}font-style")
        if font_style == 'italic':
            style_dict['font-style'] = 'italic'
        
        # Text decoration (underline, strikethrough)
        text_underline = props.get(f"{{{NAMESPACES['style']}}}text-underline-style")
        if text_underline and text_underline != 'none':
            style_dict['text-decoration'] = 'underline'
        
        text_line_through = props.get(f"{{{NAMESPACES['style']}}}text-line-through-style")
        if text_line_through and text_line_through != 'none':
            existing = style_dict.get('text-decoration', '')
            style_dict['text-decoration'] = f"{existing} line-through".strip()
        
        # Font size
        font_size = props.get(f"{{{NAMESPACES['fo']}}}font-size")
        if font_size:
            style_dict['font-size'] = font_size
        
        # Font color
        color = props.get(f"{{{NAMESPACES['fo']}}}color")
        if color:
            style_dict['color'] = color
        
        # Font family
        font_family = props.get(f"{{{NAMESPACES['fo']}}}font-family")
        if font_family:
            style_dict['font-family'] = font_family
        
        # Background color
        bg_color = props.get(f"{{{NAMESPACES['fo']}}}background-color")
        if bg_color and bg_color != 'transparent':
            style_dict['background-color'] = bg_color
    
    def _extract_paragraph_properties(self, props: ET.Element, style_dict: dict) -> None:
        """Extract paragraph formatting properties."""
        # Text alignment
        text_align = props.get(f"{{{NAMESPACES['fo']}}}text-align")
        if text_align:
            align_map = {'start': 'left', 'end': 'right', 'center': 'center', 'justify': 'justify'}
            style_dict['text-align'] = align_map.get(text_align, text_align)
        
        # Margins
        margin_top = props.get(f"{{{NAMESPACES['fo']}}}margin-top")
        if margin_top:
            style_dict['margin-top'] = margin_top
        
        margin_bottom = props.get(f"{{{NAMESPACES['fo']}}}margin-bottom")
        if margin_bottom:
            style_dict['margin-bottom'] = margin_bottom
        
        margin_left = props.get(f"{{{NAMESPACES['fo']}}}margin-left")
        if margin_left:
            style_dict['margin-left'] = margin_left
        
        # Line height
        line_height = props.get(f"{{{NAMESPACES['fo']}}}line-height")
        if line_height:
            style_dict['line-height'] = line_height
        
        # Background color
        bg_color = props.get(f"{{{NAMESPACES['fo']}}}background-color")
        if bg_color and bg_color != 'transparent':
            style_dict['background-color'] = bg_color
    
    def _extract_table_properties(self, props: ET.Element, style_dict: dict) -> None:
        """Extract table formatting properties."""
        width = props.get(f"{{{NAMESPACES['style']}}}width")
        if width:
            style_dict['width'] = width
        
        margin_left = props.get(f"{{{NAMESPACES['fo']}}}margin-left")
        if margin_left:
            style_dict['margin-left'] = margin_left
        
        margin_right = props.get(f"{{{NAMESPACES['fo']}}}margin-right")
        if margin_right:
            style_dict['margin-right'] = margin_right
    
    def _extract_cell_properties(self, props: ET.Element, style_dict: dict) -> None:
        """Extract table cell formatting properties."""
        padding = props.get(f"{{{NAMESPACES['fo']}}}padding")
        if padding:
            style_dict['padding'] = padding
        
        border = props.get(f"{{{NAMESPACES['fo']}}}border")
        if border:
            style_dict['border'] = border
        
        bg_color = props.get(f"{{{NAMESPACES['fo']}}}background-color")
        if bg_color and bg_color != 'transparent':
            style_dict['background-color'] = bg_color
        
        vertical_align = props.get(f"{{{NAMESPACES['style']}}}vertical-align")
        if vertical_align:
            style_dict['vertical-align'] = vertical_align
    
    def _get_style_string(self, style_name: str) -> str:
        """Get CSS style string for a named style."""
        if style_name not in self.styles:
            return ""
        
        props = self.styles[style_name]
        return "; ".join(f"{k}: {v}" for k, v in props.items())
    
    def _convert_content(self, content_xml: str) -> str:
        """Convert ODT content XML to HTML body content."""
        root = ET.fromstring(content_xml)
        
        # Find the body/text element
        body = root.find(f".//{{{NAMESPACES['office']}}}text")
        if body is None:
            return "<p>No content found in document.</p>"
        
        return self._process_element(body)
    
    def _process_element(self, element: ET.Element) -> str:
        """Process an XML element and convert to HTML."""
        html_parts = []
        
        for child in element:
            tag = child.tag.split('}')[-1]  # Remove namespace
            
            if tag == 'p':
                html_parts.append(self._process_paragraph(child))
            elif tag == 'h':
                html_parts.append(self._process_heading(child))
            elif tag == 'list':
                html_parts.append(self._process_list(child))
            elif tag == 'table':
                html_parts.append(self._process_table(child))
            elif tag == 'section':
                html_parts.append(self._process_element(child))
            elif tag == 'frame':
                html_parts.append(self._process_frame(child))
            elif tag == 'soft-page-break':
                html_parts.append('<hr class="page-break">')
        
        return '\n'.join(html_parts)
    
    def _process_paragraph(self, para: ET.Element) -> str:
        """Process a paragraph element."""
        style_name = para.get(f"{{{NAMESPACES['text']}}}style-name", "")
        style_str = self._get_style_string(style_name)
        
        content = self._process_inline_content(para)
        
        if not content.strip():
            content = "&nbsp;"  # Preserve empty paragraphs
        
        style_attr = f' style="{style_str}"' if style_str else ''
        return f'<p{style_attr}>{content}</p>'
    
    def _process_heading(self, heading: ET.Element) -> str:
        """Process a heading element."""
        level = heading.get(f"{{{NAMESPACES['text']}}}outline-level", "1")
        level = min(int(level), 6)  # HTML only supports h1-h6
        
        style_name = heading.get(f"{{{NAMESPACES['text']}}}style-name", "")
        style_str = self._get_style_string(style_name)
        
        content = self._process_inline_content(heading)
        
        style_attr = f' style="{style_str}"' if style_str else ''
        return f'<h{level}{style_attr}>{content}</h{level}>'
    
    def _process_inline_content(self, element: ET.Element) -> str:
        """Process inline content within a paragraph or heading."""
        parts = []
        
        # Add element's direct text
        if element.text:
            parts.append(escape(element.text))
        
        for child in element:
            tag = child.tag.split('}')[-1]
            
            if tag == 'span':
                parts.append(self._process_span(child))
            elif tag == 's':
                # Spaces
                count = int(child.get(f"{{{NAMESPACES['text']}}}c", "1"))
                parts.append('&nbsp;' * count)
            elif tag == 'tab':
                parts.append('&emsp;')
            elif tag == 'line-break':
                parts.append('<br>')
            elif tag == 'a':
                parts.append(self._process_link(child))
            elif tag == 'frame':
                parts.append(self._process_frame(child))
            elif tag == 'bookmark' or tag == 'bookmark-start' or tag == 'bookmark-end':
                # Bookmarks can be ignored or converted to anchors
                name = child.get(f"{{{NAMESPACES['text']}}}name", "")
                if name:
                    parts.append(f'<a id="{escape(name)}"></a>')
            elif tag == 'note':
                parts.append(self._process_note(child))
            elif tag == 'soft-page-break':
                pass  # Ignore inline page breaks
            else:
                # Try to get any text content
                if child.text:
                    parts.append(escape(child.text))
            
            # Add tail text
            if child.tail:
                parts.append(escape(child.tail))
        
        return ''.join(parts)
    
    def _process_span(self, span: ET.Element) -> str:
        """Process a text span element."""
        style_name = span.get(f"{{{NAMESPACES['text']}}}style-name", "")
        style_str = self._get_style_string(style_name)
        
        content = self._process_inline_content(span)
        
        if style_str:
            return f'<span style="{style_str}">{content}</span>'
        return content
    
    def _process_link(self, link: ET.Element) -> str:
        """Process a hyperlink element."""
        href = link.get(f"{{{NAMESPACES['xlink']}}}href", "#")
        content = self._process_inline_content(link)
        
        return f'<a href="{escape(href)}">{content}</a>'
    
    def _process_frame(self, frame: ET.Element) -> str:
        """Process a frame element (usually contains images)."""
        # Get frame dimensions
        width = frame.get(f"{{{NAMESPACES['svg']}}}width", "")
        height = frame.get(f"{{{NAMESPACES['svg']}}}height", "")
        
        style_parts = []
        if width:
            style_parts.append(f"width: {width}")
        if height:
            style_parts.append(f"height: {height}")
        
        # Look for image inside the frame
        image = frame.find(f".//{{{NAMESPACES['draw']}}}image")
        if image is not None:
            return self._process_image(image, style_parts)
        
        # Look for text box
        text_box = frame.find(f".//{{{NAMESPACES['draw']}}}text-box")
        if text_box is not None:
            return self._process_text_box(text_box, style_parts)
        
        return ""
    
    def _process_image(self, image: ET.Element, style_parts: list) -> str:
        """Process an image element."""
        href = image.get(f"{{{NAMESPACES['xlink']}}}href", "")
        
        if not href:
            return ""
        
        # Get the image data
        if href in self.resources:
            data = self.resources[href]
            mime_type = mimetypes.guess_type(href)[0] or 'application/octet-stream'
            base64_data = base64.b64encode(data).decode('ascii')
            src = f"data:{mime_type};base64,{base64_data}"
        else:
            # External image - keep the href
            src = href
        
        style_str = "; ".join(style_parts) if style_parts else ""
        style_attr = f' style="{style_str}"' if style_str else ''
        
        return f'<img src="{src}"{style_attr} alt="">'
    
    def _process_text_box(self, text_box: ET.Element, style_parts: list) -> str:
        """Process a text box element."""
        content = self._process_element(text_box)
        
        style_parts.append("border: 1px solid #ccc")
        style_parts.append("padding: 8px")
        style_parts.append("display: inline-block")
        
        style_str = "; ".join(style_parts)
        return f'<div style="{style_str}">{content}</div>'
    
    def _process_list(self, list_elem: ET.Element, level: int = 1) -> str:
        """Process a list element."""
        style_name = list_elem.get(f"{{{NAMESPACES['text']}}}style-name", "")
        
        # Determine list type (ordered or unordered)
        list_type = 'ul'
        if style_name in self.list_styles:
            level_info = self.list_styles[style_name].get(str(level), {})
            if level_info.get('type') == 'number':
                list_type = 'ol'
        
        items_html = []
        for item in list_elem:
            tag = item.tag.split('}')[-1]
            if tag == 'list-item':
                items_html.append(self._process_list_item(item, style_name, level))
        
        return f'<{list_type}>{"".join(items_html)}</{list_type}>'
    
    def _process_list_item(self, item: ET.Element, list_style: str, level: int) -> str:
        """Process a list item element."""
        parts = []
        
        for child in item:
            tag = child.tag.split('}')[-1]
            if tag == 'p':
                # Don't wrap in <p> for list items, just get content
                content = self._process_inline_content(child)
                parts.append(content)
            elif tag == 'list':
                # Nested list
                parts.append(self._process_list(child, level + 1))
            elif tag == 'h':
                parts.append(self._process_heading(child))
        
        return f'<li>{"".join(parts)}</li>'
    
    def _process_table(self, table: ET.Element) -> str:
        """Process a table element."""
        style_name = table.get(f"{{{NAMESPACES['table']}}}style-name", "")
        style_str = self._get_style_string(style_name)
        
        rows_html = []
        
        for child in table:
            tag = child.tag.split('}')[-1]
            if tag == 'table-row':
                rows_html.append(self._process_table_row(child))
            elif tag == 'table-header-rows':
                for row in child:
                    row_tag = row.tag.split('}')[-1]
                    if row_tag == 'table-row':
                        rows_html.append(self._process_table_row(row, is_header=True))
        
        style_attr = f' style="{style_str}"' if style_str else ''
        return f'<table{style_attr} border="1" cellspacing="0" cellpadding="4">{"".join(rows_html)}</table>'
    
    def _process_table_row(self, row: ET.Element, is_header: bool = False) -> str:
        """Process a table row element."""
        cells_html = []
        cell_tag = 'th' if is_header else 'td'
        
        for child in row:
            tag = child.tag.split('}')[-1]
            if tag == 'table-cell':
                cells_html.append(self._process_table_cell(child, cell_tag))
            elif tag == 'covered-table-cell':
                # Merged cell - skip
                pass
        
        return f'<tr>{"".join(cells_html)}</tr>'
    
    def _process_table_cell(self, cell: ET.Element, cell_tag: str) -> str:
        """Process a table cell element."""
        style_name = cell.get(f"{{{NAMESPACES['table']}}}style-name", "")
        style_str = self._get_style_string(style_name)
        
        # Handle colspan and rowspan
        colspan = cell.get(f"{{{NAMESPACES['table']}}}number-columns-spanned", "")
        rowspan = cell.get(f"{{{NAMESPACES['table']}}}number-rows-spanned", "")
        
        attrs = []
        if style_str:
            attrs.append(f'style="{style_str}"')
        if colspan and colspan != "1":
            attrs.append(f'colspan="{colspan}"')
        if rowspan and rowspan != "1":
            attrs.append(f'rowspan="{rowspan}"')
        
        attr_str = " " + " ".join(attrs) if attrs else ""
        
        # Process cell content
        content_parts = []
        for child in cell:
            tag = child.tag.split('}')[-1]
            if tag == 'p':
                content_parts.append(self._process_inline_content(child))
            elif tag == 'list':
                content_parts.append(self._process_list(child))
        
        content = "<br>".join(content_parts) if content_parts else "&nbsp;"
        
        return f'<{cell_tag}{attr_str}>{content}</{cell_tag}>'
    
    def _process_note(self, note: ET.Element) -> str:
        """Process a footnote/endnote element."""
        note_class = note.get(f"{{{NAMESPACES['text']}}}note-class", "footnote")
        note_id = note.get(f"{{{NAMESPACES['text']}}}id", "")
        
        # Get note citation
        citation = note.find(f"{{{NAMESPACES['text']}}}note-citation")
        citation_text = citation.text if citation is not None and citation.text else "*"
        
        # Get note body
        body = note.find(f"{{{NAMESPACES['text']}}}note-body")
        body_html = self._process_element(body) if body is not None else ""
        
        return f'<sup><a href="#note-{escape(note_id)}" id="ref-{escape(note_id)}">[{escape(citation_text)}]</a></sup>'
    
    def _wrap_html(self, body_content: str) -> str:
        """Wrap the body content in a complete HTML document."""
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="generator" content="ODT to HTML Converter">
    <title>Converted Document</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
            background-color: #fff;
        }}
        p {{
            margin: 0.5em 0;
        }}
        h1, h2, h3, h4, h5, h6 {{
            margin-top: 1em;
            margin-bottom: 0.5em;
            color: #222;
        }}
        table {{
            border-collapse: collapse;
            margin: 1em 0;
        }}
        th, td {{
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #f5f5f5;
        }}
        img {{
            max-width: 100%;
            height: auto;
        }}
        a {{
            color: #0066cc;
        }}
        ul, ol {{
            margin: 0.5em 0;
            padding-left: 2em;
        }}
        li {{
            margin: 0.25em 0;
        }}
        hr.page-break {{
            border: none;
            border-top: 2px dashed #ccc;
            margin: 2em 0;
        }}
        sup a {{
            text-decoration: none;
            color: #0066cc;
        }}
    </style>
</head>
<body>
{body_content}
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(
        description='Convert ODT files to standalone HTML with embedded resources.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
    python odt_to_html.py document.odt output.html
    python odt_to_html.py "path/to/my document.odt" "path/to/output.html"
        '''
    )
    parser.add_argument('input', help='Path to the input ODT file')
    parser.add_argument('output', help='Path for the output HTML file')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    # Validate input file
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    
    if not input_path.suffix.lower() == '.odt':
        print(f"Warning: Input file does not have .odt extension: {input_path}", file=sys.stderr)
    
    try:
        converter = ODTConverter(str(input_path))
        html_content = converter.convert()
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write output
        output_path.write_text(html_content, encoding='utf-8')
        
        print(f"Successfully converted: {input_path} -> {output_path}")
        
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ET.ParseError as e:
        print(f"Error parsing ODT content: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
