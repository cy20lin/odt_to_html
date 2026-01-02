#!/usr/bin/env python3
"""
ODT to HTML Converter (v2)

Converts OpenDocument Text (.odt) files to standalone HTML with embedded resources.
All images and media are embedded as base64 data URIs for single-file portability.

Usage:
    python odt_to_html.py <input.odt> <output.html> [--page-breaks]
    
Options:
    --page-breaks    Show visible page break separators in output HTML
"""

import argparse
import base64
import mimetypes
import math
import re
import sys
import string
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
    'loext': 'urn:org:documentfoundation:names:experimental:office:xmlns:loext:1.0',
}

# Register namespaces for ElementTree
for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)


class ODTConverter:
    """Converts ODT files to HTML with embedded resources."""
    
    def __init__(self, odt_path: str, show_page_breaks: bool = True, respect_table_borders: bool = True):
        self.odt_path = Path(odt_path)
        self.resources: dict[str, bytes] = {}
        self.styles: dict[str, dict] = {}
        self.list_styles: dict[str, dict] = {}
        self.font_declarations: dict[str, dict] = {}
        self.footnotes: list[dict] = []  # Collect footnotes for end of document
        self.show_page_breaks = show_page_breaks
        self.respect_table_borders = respect_table_borders
        
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
            
            # Add footnotes section if any
            if self.footnotes:
                html_body += self._generate_footnotes_section()
        
        return self._wrap_html(html_body)
    
    def _load_resources(self, odt_zip: zipfile.ZipFile) -> None:
        """Load all embedded resources from the ODT archive."""
        for name in odt_zip.namelist():
            if name.startswith('Pictures/') or name.startswith('media/') or name.startswith('ObjectReplacements/'):
                self.resources[name] = odt_zip.read(name)
    
    def _parse_styles(self, xml_content: str) -> None:
        """Parse style definitions from XML content."""
        root = ET.fromstring(xml_content)
        
        # Parse font declarations
        for font_decl in root.iter(f"{{{NAMESPACES['style']}}}font-face"):
            font_name = font_decl.get(f"{{{NAMESPACES['style']}}}name")
            font_family = font_decl.get(f"{{{NAMESPACES['svg']}}}font-family")
            if font_name and font_family:
                self.font_declarations[font_name] = {
                    'family': font_family.strip("'\""),
                    'generic': font_decl.get(f"{{{NAMESPACES['style']}}}font-family-generic", ""),
                }
        
        # Find all style definitions
        for style in root.iter(f"{{{NAMESPACES['style']}}}style"):
            style_name = style.get(f"{{{NAMESPACES['style']}}}name")
            if not style_name:
                continue
            
            style_props = {}
            
            # Get parent style properties first
            parent_style = style.get(f"{{{NAMESPACES['style']}}}parent-style-name")
            if parent_style and parent_style in self.styles:
                style_props.update(self.styles[parent_style])
            
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
            
            # Get graphic properties
            graphic_props = style.find(f"{{{NAMESPACES['style']}}}graphic-properties")
            if graphic_props is not None:
                self._extract_graphic_properties(graphic_props, style_props)
            
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
        text_line_through_type = props.get(f"{{{NAMESPACES['style']}}}text-line-through-type")
        if (text_line_through and text_line_through != 'none') or (text_line_through_type and text_line_through_type != 'none'):
            existing = style_dict.get('text-decoration', '')
            if 'line-through' not in existing:
                style_dict['text-decoration'] = f"{existing} line-through".strip()
        
        # Border (Table cells)
        if self.respect_table_borders:
            for border_prop in ['border', 'border-top', 'border-bottom', 'border-left', 'border-right']:
                border_val = props.get(f"{{{NAMESPACES['fo']}}}{border_prop}")
                if border_val and border_val != 'none':
                    # Parse border value to ensure it's valid CSS. ODT might use "0.05pt solid #000000"
                    # We might want to ensure a minimum width for visibility if it's very thin
                    parts = border_val.split()
                    if len(parts) >= 3 and parts[0].endswith('pt'):
                        try:
                            width = float(parts[0][:-2])
                            if width < 0.5:
                                # Ensure minimum visibility
                                parts[0] = "0.5pt"
                                border_val = " ".join(parts)
                        except ValueError:
                            pass
                    style_dict[border_prop] = border_val
        
        # Border (Table cells)
        if self.respect_table_borders:
            for border_prop in ['border', 'border-top', 'border-bottom', 'border-left', 'border-right']:
                border_val = props.get(f"{{{NAMESPACES['fo']}}}{border_prop}")
                if border_val and border_val != 'none':
                    # Parse border value to ensure it's valid CSS. ODT might use "0.05pt solid #000000"
                    # We might want to ensure a minimum width for visibility if it's very thin
                    parts = border_val.split()
                    if len(parts) >= 3 and parts[0].endswith('pt'):
                        try:
                            width = float(parts[0][:-2])
                            if width < 0.5:
                                # Ensure minimum visibility
                                parts[0] = "0.5pt"
                                border_val = " ".join(parts)
                        except ValueError:
                            pass
                    style_dict[border_prop] = border_val
        
        # Font size
        font_size = props.get(f"{{{NAMESPACES['fo']}}}font-size")
        if font_size:
            style_dict['font-size'] = font_size
        
        # Font color
        color = props.get(f"{{{NAMESPACES['fo']}}}color")
        if color:
            style_dict['color'] = color
        
        # Font family - use the actual font name from declarations
        font_name = props.get(f"{{{NAMESPACES['style']}}}font-name")
        if font_name:
            if font_name in self.font_declarations:
                font_info = self.font_declarations[font_name]
                font_family = font_info['family']
                generic = font_info.get('generic', '')
                if generic:
                    style_dict['font-family'] = f"'{font_family}', {generic}"
                else:
                    style_dict['font-family'] = f"'{font_family}'"
            else:
                style_dict['font-family'] = f"'{font_name}'"
        
        # Fallback to fo:font-family
        fo_font_family = props.get(f"{{{NAMESPACES['fo']}}}font-family")
        if fo_font_family and 'font-family' not in style_dict:
            style_dict['font-family'] = fo_font_family
        
        # Background color
        bg_color = props.get(f"{{{NAMESPACES['fo']}}}background-color")
        if bg_color and bg_color != 'transparent':
            style_dict['background-color'] = bg_color
        
        # Subscript/Superscript
        text_position = props.get(f"{{{NAMESPACES['style']}}}text-position")
        if text_position:
            if text_position.startswith('sub') or text_position.startswith('-'):
                style_dict['vertical-align'] = 'sub'
                style_dict['font-size'] = '0.8em'
            elif text_position.startswith('super') or (text_position[0].isdigit() and int(text_position.split('%')[0]) > 0):
                style_dict['vertical-align'] = 'super'
                style_dict['font-size'] = '0.8em'
    
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
        
        if self.respect_table_borders:
            for border_prop in ['border', 'border-top', 'border-bottom', 'border-left', 'border-right']:
                border_val = props.get(f"{{{NAMESPACES['fo']}}}{border_prop}")
                if border_val and border_val != 'none':
                    # Parse border value to ensure it's valid CSS. ODT might use "0.05pt solid #000000"
                    # We might want to ensure a minimum width for visibility if it's very thin
                    parts = border_val.split()
                    if len(parts) >= 3 and parts[0].endswith('pt'):
                        try:
                            width = float(parts[0][:-2])
                            if width < 0.5:
                                # Ensure minimum visibility
                                parts[0] = "0.5pt"
                                border_val = " ".join(parts)
                        except ValueError:
                            pass
                    style_dict[border_prop] = border_val
        
        bg_color = props.get(f"{{{NAMESPACES['fo']}}}background-color")
        if bg_color and bg_color != 'transparent':
            style_dict['background-color'] = bg_color
        
        vertical_align = props.get(f"{{{NAMESPACES['style']}}}vertical-align")
        if vertical_align:
            style_dict['vertical-align'] = vertical_align
    
    def _extract_graphic_properties(self, props: ET.Element, style_dict: dict) -> None:
        """Extract graphic/drawing properties."""
        # Stroke/border color
        stroke = props.get(f"{{{NAMESPACES['svg']}}}stroke-color")
        stroke_style = props.get(f"{{{NAMESPACES['draw']}}}stroke")
        
        if stroke_style == 'none':
             style_dict['border'] = 'none' # standard css for div
             style_dict['stroke'] = 'none' # for svg
        elif stroke:
            style_dict['border-color'] = stroke
            style_dict['stroke'] = stroke
        
        stroke_width = props.get(f"{{{NAMESPACES['svg']}}}stroke-width")
        if stroke_width:
             # Handle hairline width (0cm, 0in) which means "thinnest possible"
             if stroke_width.startswith('0') and '0.' not in stroke_width and stroke_width.replace('0', '').strip(string.ascii_letters) == '':
                  # This covers "0in", "0cm", "0pt" etc but not "0.05pt"
                  style_dict['border-width'] = '1px'
                  style_dict['stroke-width'] = '1px'
             else:
                style_dict['border-width'] = stroke_width
                style_dict['stroke-width'] = stroke_width
        
        # Fill color
        fill = props.get(f"{{{NAMESPACES['draw']}}}fill")
        fill_color = props.get(f"{{{NAMESPACES['draw']}}}fill-color")
        
        if fill == 'none':
            style_dict['background-color'] = 'transparent'
            style_dict['fill'] = 'none'
        elif fill_color:
            style_dict['background-color'] = fill_color
            style_dict['fill'] = fill_color

        # Stroke Dash
        stroke_dash = props.get(f"{{{NAMESPACES['draw']}}}stroke-dash")
        if stroke_style == 'dash' or stroke_dash:
            style_dict['border-style'] = 'dashed'
            style_dict['stroke-dasharray'] = '5,5' # Simple fallback for SVG
        elif stroke_style == 'solid':
            style_dict['border-style'] = 'solid'

        # Also check for fo:border properties which might be used in graphic styles
        if self.respect_table_borders:
            for border_prop in ['border', 'border-top', 'border-bottom', 'border-left', 'border-right']:
                border_val = props.get(f"{{{NAMESPACES['fo']}}}{border_prop}")
                if border_val and border_val != 'none':
                    parts = border_val.split()
                    if len(parts) >= 3 and parts[0].endswith('pt'):
                        try:
                            width = float(parts[0][:-2])
                            if width < 0.5:
                                parts[0] = "0.5pt"
                                border_val = " ".join(parts)
                        except ValueError:
                            pass
                    style_dict[border_prop] = border_val

        # Padding/Margin
        padding = props.get(f"{{{NAMESPACES['fo']}}}padding")
        if padding: style_dict['padding'] = padding
        margin = props.get(f"{{{NAMESPACES['fo']}}}margin")
        if margin: style_dict['margin'] = margin


    
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
                if self.show_page_breaks:
                    html_parts.append('<div class="page-break"><span>Page Break</span></div>')
            elif tag == 'sequence-decls':
                pass  # Sequence declarations, skip
            elif tag == 'text-box':
                html_parts.append(self._process_text_box(child, []))
        
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
            
            # Check for positioning attributes on the element
            # ODT shapes anchored to paragraph/char inside a paragraph often have x/y coordinates
            # We need to apply these as absolute positioning ONLY if anchor-type is not "as-char"
            anchor_type = child.get(f"{{{NAMESPACES['draw']}}}anchor-type")
            element_style = []
            x = child.get(f"{{{NAMESPACES['svg']}}}x")
            y = child.get(f"{{{NAMESPACES['svg']}}}y")
            width = child.get(f"{{{NAMESPACES['svg']}}}width")
            height = child.get(f"{{{NAMESPACES['svg']}}}height")
            
            if (x and y) or anchor_type in ('paragraph', 'char'):
                # Shapes with both x AND y coordinates, or explicitly anchored to paragraph/char
                # are positioned absolutely within their container
                element_style.append("position: absolute")
                if x: element_style.append(f"left: {x}")
                if y: element_style.append(f"top: {y}")
            else:
                # As-char elements, unset anchor, or only partial coordinates → flow inline
                element_style.append("display: inline-block")
                element_style.append("vertical-align: text-bottom")
                # Note: y offset for as-char is typically a baseline adjustment, not absolute position
            
            # Note: width/height are usually handled by the specific processors, 
            # but we pass them via style for generic containers if needed.
            
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
                # Pass element_style if it has positioning (the frame processor will merge/handle it?)
                # _process_frame doesn't currently accept external styles argument.
                # However, it reads x/y itself from the element. 
                # But it assumes it returns a block. If we are inline, and it has x/y, 
                # _process_frame handles extracting x/y from the element itself (lines 600-601).
                # So we just call it.
                parts.append(self._process_frame(child))
            elif tag == 'bookmark' or tag == 'bookmark-start' or tag == 'bookmark-end':
                # Bookmarks can be ignored or converted to anchors
                name = child.get(f"{{{NAMESPACES['text']}}}name", "")
                if name:
                    parts.append(f'<a id="{escape(name)}"></a>')
            elif tag == 'note':
                parts.append(self._process_note(child))
            elif tag == 'soft-page-break':
                if self.show_page_breaks:
                    parts.append('<span class="inline-page-break"></span>')
            elif tag == 'sequence':
                # Handle sequence numbers (Figure 1, Table 1, etc.)
                parts.append(self._process_sequence(child))
            elif tag == 'note-ref':
                # Note reference
                ref_name = child.get(f"{{{NAMESPACES['text']}}}ref-name", "")
                note_format = child.get(f"{{{NAMESPACES['text']}}}note-class", "footnote")
                content = self._process_inline_content(child)
                parts.append(f'<sup><a href="#ref-{ref_name}" class="footnote-ref">{content}</a></sup>')
            elif tag == 'custom-shape':
                # Handle inline custom shapes
                parts.append(self._process_custom_shape(child, child, element_style))
            elif tag == 'rect':
                parts.append(self._process_drawing_rect(child, child, element_style))
            elif tag == 'ellipse':
                parts.append(self._process_drawing_ellipse(child, child, element_style))
            elif tag == 'line':
                parts.append(self._process_drawing_line(child, element_style))
            else:
                # Try to get any text content
                if child.text:
                    parts.append(escape(child.text))
            
            # Add tail text
            if child.tail:
                parts.append(escape(child.tail))
        
        return "".join(parts)
        

    
    def _process_sequence(self, seq: ET.Element) -> str:
        """Process a sequence element (figure/table numbering)."""
        # The sequence text is the number itself
        seq_text = seq.text or ""
        return escape(seq_text)
    
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
        """Process a frame element (usually contains images or drawings).
        
        Frames can contain multiple elements: images, text-boxes with captions,
        custom shapes, etc. We process all children and combine the results.
        """
        # Get frame name (used for captions)
        frame_name = frame.get(f"{{{NAMESPACES['draw']}}}name", "")
        
        # Get frame dimensions
        width = frame.get(f"{{{NAMESPACES['svg']}}}width", "")
        height = frame.get(f"{{{NAMESPACES['svg']}}}height", "")
        
        style_parts = []
        if width:
            style_parts.append(f"width: {width}")
        if height:
            style_parts.append(f"height: {height}")
        
        # Get style name and properties
        style_name = frame.get(f"{{{NAMESPACES['draw']}}}style-name", "")
        if style_name in self.styles:
            frame_style_props = self.styles[style_name]
            
            # Apply border/background properties
            for prop in ['border', 'border-color', 'border-width', 'border-style', 
                         'background-color', 'padding', 'margin']:
                if prop in frame_style_props:
                    style_parts.append(f"{prop}: {frame_style_props[prop]}")
            
            # Ensure box-sizing if borders are added
            if 'border' in frame_style_props or 'border-width' in frame_style_props:
                style_parts.append("box-sizing: border-box")
        
        # Check for absolute positioning
        x = frame.get(f"{{{NAMESPACES['svg']}}}x")
        y = frame.get(f"{{{NAMESPACES['svg']}}}y")
        anchor_type = frame.get(f"{{{NAMESPACES['draw']}}}anchor-type")
        
        if (x or y) and anchor_type != 'as-char':
            style_parts.append("position: absolute")
            if x: style_parts.append(f"left: {x}")
            if y: style_parts.append(f"top: {y}")
        elif anchor_type == 'as-char':
             style_parts.append("display: inline-block")
             style_parts.append("vertical-align: text-bottom") # Approximation
        
        # Note: In ODT, frames directly in paragraphs might be positioned relative to the paragraph/page.
        # Inside a draw:frame container, children are absolutely positioned.
        
        # Collect all content from the frame
        frame_content_parts = []
        
        # If we have multiple children, or specific positioning, we might want a container
        has_positioned_children = False
        
        # Process all direct children of the frame
        for child in frame:
            tag = child.tag.split('}')[-1]
            child_style = []
            
            # Check for positioning on children
            cx = child.get(f"{{{NAMESPACES['svg']}}}x")
            cy = child.get(f"{{{NAMESPACES['svg']}}}y")
            cw = child.get(f"{{{NAMESPACES['svg']}}}width")
            ch = child.get(f"{{{NAMESPACES['svg']}}}height")
            transform = child.get(f"{{{NAMESPACES['draw']}}}transform")
            
            if cx or cy:
                has_positioned_children = True
                child_style.append("position: absolute")
                if cx: child_style.append(f"left: {cx}")
                if cy: child_style.append(f"top: {cy}")
            if cw: child_style.append(f"width: {cw}")
            if ch: child_style.append(f"height: {ch}")
            
            if transform:
                 # Clean up transform string - simplified for basic cases
                 # rotate (-0.5...) translate (...) -> rotate(...) translate(...)
                 child_style.append(f"transform: {transform}")
                 # You might need detailed parsing if syntax varies significantly from CSS
                 # ODT often uses "rotate (angle) translate (x y)". CSS expects "rotate(angle) translate(x, y)"
                 # Simple fix specific for typical ODT output: add commas to translate?
                 # Actually ODT: "rotate (1.57) translate (1cm 2cm)" -> CSS: "rotate(1.57rad) translate(1cm, 2cm)"
                 # This is complex. For now, pass it through and hope it works or needs minor tweak.
                 pass

            if tag == 'image':
                frame_content_parts.append(self._process_image(child, style_parts.copy() + child_style, frame_name))
            elif tag == 'text-box':
                # Text box needs to be a positioning context for shapes inside
                # Get min-height from the text-box element
                tb_min_height = child.get(f"{{{NAMESPACES['fo']}}}min-height", "")
                tb_style = ["position: relative"]  # Always relative for positioned children
                if tb_min_height:
                    tb_style.append(f"min-height: {tb_min_height}")
                tb_style.extend(child_style)
                
                content = self._process_text_box_content(child)
                s = "; ".join(tb_style)
                frame_content_parts.append(f'<div class="text-box-container" style="{s}">{content}</div>')
            elif tag == 'custom-shape':
                frame_content_parts.append(self._process_custom_shape(frame, child, style_parts.copy() + child_style))
            elif tag == 'rect':
                frame_content_parts.append(self._process_drawing_rect(frame, child, style_parts.copy() + child_style))
            elif tag == 'ellipse':
                frame_content_parts.append(self._process_drawing_ellipse(frame, child, style_parts.copy() + child_style))
            elif tag == 'line':
                frame_content_parts.append(self._process_drawing_line(child, style_parts.copy() + child_style))
            elif tag == 'object':
                # OLE object - try to find replacement image
                replacement_img = frame.find(f".//{{{NAMESPACES['draw']}}}image")
                if replacement_img is not None:
                    frame_content_parts.append(self._process_image(replacement_img, style_parts.copy() + child_style, frame_name))
        
        # If we have positioned children, the container must be relative
        if has_positioned_children:
            style_parts.append("position: relative")
            # Ensure it has block display to contain size
            style_parts.append("display: inline-block")
            
        # If we found content, return it
        if frame_content_parts:
            # Wrap in the main frame div
            style_str = "; ".join(style_parts)
            content = '\n'.join(part for part in frame_content_parts if part)
            return f'<div class="drawing-frame" style="{style_str}">{content}</div>'
        
        # Fallback: check for ObjectReplacements
        for name in self.resources:
            if 'ObjectReplacement' in name and frame_name and frame_name in name:
                return self._create_image_from_resource(name, style_parts)
        
        return ""
    
    def _process_text_box_content(self, text_box: ET.Element) -> str:
        """Process text box content without adding extra wrapper styling.
        
        This is used for text boxes that contain captions or labels,
        where we just want the text content.
        """
        parts = []
        for child in text_box:
            tag = child.tag.split('}')[-1]
            if tag == 'p':
                content = self._process_inline_content(child)
                if content.strip():
                    # Check if this looks like a figure caption
                    style_name = child.get(f"{{{NAMESPACES['text']}}}style-name", "")
                    style_str = self._get_style_string(style_name)
                    style_attr = f' style="{style_str}"' if style_str else ''
                    parts.append(f'<p class="caption"{style_attr}>{content}</p>')
            elif tag == 'list':
                parts.append(self._process_list(child))
        return '\n'.join(parts)
    
    def _process_image(self, image: ET.Element, style_parts: list, frame_name: str = "") -> str:
        """Process an image element with optional caption support."""
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
        
        alt_text = frame_name if frame_name else ""
        
        # Return as a figure element for semantic correctness
        return f'<img src="{src}"{style_attr} alt="{escape(alt_text)}">'
    
    def _create_image_from_resource(self, resource_name: str, style_parts: list) -> str:
        """Create an image tag from a resource."""
        data = self.resources[resource_name]
        mime_type = mimetypes.guess_type(resource_name)[0] or 'application/octet-stream'
        base64_data = base64.b64encode(data).decode('ascii')
        src = f"data:{mime_type};base64,{base64_data}"
        
        style_str = "; ".join(style_parts) if style_parts else ""
        style_attr = f' style="{style_str}"' if style_str else ''
        
        return f'<img src="{src}"{style_attr} alt="">'
    
    def _process_custom_shape(self, frame: ET.Element, shape: ET.Element, style_parts: list) -> str:
        """Process a custom shape drawing element."""
        # Get dimensions
        width = frame.get(f"{{{NAMESPACES['svg']}}}width", "100px")
        height = frame.get(f"{{{NAMESPACES['svg']}}}height", "100px")
        
        # Try to convert dimensions to pixels for SVG container
        svg_width_px = self._dimension_to_px(width)
        svg_height_px = self._dimension_to_px(height)
        
        # Get style name for colors
        style_name = shape.get(f"{{{NAMESPACES['draw']}}}style-name", "")
        shape_style = self.styles.get(style_name, {})
        
        fill_color = shape_style.get('fill', '#e0e0e0' if 'fill' not in shape_style else 'none')
        stroke_color = shape_style.get('stroke', '#333333' if 'stroke' not in shape_style else 'none')
        stroke_width = shape_style.get('stroke-width', '1pt')
        
        # Override defaults if explicit NONE found in style dict (from fill="none")
        if shape_style.get('fill') == 'none':
            fill_color = 'none'
        if shape_style.get('stroke') == 'none':
            stroke_color = 'none'
        
        # ODT custom shapes usually have a viewBox coordinate system (e.g. 0 0 21600 21600)
        enhanced_geom = shape.find(f".//{{{NAMESPACES['draw']}}}enhanced-geometry")
        
        view_box = "0 0 21600 21600" # Default ODT viewbox
        path_data = ""
        
        if enhanced_geom is not None:
             # Get viewBox if available
            vb = enhanced_geom.get(f"{{{NAMESPACES['svg']}}}viewBox")
            if vb:
                view_box = vb
            
            # Solve equations to get variable values
            variables = self._solve_equations(enhanced_geom, frame)
            
            # Get path and substitute variables
            raw_path = enhanced_geom.get(f"{{{NAMESPACES['draw']}}}enhanced-path", "")
            if raw_path:
                path_data = self._convert_path(raw_path, variables)
        
        # Check for text inside the shape
        text_content_parts = []
        # ODT puts text in a text-box or directly as P/List elements? 
        # Inside custom-shape it can have text:p
        for child in shape:
            tag = child.tag.split('}')[-1]
            if tag == 'p':
                 text_content_parts.append(f'<p style="margin:0; padding:0;">{self._process_inline_content(child)}</p>')
            elif tag == 'list':
                 text_content_parts.append(self._process_list(child))

        text_html = "".join(text_content_parts)
            
        # Construct SVG
        # We use the viewBox from ODT to let the path coordinates work directly
        svg_content = ""
        if path_data:
             svg_content = f'<path d="{path_data}" fill="{fill_color}" stroke="{stroke_color}" stroke-width="{stroke_width}" vector-effect="non-scaling-stroke"/>'
        else:
             # Fallback if no path (e.g. simple rect logic needed but custom-shape should have path or type)
             # Some shapes use modifiers and type='rectangle' without explicit path.
             # For now, minimal fallback if empty path but existing geometry
             pass
             
        svg = f'''<svg width="{width}" height="{height}" viewBox="{view_box}" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">
            {svg_content}
        </svg>'''
        
        # If there is text, we need to overlay it. 
        # ODT text inside shapes is usually centered or fully filling the shape box.
        # We can use a relative container.
        
        style_str = "; ".join(style_parts)
        if "position" not in style_str:
            style_str += "; position: relative"
        if "display" not in style_str:
            style_str += "; display: inline-block"
            
        content = svg
        if text_html.strip():
            # Overlay text centered
            content += f'<div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: center; align-items: center; overflow: hidden;">{text_html}</div>'

        return f'<div class="drawing-custom-shape" style="{style_str}">{content}</div>'

    def _solve_equations(self, geometry: ET.Element, frame: ET.Element) -> dict:
        """Solve ODT enhanced geometry equations."""
        variables = {}
        
        # Get modifiers ($0, $1...)
        modifiers = geometry.get(f"{{{NAMESPACES['draw']}}}modifiers", "")
        if modifiers:
            # Modifiers can be numbers or percentages? Usually space separated numbers.
            mods = modifiers.split()
            for i, val in enumerate(mods):
                try:
                    variables[f'${i}'] = float(val)
                except ValueError:
                    variables[f'${i}'] = 0.0
        else:
             # Some defaults might be needed?
             pass

        # Constants often used
        variables['pi'] = math.pi
        variables['left'] = 0
        variables['top'] = 0
        variables['right'] = 21600 # Default width in internal units
        variables['bottom'] = 21600 # Default height
        
        # Update width/height if viewBox provided (though right/bottom usually match viewBox width/height)
        vb = geometry.get(f"{{{NAMESPACES['svg']}}}viewBox")
        if vb:
            parts = vb.split()
            if len(parts) == 4:
                variables['left'] = float(parts[0])
                variables['top'] = float(parts[1])
                variables['right'] = float(parts[2]) # strictly left + width?
                variables['bottom'] = float(parts[3]) 
                # Note: viewBox is min-x min-y width height. 
                # ODT usage of 'right' usually implies width if starting at 0.
        
        # Helper for if function
        def iff(c, t, f):
            return t if c else f

        # Process equations in order
        for eq in geometry.findall(f".//{{{NAMESPACES['draw']}}}equation"):
            name = eq.get(f"{{{NAMESPACES['draw']}}}name")
            formula = eq.get(f"{{{NAMESPACES['draw']}}}formula")
            if name and formula:
                # Sanitize and convert formula to python expression
                
                expr = formula
                
                # Replace $0, $1... with mod_0, mod_1...
                expr = re.sub(r'\$(\d+)', r'mod_\1', expr)
                
                # Replace ?name with var_name
                expr = re.sub(r'\?([a-zA-Z0-9]+)', r'var_\1', expr)
                
                # Replace 'if(' with 'iff('
                expr = expr.replace('if(', 'iff(')
                
                # Allowed globals
                safe_locals = {'math': math, 'sin': math.sin, 'cos': math.cos, 
                               'tan': math.tan, 'sqrt': math.sqrt, 'abs': abs,
                               'min': min, 'max': max, 'pi': math.pi, 'iff': iff}
                
                # Add current variables to locals with mapped names
                current_locals = safe_locals.copy()
                for k, v in variables.items():
                    if k.startswith('$'):
                        current_locals[f'mod_{k[1:]}'] = v
                    else:
                        current_locals[f'var_{k}'] = v
                        # Also expose standard constants directly (left, top, right, bottom)
                        if k in ['left', 'top', 'right', 'bottom', 'width', 'height']:
                             current_locals[k] = v
                
                try:
                    res = eval(expr, {"__builtins__": {}}, current_locals)
                    variables[name] = float(res)
                except Exception as e:
                    # Fallback or log?
                    variables[name] = 0.0
                    
        return variables

    def _convert_path(self, path_data: str, variables: dict) -> str:
        """Convert ODT enhanced path to SVG path."""
        # Split tokens
        raw_tokens = path_data.split()
        
        # Pass 1: Resolve all variables to float values or keep commands/literals
        resolved_tokens = []
        for token in raw_tokens:
            if token.isalpha():
                resolved_tokens.append(token.upper())
            elif token.startswith('?') or token.startswith('$'):
                val = float(variables.get(token[1:] if token.startswith('?') else token, 0))
                resolved_tokens.append(val)
            else:
                try:
                    resolved_tokens.append(float(token))
                except ValueError:
                     # Should not happen for valid paths, but keep as is just in case
                    resolved_tokens.append(token)

        # Pass 2: Process commands and generate SVG
        svg_path = []
        current_x = 0.0
        current_y = 0.0
        # Track start of subpath for Z (Close) - usually M sets this
        subpath_start_x = 0.0
        subpath_start_y = 0.0
        
        # Track subpath start state for implicit moves (U following N)
        is_subpath_start = True
        
        def fmt(val):
            if isinstance(val, float):
                return f"{val:.2f}".rstrip('0').rstrip('.')
            return str(val)

        i = 0
        last_cmd = None # Track last command for implicit repetition

        while i < len(resolved_tokens):
            token = resolved_tokens[i]
            
            # Determine command to execute
            cmd = None
            if isinstance(token, str) and token.isalpha():
                cmd = token
                i += 1
                last_cmd = cmd
            else:
                # Implicit command based on last_cmd
                if last_cmd in ['M', 'L']:
                    cmd = 'L' # M followed by coords implies L, L repeats
                elif last_cmd == 'C':
                    cmd = 'C'
                elif last_cmd in ['X', 'Y']:
                    # Implicit repetition for X/Y? 
                    # Assuming X/Y also behave like L regarding coordinate consumption (take 2 args here as per our Arc logic which uses targets)
                    # Although ODF spec for X/Y is murky, treating them as L-like targets for Arc seems consistent with 'Poly-Arc'?
                    # Or should we fallback to L? 
                    # Let's fallback to behaving like the explicit command was repeated.
                    cmd = last_cmd 
                # U, Z, N usually don't have coordinate repetition in the same way (U has fixed args, Z/N have none/ignore)
            
            if cmd == 'M':
                # Abs Move: M x y
                if i + 1 < len(resolved_tokens):
                    x = resolved_tokens[i]
                    y = resolved_tokens[i+1]
                    svg_path.append(f"M {fmt(x)} {fmt(y)}")
                    current_x, current_y = x, y
                    subpath_start_x, subpath_start_y = x, y
                    is_subpath_start = False
                    i += 2
            elif cmd == 'L':
                # Abs Line: L x y
                if i + 1 < len(resolved_tokens):
                    x = resolved_tokens[i]
                    y = resolved_tokens[i+1]
                    svg_path.append(f"L {fmt(x)} {fmt(y)}")
                    current_x, current_y = x, y
                    is_subpath_start = False
                    i += 2
            elif cmd == 'C':
                # Cubic Bezier: C x1 y1 x2 y2 x y
                if i + 5 < len(resolved_tokens):
                    coords = resolved_tokens[i:i+6]
                    svg_path.append(f"C {' '.join(fmt(c) for c in coords)}")
                    current_x, current_y = coords[4], coords[5]
                    is_subpath_start = False
                    i += 6
            elif cmd == 'Z':
                svg_path.append("Z")
                current_x, current_y = subpath_start_x, subpath_start_y
                # is_subpath_start remains False usually? 
                pass
            elif cmd == 'N':
                # End subpath
                is_subpath_start = True
            elif cmd == 'X' or cmd == 'Y':
                # Treated as Arc (Quarter Ellipse) for Round Rectangles
                # Abs target: x y
                if i + 1 < len(resolved_tokens):
                    x = resolved_tokens[i]
                    y = resolved_tokens[i+1]
                    
                    # Calculate radii based on distance
                    rx = abs(x - current_x)
                    ry = abs(y - current_y)
                    
                    # A rx ry rot large_arc sweep x y
                    # Sweep 0 is usually correct for convex corners in standard ODF paths
                    svg_path.append(f"A {fmt(rx)} {fmt(ry)} 0 0 0 {fmt(x)} {fmt(y)}")
                    
                    current_x, current_y = x, y
                    is_subpath_start = False
                    i += 2
            elif cmd == 'U':
                # Angle Ellipse: U cx cy rx ry start end
                if i + 5 < len(resolved_tokens):
                    args = resolved_tokens[i:i+6]
                    cx, cy, rx, ry, start_deg, end_deg = args
                    
                    start_rad = math.radians(start_deg)
                    end_rad = math.radians(end_deg)
                    
                    sx = cx + rx * math.cos(start_rad)
                    sy = cy + ry * math.sin(start_rad)
                    
                    # implicit move/line logic
                    action = 'M' if is_subpath_start else 'L'
                    svg_path.append(f"{action} {fmt(sx)} {fmt(sy)}")
                    
                    # Draw arcs
                    if abs(end_deg - start_deg) >= 360:
                        mid_rad = start_rad + math.pi
                        mid_x = cx + rx * math.cos(mid_rad)
                        mid_y = cy + ry * math.sin(mid_rad)
                        end_x = cx + rx * math.cos(end_rad)
                        end_y = cy + ry * math.sin(end_rad)
                        
                        svg_path.append(f"A {fmt(rx)} {fmt(ry)} 0 1 1 {fmt(mid_x)} {fmt(mid_y)}")
                        svg_path.append(f"A {fmt(rx)} {fmt(ry)} 0 1 1 {fmt(end_x)} {fmt(end_y)}")
                    else:
                        ex = cx + rx * math.cos(end_rad)
                        ey = cy + ry * math.sin(end_rad)
                        delta = end_deg - start_deg
                        large = 1 if abs(delta) > 180 else 0
                        sweep = 1 # Clockwise usually
                        svg_path.append(f"A {fmt(rx)} {fmt(ry)} 0 {large} {sweep} {fmt(ex)} {fmt(ey)}")
                    
                    # Update current pos (end of arc)
                    current_x = cx + rx * math.cos(end_rad)
                    current_y = cy + ry * math.sin(end_rad)
                    is_subpath_start = False
                    i += 6
            else:
                # Unknown command? skip
                if cmd is None:
                    i += 1
                pass
                
        return " ".join(svg_path)
    
    def _process_drawing_rect(self, frame: ET.Element, rect: ET.Element, style_parts: list) -> str:
        """Process a rectangle drawing."""
        width = frame.get(f"{{{NAMESPACES['svg']}}}width", "100px")
        height = frame.get(f"{{{NAMESPACES['svg']}}}height", "50px")
        
        svg_width = self._dimension_to_px(width)
        svg_height = self._dimension_to_px(height)
        
        svg = f'''<svg width="{svg_width}" height="{svg_height}" xmlns="http://www.w3.org/2000/svg">
            <rect x="2" y="2" width="{svg_width-4}" height="{svg_height-4}"
                  fill="#e0e0e0" stroke="#333" stroke-width="2"/>
        </svg>'''
        
        style_str = "; ".join(style_parts)
        if "position" not in style_str and "display" not in style_str:
            style_str += "; display: inline-block"
        return f'<div class="drawing" style="{style_str}">{svg}</div>'
    
    def _process_drawing_ellipse(self, frame: ET.Element, ellipse: ET.Element, style_parts: list) -> str:
        """Process an ellipse drawing."""
        width = frame.get(f"{{{NAMESPACES['svg']}}}width", "100px")
        height = frame.get(f"{{{NAMESPACES['svg']}}}height", "100px")
        
        svg_width = self._dimension_to_px(width)
        svg_height = self._dimension_to_px(height)
        
        svg = f'''<svg width="{svg_width}" height="{svg_height}" xmlns="http://www.w3.org/2000/svg">
            <ellipse cx="{svg_width/2}" cy="{svg_height/2}" rx="{svg_width/2-2}" ry="{svg_height/2-2}"
                     fill="#e0e0e0" stroke="#333" stroke-width="2"/>
        </svg>'''
        
        style_str = "; ".join(style_parts)
        if "position" not in style_str and "display" not in style_str:
            style_str += "; display: inline-block"
        return f'<div class="drawing" style="{style_str}">{svg}</div>'
    
    def _process_drawing_line(self, line: ET.Element, style_parts: list) -> str:
        """Process a line drawing."""
        x1 = line.get(f"{{{NAMESPACES['svg']}}}x1", "0")
        y1 = line.get(f"{{{NAMESPACES['svg']}}}y1", "0")
        x2 = line.get(f"{{{NAMESPACES['svg']}}}x2", "100")
        y2 = line.get(f"{{{NAMESPACES['svg']}}}y2", "0")
        
        # Convert to pixels
        x1_px = self._dimension_to_px(x1)
        y1_px = self._dimension_to_px(y1)
        x2_px = self._dimension_to_px(x2)
        y2_px = self._dimension_to_px(y2)
        
        svg_width = max(x1_px, x2_px) + 10
        svg_height = max(y1_px, y2_px) + 10
        
        svg = f'''<svg width="{svg_width}" height="{svg_height}" xmlns="http://www.w3.org/2000/svg">
            <line x1="{x1_px}" y1="{y1_px}" x2="{x2_px}" y2="{y2_px}" stroke="#333" stroke-width="2"/>
        </svg>'''
        
        style_str = "; ".join(style_parts)
        if "position" not in style_str and "display" not in style_str:
            style_str += "; display: inline-block"
        return f'<div class="drawing" style="{style_str}">{svg}</div>'
    
    def _dimension_to_px(self, dim: str) -> float:
        """Convert an ODF dimension to pixels."""
        if not dim:
            return 100
        
        dim = dim.strip()
        
        # Remove unit and convert
        if dim.endswith('cm'):
            return float(dim[:-2]) * 37.795275591  # 1cm = 37.8px
        elif dim.endswith('mm'):
            return float(dim[:-2]) * 3.7795275591  # 1mm = 3.78px
        elif dim.endswith('in'):
            return float(dim[:-2]) * 96  # 1in = 96px
        elif dim.endswith('pt'):
            return float(dim[:-2]) * 1.333  # 1pt = 1.33px
        elif dim.endswith('px'):
            return float(dim[:-2])
        else:
            try:
                return float(dim)
            except ValueError:
                return 100
    
    def _process_text_box(self, text_box: ET.Element, style_parts: list) -> str:
        """Process a text box element."""
        content = self._process_element(text_box)
        
        style_parts.append("border: 1px solid #ccc")
        style_parts.append("padding: 8px")
        style_parts.append("display: inline-block")
        
        style_str = "; ".join(style_parts)
        return f'<div class="text-box" style="{style_str}">{content}</div>'
    
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
        """Process a footnote/endnote element - collect for end of document."""
        note_class = note.get(f"{{{NAMESPACES['text']}}}note-class", "footnote")
        note_id = note.get(f"{{{NAMESPACES['text']}}}id", "")
        
        # Get note citation
        citation = note.find(f"{{{NAMESPACES['text']}}}note-citation")
        citation_text = citation.text if citation is not None and citation.text else "*"
        
        # Get note body content
        body = note.find(f"{{{NAMESPACES['text']}}}note-body")
        body_html = ""
        if body is not None:
            # Process all paragraphs in the note body
            body_parts = []
            for child in body:
                tag = child.tag.split('}')[-1]
                if tag == 'p':
                    body_parts.append(self._process_inline_content(child))
            body_html = " ".join(body_parts)
        
        # Store footnote for later rendering
        self.footnotes.append({
            'id': note_id,
            'citation': citation_text,
            'content': body_html,
            'class': note_class,
        })
        
        # Return the inline reference
        return f'<sup class="footnote-ref"><a href="#note-{escape(note_id)}" id="ref-{escape(note_id)}">[{escape(citation_text)}]</a></sup>'
    
    def _generate_footnotes_section(self) -> str:
        """Generate the footnotes section at the end of the document."""
        if not self.footnotes:
            return ""
        
        html_parts = ['<hr class="footnotes-separator">', '<section class="footnotes">', '<h4>Footnotes</h4>', '<ol class="footnotes-list">']
        
        for note in self.footnotes:
            note_id = note['id']
            citation = note['citation']
            content = note['content']
            
            html_parts.append(
                f'<li id="note-{escape(note_id)}" value="{escape(citation)}">'
                f'{content} '
                f'<a href="#ref-{escape(note_id)}" class="footnote-backref" title="Go back to reference">↩</a>'
                f'</li>'
            )
        
        html_parts.append('</ol>')
        html_parts.append('</section>')
        
        return '\n'.join(html_parts)
    
    def _wrap_html(self, body_content: str) -> str:
        """Wrap the body content in a complete HTML document."""
        # Build font-family CSS variables for commonly used fonts
        # Map ODF fonts to system font stacks for offline viewing
        font_stack_map = {
            'Liberation Serif': "'Liberation Serif', 'Times New Roman', 'Georgia', serif",
            'Liberation Sans': "'Liberation Sans', 'Arial', 'Helvetica Neue', sans-serif",
            'Liberation Mono': "'Liberation Mono', 'Courier New', 'Consolas', monospace",
            'Times New Roman': "'Times New Roman', 'Georgia', serif",
            'Arial': "'Arial', 'Helvetica Neue', sans-serif",
            'Courier New': "'Courier New', 'Consolas', monospace",
            'Noto Serif': "'Noto Serif', 'Times New Roman', serif",
            'Noto Sans': "'Noto Sans', 'Arial', sans-serif",
            'Noto Sans Mono': "'Noto Sans Mono', 'Courier New', monospace",
            'Noto Serif CJK TC': "'Noto Serif CJK TC', 'PMingLiU', 'SimSun', serif",
            'Noto Sans CJK TC': "'Noto Sans CJK TC', 'Microsoft JhengHei', 'SimHei', sans-serif",
        }
        
        # Generate CSS custom properties for fonts used in the document
        font_css_vars = []
        for style_props in self.styles.values():
            if 'font-family' in style_props:
                font = style_props['font-family'].strip("'\"")
                if ',' in font:
                    font = font.split(',')[0].strip().strip("'\"")
                if font in font_stack_map:
                    # Update the style to use the full font stack
                    style_props['font-family'] = font_stack_map[font]
        
        page_break_css = ""
        if self.show_page_breaks:
            page_break_css = """
        .page-break {
            page-break-before: always;
            border: none;
            border-top: 2px dashed #999;
            margin: 2em 0;
            position: relative;
            text-align: center;
        }
        .page-break span {
            background: #fff;
            padding: 0 10px;
            color: #999;
            font-size: 12px;
            position: relative;
            top: -10px;
        }
        .inline-page-break::after {
            content: '⋯';
            color: #999;
        }
"""
        
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="generator" content="ODT to HTML Converter v2">
    <title>Converted Document</title>
    <style>
        body {{
            font-family: 'Noto Serif', 'Times New Roman', serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
            background-color: #fff;
        }}
        p {{
            margin: 0.5em 0;
            position: relative;
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
        figure {{
            margin: 1em 0;
            text-align: center;
        }}
        figure img {{
            display: block;
            margin: 0 auto;
        }}
        figcaption {{
            margin-top: 0.5em;
            font-style: italic;
            color: #666;
            font-size: 0.9em;
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
        .footnote-ref a {{
            text-decoration: none;
            color: #0066cc;
        }}
        .footnotes {{
            margin-top: 2em;
            padding-top: 1em;
            font-size: 0.9em;
        }}
        .footnotes h4 {{
            margin-bottom: 0.5em;
            color: #555;
        }}
        .footnotes-list {{
            padding-left: 1.5em;
        }}
        .footnotes-list li {{
            margin: 0.5em 0;
        }}
        .footnote-backref {{
            text-decoration: none;
            color: #0066cc;
            margin-left: 0.5em;
        }}
        .footnotes-separator {{
            border: none;
            border-top: 1px solid #ccc;
            margin: 2em 0 1em 0;
        }}
        .drawing {{
            margin: 0.5em 0;
        }}
        .text-box {{
            margin: 0.5em 0;
        }}
        {page_break_css}
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
    python odt_to_html.py document.odt output.html --no-page-breaks
    python odt_to_html.py "path/to/my document.odt" "path/to/output.html"
        '''
    )
    parser.add_argument('input', help='Path to the input ODT file')
    parser.add_argument('output', help='Path for the output HTML file')
    parser.add_argument('--no-page-breaks', action='store_true',
                        help='Hide page break separators in output HTML (shown by default)')
    parser.add_argument('--table-respect-border', action='store_true', default=True,
                        help='Respect table border styles from ODT (default: True). Use --no-table-respect-border to disable.')
    parser.add_argument('--no-table-respect-border', action='store_false', dest='table_respect_border',
                        help='Disable respecting table border styles')
    
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
        # Page breaks shown by default, --no-page-breaks disables them
        show_page_breaks = not args.no_page_breaks
        converter = ODTConverter(
            str(input_path), 
            show_page_breaks=show_page_breaks,
            respect_table_borders=args.table_respect_border
        )
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
