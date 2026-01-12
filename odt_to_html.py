#!/usr/bin/env python3
"""
ODT to HTML Converter

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
import traceback
from typing import Callable, Optional


def str_to_bool(s: str):
    if s.isupper():
        ss = s.lower()
    else:
        ss = s[0].lower() + s[1:]
    if ss in ('1','y','t','yes','true','on'):
        return True
    elif ss in ('0','n','f','no','false','off'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

# For processing paragraph anchored objects

class Length:
    # conversion factors to meter
    _UNIT_TO_M = {
        "mm": 0.001,
        "cm": 0.01,
        "m": 1.0,
        "km": 1000.0,
        "inch": 0.0254,
        "in": 0.0254,
        "ft": 0.3048,           # 12 * 0.0254
        "mi": 1609.344,         # 5280 * 0.3048
        "pt": 0.0254 / 72,      # 1 pt = 1/72 inch
        "pc": 12 * (0.0254 / 72) # 1 pica = 12 pt
    }

    @staticmethod
    def from_str(text) -> 'Length':
        """
        Extracts the first number (integer or float) and its unit from a string.
        
        Returns a tuple (number_as_float, unit_string) or (None, None) if no match.
        """
        # Regex pattern explanation:
        # (?P<number>[-+]*\\d*\\.?\\d+) : Captures the number part (float or int) into a group named 'number'.
        # \\s?                      : Matches an optional space.
        # (?P<unit>[a-zA-Z]+)       : Captures the unit part (letters only) into a group named 'unit'.
        pattern = re.compile(r'(?P<number>[-+]*\d*\.?\d+)\s*(?P<unit>[a-zA-Z]*)')
        match = pattern.match(text.strip())
        if match:
            # Access the named groups
            number_str = match.group('number')
            unit_str = match.group('unit')
            # Convert the number string to a float
            return Length(float(number_str), unit_str)
        else:
            raise ValueError(f'Cannot parse {repr(text)} to Length.')

    def __init__(self, value, unit="m"):
        if unit not in self._UNIT_TO_M:
            raise ValueError(f"Unsupported unit: {unit}")
        self.value = float(value)
        self.unit = unit
        self._meters = self.value * self._UNIT_TO_M[unit]

    # Representations
    def __repr__(self):
        return f"Length({self.value}, '{self.unit}')"

    def __str__(self):
        return f"{self.value} {self.unit}"

    # Arithmetic operations
    def __add__(self, other):
        if not isinstance(other, Length):
            return NotImplemented
        return Length(self.value + other.to(self.unit), self.unit)

    def __sub__(self, other):
        if not isinstance(other, Length):
            return NotImplemented
        return Length(self.value - other.to(self.unit), self.unit)

    def __mul__(self, factor):
        if not isinstance(factor, (int, float)):
            return NotImplemented
        return Length(self.value * factor, self.unit)

    def __rmul__(self, factor):
        return self.__mul__(factor)

    def __truediv__(self, factor):
        if not isinstance(factor, (int, float)):
            return NotImplemented
        return Length(self.value / factor, self.unit)

    # Negation
    def __neg__(self):
        return Length(-self.value , self.unit)

    def __abs__(self):
        return Length(abs(self.value), self.unit)

    # Comparison
    def __eq__(self, other):
        if not isinstance(other, Length):
            return NotImplemented
        return self._meters == other._meters

    def __lt__(self, other):
        if isinstance(other, Length):
            return self._meters < other._meters
        elif isinstance(other,(int,float)):
            return self.value < other
        else:
            return NotImplemented

    def __le__(self, other):
        return self == other or self < other

    def __gt__(self, other):
        return not self <= other

    def __ge__(self, other):
        return not self < other

    # Hash (so it can be used in sets or as dict keys)
    def __hash__(self):
        return hash(self._meters)

    # Convert to different unit
    def to(self, unit):
        if unit not in self._UNIT_TO_M:
            raise ValueError(f"Unsupported unit: {unit}")
        return self._meters / self._UNIT_TO_M[unit]
    def __str__(self):
        return f'{self.value:.6g}{self.unit}'

def merge_intervals(intervals):
    '''
    Given maybe overlapping intervals,
    Merge and compute non overlapping initial position sorted intervals

    Arguments: 
    - intervals: [(x1,x2)]
    Result:
    - merged_intervals: [(y1,y2)]
    - indices_group: list[list[int]]
    '''
    if not intervals:
        return [],[]
    # sort by starting position
    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0]]
    indices_group = [[0]]
    for i,current in enumerate(intervals[1:],1):
        prev_start, prev_end = merged[-1]
        curr_start, curr_end = current
        # if overlapped or touched
        if curr_start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, curr_end))
            indices_group[-1].append(i)
        else:
            merged.append(current)
            indices_group.append([i])

    return merged, indices_group

import heapq
from collections import Counter

def skyline_paths(boxes):
    events = []
    for x, y, w, h in boxes:
        events.append((x, 1, y, y + h))
        events.append((x + w, -1, y, y + h))

    events.sort(key=lambda e: (e[0], -e[1]))

    bottoms, tops = [], []
    bcount, tcount = Counter(), Counter()

    upper_paths = []
    lower_paths = []
    cu = cl = None
    active = False

    prev_x = None
    prev_top = None
    prev_bot = None

    def clean(heap, counter):
        while heap and counter[abs(heap[0][0])] == 0:
            heapq.heappop(heap)

    for x, typ, yb, yt in events:
        if prev_x is not None and x != prev_x and active:
            # horizontal extension only if different from last point
            if cu[-1] != (prev_x, prev_top):
                cu.append((prev_x, prev_top))
            cu.append((x, prev_top))

            if cl[-1] != (prev_x, prev_bot):
                cl.append((prev_x, prev_bot))
            cl.append((x, prev_bot))

        # apply event
        if typ == 1:
            heapq.heappush(bottoms, (yb, x))
            heapq.heappush(tops, (-yt, x))
            bcount[yb] += 1
            tcount[yt] += 1
        else:
            bcount[yb] -= 1
            if bcount[yb] == 0: del bcount[yb]
            tcount[yt] -= 1
            if tcount[yt] == 0: del tcount[yt]

        clean(bottoms, bcount)
        clean(tops, tcount)

        curr_top = -tops[0][0] if tops else None
        curr_bot = bottoms[0][0] if bottoms else None

        # end path
        if active and not tops:
            upper_paths.append(cu)
            lower_paths.append(cl)
            cu = cl = None
            active = False

        # start new path
        if not active and tops:
            active = True
            cu = [(x, curr_top)]
            cl = [(x, curr_bot)]

        # vertical change (avoid duplicates)
        if active:
            if curr_top != prev_top:
                if cu[-1] != (x, curr_top):
                    cu.append((x, curr_top))

            if curr_bot != prev_bot:
                if cl[-1] != (x, curr_bot):
                    cl.append((x, curr_bot))

        prev_x = x
        prev_top = curr_top
        prev_bot = curr_bot

    return upper_paths, lower_paths

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

def extract_sign_number_unit_str(text):
    """
    Extracts the first number (integer or float) and its unit from a string.
    
    Returns a tuple (number_as_float, unit_string) or (None, None) if no match.
    """
    # Regex pattern explanation:
    # (?P<sign>[-+]*)
    # (?P<number>\\d*\\.?\\d+) : Captures the number part (float or int) into a group named 'number'.
    # \\s?                      : Matches an optional space.
    # (?P<unit>[a-zA-Z]+)       : Captures the unit part (letters only) into a group named 'unit'.
    pattern = re.compile(r'(?P<sign>[-+]*)(?P<number>\d*\.?\d+)\s*(?P<unit>[a-zA-Z]*)')
    match = pattern.match(text.strip())
    if match:
        # Access the named groups
        sign_str = match.group('sign')
        number_str = match.group('number')
        unit_str = match.group('unit')
        # Convert the number string to a float
        return sign_str, number_str, unit_str
    else:
        return None

def is_sign_str_negative(sign_str: str):
    minus_count = sign_str.count('-')
    return minus_count % 2 == 1

from pydantic import BaseModel, ConfigDict

class TextDecoration(BaseModel):
    model_config = ConfigDict(extra='forbid') # Forbid extra fields
    line_through: bool | None = None
    underline: bool | None = None

    def inherit(self, base: "TextDecoration") -> "TextDecoration":
        return TextDecoration(
            line_through = base.line_through if base.line_through is not None else self.line_through,
            underline   = base.underline     if base.underline     is not None else self.underline,
        )
    def is_setted(self) -> bool:
        # return self.line_through is not None and self.underline is not None
        return self.line_through or self.underline 
    
    def wrap(self, content: str):
        if content and self.is_setted():
            return f'<span{self._as_style_str()}>{content}</span>'
        else:
            return content

    def nowrap(self, content: str):
        if content and self.is_setted():
            return f'</span>{content}<span{self._as_style_str()}>'
        else:
            return content

    # def as_wrapped_str(self, format:str = ' style={}') -> str:
    #     decorations = []
    #     if self.line_through: decorations.append('line-through')
    #     if self.underline: decorations.append('underline')
    #     decorations_value_str = ' '.join(decorations)
    #     style_str = decorations_value_str
    #     return format.format(style_str)
    
    def _as_style_str(self):
        decorations = []
        if self.line_through: decorations.append('line-through')
        if self.underline: decorations.append('underline')
        decorations_value_str = ' '.join(decorations)
        style_str = decorations_value_str
        result = f' style="text-decoration:{style_str}"' if style_str else ''
        return result
    
    def inherit(self, base: 'TextDecoration') -> 'TextDecoration':
        if self.line_through is None: self.line_through = base.line_through
        if self.underline is None: self.underline = base.underline
        return self

class ODTConverter:
    """Converts ODT files to HTML with embedded resources."""
    
    def __init__(
        self, 
        odt_path: str, 
        show_page_breaks: bool = True,
        title: str = None, 
        title_from_metadata: bool = True,
        title_from_styled_title: bool = True,
        title_from_h1: bool = True,
        title_from_filename: bool = True,
        title_fallback: str = None
    ):
        self.odt_path = Path(odt_path)
        self.resources: dict[str, bytes] = {}
        self.styles: dict[str, dict] = {}
        self.extra_styles: dict[str, dict] = {}
        self.text_decorations: dict[str, TextDecoration] = {} # key is style_name
        self.list_styles: dict[str, dict] = {}
        self.font_declarations: dict[str, dict] = {}
        self.footnotes: list[dict] = []  # Collect footnotes for end of document
        self.show_page_breaks = show_page_breaks
        self.current_page_anchors: list[str] = []
        self.list_style_name_stack: list[str] = []
        self.page_properties: dict[str, str] = {
            'width': '21cm',
            'height': '29.7cm',
            'margin-top': '2cm',
            'margin-bottom': '2cm', 
            'margin-left': '2cm', 
            'margin-right': '2cm'
        }
        # Title configuration
        self.overridden_title = title
        self.use_meta_title = title_from_metadata
        self.use_styled_title = title_from_styled_title
        self.use_h1_title = title_from_h1
        self.use_filename_title = title_from_filename
        self.fallback_title = title_fallback
        
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
            extra_style_props = {}
            text_decoration = TextDecoration()
            
            # Get parent style properties first
            parent_style = style.get(f"{{{NAMESPACES['style']}}}parent-style-name")
            if parent_style and parent_style in self.styles:
                style_props.update(self.styles[parent_style])
            
            # Get text properties
            text_props = style.find(f"{{{NAMESPACES['style']}}}text-properties")
            if text_props is not None:
                self._extract_text_properties(text_props, style_props, text_decoration)
            
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
                self._extract_graphic_properties(graphic_props, style_props, extra_style_props)
            
            self.styles[style_name] = style_props
            self.extra_styles[style_name] = extra_style_props
            self.text_decorations[style_name] = text_decoration

        # Parse Page Layouts
        # 1. Find master page to identify the default page layout
        default_page_layout_name = None
        for master_styles in root.iter(f"{{{NAMESPACES['office']}}}master-styles"):
             for master_page in master_styles.iter(f"{{{NAMESPACES['style']}}}master-page"):
                 # Just take the first one as default for now
                 default_page_layout_name = master_page.get(f"{{{NAMESPACES['style']}}}page-layout-name")
                 if default_page_layout_name:
                     break
        
        # 2. Extract properties from the page layout
        if default_page_layout_name:
            for page_layout in root.iter(f"{{{NAMESPACES['style']}}}page-layout"):
                if page_layout.get(f"{{{NAMESPACES['style']}}}name") == default_page_layout_name:
                    props = page_layout.find(f"{{{NAMESPACES['style']}}}page-layout-properties")
                    if props is not None:
                        self._extract_page_properties(props)
        
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
    
    def _extract_page_properties(self, props: ET.Element) -> None:
        """Extract page layout properties."""
        for attr in ['page-width', 'page-height', 'margin-top', 'margin-bottom', 'margin-left', 'margin-right']:
             val = props.get(f"{{{NAMESPACES['fo']}}}{attr}")
             if val:
                 key = attr.replace('page-', '') # page-width -> width
                 self.page_properties[key] = val
    
    def _extract_text_properties(self, props: ET.Element, style_dict: dict, text_decoration: TextDecoration) -> None:
        """Extract text formatting properties."""
        # Font weight (bold)
        font_weight = props.get(f"{{{NAMESPACES['fo']}}}font-weight")
        if font_weight == 'bold':
            style_dict['font-weight'] = 'bold'
        
        # Font style (italic)
        font_style = props.get(f"{{{NAMESPACES['fo']}}}font-style")
        if font_style == 'italic':
            style_dict['font-style'] = 'italic'
        
        # Text decoration (underline)
        # for viewing the doc about style:text-underline-style, see https://docs.oasis-open.org/office/OpenDocument/v1.3/os/part3-schema/OpenDocument-v1.3-os-part3-schema.html#__RefHeading__1420224_253892949
        # According to spec, the presense of style:text-underline-style with a non "none" value, 
        # implies the attrib style:text-underline-type should be defined and properly setted
        # so checking style:text-underline-style is enough
        text_underline = props.get(f"{{{NAMESPACES['style']}}}text-underline-style")
        if text_underline is None:
            text_decoration.underline = None
        elif text_underline == 'none':
            text_decoration.underline = False
        else:
            text_decoration.underline = True
        
        # Text decoration (Strikethrough)
        # For viewing the doc about style:text-line-through-type, see https://docs.oasis-open.org/office/OpenDocument/v1.3/os/part3-schema/OpenDocument-v1.3-os-part3-schema.html#__RefHeading__1420190_253892949
        # According to spec, the presense of style:text-line-through-style with a non "none" value, 
        # implies the attrib style:text-line-through-type should be defined and properly setted
        # so checking style:text-line-through-style is enough
        text_line_through = props.get(f"{{{NAMESPACES['style']}}}text-line-through-style")
        if text_line_through is None:
            text_decoration.line_through = None
        elif text_line_through == 'none':
            text_decoration.line_through = False
        else:
            text_decoration.line_through = True
        
        # Border (Table cells)
        for border_prop in ['border', 'border-top', 'border-bottom', 'border-left', 'border-right']:
            border_val = props.get(f"{{{NAMESPACES['fo']}}}{border_prop}")
            if border_val is not None:
                style_dict[border_prop] = border_val
            # NOTE: unomment following code if you want to have a minimun border
            # if border_val and border_val != 'none':
            #     # Parse border value to ensure it's valid CSS. ODT might use "0.05pt solid #000000"
            #     # We might want to ensure a minimum width for visibility if it's very thin
            #     parts = border_val.split()
            #     if len(parts) >= 3 and parts[0].endswith('pt'):
            #         try:
            #             width = float(parts[0][:-2])
            #             if width < 0.5:
            #                 # Ensure minimum visibility
            #                 parts[0] = "0.5pt"
            #                 border_val = " ".join(parts)
            #         except ValueError:
            #             pass
            #     style_dict[border_prop] = border_val
        
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
            
        # Break before (Page break)
        if props.get(f"{{{NAMESPACES['fo']}}}break-before") == 'page':
            style_dict['break-before'] = 'page'
    
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
        
        for border_prop in ['border', 'border-top', 'border-bottom', 'border-left', 'border-right']:
            border_val = props.get(f"{{{NAMESPACES['fo']}}}{border_prop}")
            if border_val is not None:
                style_dict[border_prop] = border_val
            # if border_val and border_val != 'none':
            #     # Parse border value to ensure it's valid CSS. ODT might use "0.05pt solid #000000"
            #     # We might want to ensure a minimum width for visibility if it's very thin
            #     parts = border_val.split()
            #     if len(parts) >= 3 and parts[0].endswith('pt'):
            #         try:
            #             width = float(parts[0][:-2])
            #             if width < 0.5:
            #                 # Ensure minimum visibility
            #                 parts[0] = "0.5pt"
            #                 border_val = " ".join(parts)
            #         except ValueError:
            #             pass
            #     style_dict[border_prop] = border_val
        
        bg_color = props.get(f"{{{NAMESPACES['fo']}}}background-color")
        if bg_color and bg_color != 'transparent':
            style_dict['background-color'] = bg_color
        
        vertical_align = props.get(f"{{{NAMESPACES['style']}}}vertical-align")
        if vertical_align:
            style_dict['vertical-align'] = vertical_align
    
    def _extract_graphic_properties(self, props: ET.Element, style_dict: dict, extra_style_dict: dict) -> None:
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

        # # Also check for fo:border properties which might be used in graphic styles
        for border_prop in ['border', 'border-top', 'border-bottom', 'border-left', 'border-right']:
            border_val = props.get(f"{{{NAMESPACES['fo']}}}{border_prop}")
            if border_val is not None:
                style_dict[border_prop] = border_val
            # if border_val and border_val != 'none':
            #     parts = border_val.split()
            #     if len(parts) >= 3 and parts[0].endswith('pt'):
            #         try:
            #             width = float(parts[0][:-2])
            #             if width < 0.5:
            #                 parts[0] = "0.5pt"
            #                 border_val = " ".join(parts)
            #         except ValueError:
            #             pass
            #     style_dict[border_prop] = border_val

        # Padding/Margin
        padding = props.get(f"{{{NAMESPACES['fo']}}}padding")
        if padding: style_dict['padding'] = padding
        margin = props.get(f"{{{NAMESPACES['fo']}}}margin")
        if margin: style_dict['margin'] = margin

        # Wrap properties
        # wrap: https://docs.oasis-open.org/office/OpenDocument/v1.3/os/part3-schema/OpenDocument-v1.3-os-part3-schema.html#property-style_wrap
        # run-through: https://docs.oasis-open.org/office/OpenDocument/v1.3/os/part3-schema/OpenDocument-v1.3-os-part3-schema.html#__RefHeading__1420150_253892949
        # horizontal-pos: https://docs.oasis-open.org/office/OpenDocument/v1.3/os/part3-schema/OpenDocument-v1.3-os-part3-schema.html#__RefHeading__1420028_253892949
        # wrap = biggest | dynamic | left | none | parallel | right | run-through
        # run-through: background | foreground
        
        wrap = props.get(f"{{{NAMESPACES['style']}}}wrap")
        if wrap: extra_style_dict['wrap'] = wrap
        
        run_through = props.get(f"{{{NAMESPACES['style']}}}run-through")
        if run_through: extra_style_dict['run-through'] = run_through
        
        # NOTE: this is currently not used
        # horizontal_pos = props.get(f"{{{NAMESPACES['style']}}}horizontal-pos")
        # if horizontal_pos: extra_style_dict['horizontal-pos'] = horizontal_pos

    def _parse_odt_transform(self, transform_str: str) -> dict:
        """Parse ODT draw:transform attribute.
        
        ODT transform syntax: "rotate (angle) translate (x y)" 
        where angle is in radians, and x/y are dimensions like "1.5in".
        
        Returns dict with keys: 'rotate' (radians), 'translate_x', 'translate_y'
        """
        result = {'rotate': None, 'translate_x': None, 'translate_y': None}
        if not transform_str:
            return result
        
        # Parse rotate
        rotate_match = re.search(r'rotate\s*\(\s*([-\d.]+)\s*\)', transform_str)
        if rotate_match:
            result['rotate'] = float(rotate_match.group(1))
        
        # Parse translate - ODT uses "translate (x y)" with space separator
        translate_match = re.search(r'translate\s*\(\s*([\d.]+\w+)\s+([\d.]+\w+)\s*\)', transform_str)
        if translate_match:
            result['translate_x'] = translate_match.group(1)
            result['translate_y'] = translate_match.group(2)
        
        return result

    def _get_meta_title(self, odt_zip: zipfile.ZipFile) -> str | None:
        """Extract title from meta.xml if available."""
        if 'meta.xml' not in odt_zip.namelist():
            return None
            
        try:
            meta_xml = odt_zip.read('meta.xml').decode('utf-8')
            root = ET.fromstring(meta_xml)
            
            # Find dc:title in office:meta
            # Note: namespaces are registered globally but need careful handling in find
            # dc uses http://purl.org/dc/elements/1.1/
            
            ns = {'dc': NAMESPACES['dc'], 'office': NAMESPACES['office']}
            meta_office = root.find(f"{{{NAMESPACES['office']}}}meta")
            if meta_office is not None:
                title_elem = meta_office.find(f"{{{NAMESPACES['dc']}}}title")
                if title_elem is not None and title_elem.text:
                    return title_elem.text.strip()
        except Exception:
            pass
            
        return None

    def _find_title_candidates(self, content_xml: str) -> dict:
        """Parse content to find title candidates (styled title, h1)."""
        candidates = {'styled_title': None, 'h1_title': None}
        
        try:
            root = ET.fromstring(content_xml)
            body = root.find(f".//{{{NAMESPACES['office']}}}text")
            if body is None:
                return candidates
                
            # Iterate through direct children to find first candidates
            for child in body:
                tag = child.tag.split('}')[-1]
                
                # Check for "Title" style (including parent style inheritance)
                if tag == 'p' and not candidates['styled_title']:
                    style_name = child.get(f"{{{NAMESPACES['text']}}}style-name", "")
                    if self._is_title_style(style_name, root):
                        text_content = "".join(child.itertext()).strip()
                        if text_content:
                            candidates['styled_title'] = text_content
                
                # Check for Heading 1
                if tag == 'h' and not candidates['h1_title']:
                    level = child.get(f"{{{NAMESPACES['text']}}}outline-level", "1")
                    if level == "1":
                        text_content = "".join(child.itertext()).strip()
                        if text_content:
                            candidates['h1_title'] = text_content
                
                if candidates['styled_title'] and candidates['h1_title']:
                    break
                    
        except Exception:
            pass
            
        return candidates

    def _is_title_style(self, style_name: str, root: ET.Element) -> bool:
        """Check if a style is a Title style, including parent style inheritance."""
        if not style_name:
            return False
            
        # Direct match
        if 'title' in style_name.lower():
            return True
        
        # Check parent style chain using parsed styles or the XML
        visited = set()  # Prevent infinite loops
        current_style = style_name
        
        while current_style and current_style not in visited:
            visited.add(current_style)
            
            # First check in self.styles (which has already parsed parent-style-name)
            # But self.styles may not have parent-style-name stored directly.
            # Let's search the XML for the style definition
            
            # Find style in automatic-styles or office:styles
            style_elem = None
            for style in root.iter(f"{{{NAMESPACES['style']}}}style"):
                if style.get(f"{{{NAMESPACES['style']}}}name") == current_style:
                    style_elem = style
                    break
            
            if style_elem is None:
                break
                
            parent_style = style_elem.get(f"{{{NAMESPACES['style']}}}parent-style-name")
            if parent_style:
                if 'title' in parent_style.lower():
                    return True
                current_style = parent_style
            else:
                break
                
        return False

    def _determine_title(self, odt_zip: zipfile.ZipFile, content_xml: str) -> str:
        """Determine the document title based on precedence rules."""
        # 1. User Argument
        if self.overridden_title:
            return self.overridden_title
            
        # 2. Metadata
        if self.use_meta_title:
            meta_title = self._get_meta_title(odt_zip)
            if meta_title:
                return meta_title
        
        # Parse content candidates if needed
        candidates = None
        if self.use_styled_title or self.use_h1_title:
            candidates = self._find_title_candidates(content_xml)
            
        # 3. Styled Title
        if self.use_styled_title and candidates and candidates['styled_title']:
            return candidates['styled_title']
            
        # 4. Heading 1
        if self.use_h1_title and candidates and candidates['h1_title']:
            return candidates['h1_title']
            
        # 5. Fallback Argument
        if self.fallback_title:
            return self.fallback_title
            
        # 6. Filename
        if self.use_filename_title:
            return self.odt_path.stem
            
        # 7. None / Default
        return ""
    
    def _get_style_string(self, style_name: str, predicate: Optional[Callable[[str],bool]] = None) -> str:
        """Get CSS style string for a named style."""
        if style_name not in self.styles:
            return ""
        
        props = self.styles[style_name]
        return "; ".join(f"{k}: {v}" for k, v in props.items() if predicate is None or predicate(k))

    def _get_text_decoration(self, style_name: str) -> TextDecoration:
        """Get CSS style string for a named style."""
        text_decoration = self.text_decorations[style_name]
        return text_decoration

    def _convert_content(self, content_xml: str) -> str:
        """Convert ODT content XML to HTML body content."""
        root = ET.fromstring(content_xml)
        
        # Find the body/text element
        body = root.find(f".//{{{NAMESPACES['office']}}}text")
        if body is None:
            return "<p>No content found in document.</p>"
            
        # Process content with pagination
        pages = []
        current_page_content = []
        self.current_page_anchors = [] # Reset anchors
        
        def start_new_page():
            nonlocal current_page_content
            # Finish current page
            page_inner_html = "\n".join(current_page_content)
            
            # Add hoisted page anchors
            anchors_html = "".join(self.current_page_anchors)
            self.current_page_anchors = [] # Reset for next page
            
            # Construct page div
            w = self.page_properties.get('width', '21cm')
            h = self.page_properties.get('height', '29.7cm')
            mt = self.page_properties.get('margin-top', '2cm')
            mb = self.page_properties.get('margin-bottom', '2cm')
            ml = self.page_properties.get('margin-left', '2cm')
            mr = self.page_properties.get('margin-right', '2cm')
            
            # Convert dimensions to pixels for consistent rendering if needed, 
            # but using CSS strings is fine if they are units like 'cm'.
            # Note: Explicit dimensions are crucial for absolute positioning reliability.
            
            page_style = (f"width: {w}; min-height: {h}; "
                          f"padding: {mt} {mr} {mb} {ml}; "
                          f"box-sizing: border-box")
            
            content_style = "position: relative; width: 100%; height: 100%;"
            
            page_html = (f'<div class="anchor-page" style="{page_style}">'
                         f'<div class="anchor-page-content" style="{content_style}">'
                         f'{page_inner_html}{anchors_html}'
                         f'</div></div>')
            
            pages.append(page_html)
            current_page_content = []

        
        for child in body:
            tag = child.tag.split('}')[-1]
            
            # Check for page breaks
            is_break = False
            
            # 1. Explicit soft-page-break at top level
            if tag == 'soft-page-break':
                is_break = True
            
            # 2. Paragraph with break-before style
            if tag in ('p', 'h'):
                style_name = child.get(f"{{{NAMESPACES['text']}}}style-name", "")
                if style_name in self.styles and self.styles[style_name].get('break-before') == 'page':
                    is_break = True
                
                # 3. Check for soft-page-break as *first* child of paragraph (effectively a page break)
                # Optimization to avoid splitting: if it's at start, break before para.
                if len(child) > 0:
                     first_child_tag = child[0].tag.split('}')[-1]
                     if first_child_tag == 'soft-page-break':
                         is_break = True
                         # We can optionally remove the soft-page-break node to avoid double processing?
                         # _process_paragraph handles soft-page-break by returning empty span or nothing.
            
            if is_break and current_page_content:
                start_new_page()
            
            # Process element
            # We use a simplified dispatch here for top-level elements
            # Reuse _process_element dispatch logic but for single item
            
            # We create a dummy wrapper to use _process_element? 
            # Or just call specific methods. 
            # _process_element iterates. Let's make a single element dispatcher.
            
            html_part = self._process_single_element(child)
            if html_part:
                current_page_content.append(html_part)
        
        # Flush final page
        if current_page_content or self.current_page_anchors:
            start_new_page()
            
        return "\n".join(pages)

    def _process_single_element(self, child: ET.Element) -> str:
        """Process a single top-level element."""
        tag = child.tag.split('}')[-1]
        
        if tag == 'p':
            return self._process_paragraph(child)
        elif tag == 'h':
            return self._process_heading(child)
        elif tag == 'list':
            return self._process_list(child)
        elif tag == 'table':
            return self._process_table(child)
        elif tag == 'section':
            return self._process_element(child) # Recursively process section
        elif tag == 'frame':
            return self._process_frame(child)
        elif tag == 'soft-page-break':
             # Handled by loop, but if we process it, return empty or marker
             return "" 
        elif tag == 'text-box':
             return self._process_text_box(child, [])
        else:
             return ""

    def _process_element(self, element: ET.Element) -> str:
        """Process an XML element and convert to HTML (Recursive)."""
        html_parts = []
        for child in element:
            html_parts.append(self._process_single_element(child))
        return '\n'.join(p for p in html_parts if p)
    
    def _process_paragraph(self, para: ET.Element) -> str:
        """Process a paragraph element."""
        style_name = para.get(f"{{{NAMESPACES['text']}}}style-name", "")
        text_decoration = self._get_text_decoration(style_name)
        style_str = self._get_style_string(style_name)
        
        # Split content into inline text, paragraph anchors, and page anchors
        inline_content, anchored_content_list, page_anchors_list = self._process_paragraph_content_split(para, text_decoration)
        
        # Hoist page anchors to global state
        if page_anchors_list:
            self.current_page_anchors.extend(page_anchors_list)
        
        inline_content = text_decoration.wrap(inline_content)
        if not inline_content.strip() and not anchored_content_list:
            inline_content = "&nbsp;"  # Preserve empty paragraphs
        elif not inline_content.strip():
            # Ensure paragraph has height if it contains anchors but no text
            inline_content = "&nbsp;"
        
        if anchored_content_list:
            anchored_html = "".join(anchored_content_list)
            style_attr = f' style="position:relative;{style_str}"'
            result = f'<p class="anchor-paragraph"{style_attr}>{anchored_html}{inline_content}</p>'
        else:
            style_attr = f' style="{style_str}"' if style_str else ''
            result = f'<p {style_attr}>{inline_content}</p>'
        # TODO: use <span calss="p"> instead of <p> in inline context
        return result

    def _get_element_box(self, element: ET.Element) -> tuple[int,int,int,int]:
        x = element.get(f"{{{NAMESPACES['svg']}}}x")
        if x is None: return None
        y = element.get(f"{{{NAMESPACES['svg']}}}y")
        if y is None: return None
        width = element.get(f"{{{NAMESPACES['svg']}}}width")
        if width is None: return None
        height = element.get(f"{{{NAMESPACES['svg']}}}height")
        if height is None: return None
        return (Length.from_str(x),Length.from_str(y),Length.from_str(width),Length.from_str(height))
    
    def _get_element_wrap_properties(self, element: ET.Element) -> tuple[str,str]:
        # Get style name and properties
        style_name = element.get(f"{{{NAMESPACES['draw']}}}style-name", "")
        if style_name in self.styles:
            frame_style = self.extra_styles[style_name]
            wrap = frame_style.get('wrap', 'none')
            run_through = frame_style.get('run-through', 'background')
            return wrap,run_through
        else:
            return 'none', 'background'

    _WRAP_TO_WRAP_MODE_MAP = {
        'left': 'left',
        'right': 'right',
        'biggest': 'left',
        'dynamic': 'left',
        'parallel': 'left',
        'run-through': 'through',
        'none': 'none',
    }
    @classmethod
    def _map_wrap_properties_to_wrap_mode(cls, wrap, through) -> str:
        default_wrap_mode = 'none'
        return cls._WRAP_TO_WRAP_MODE_MAP.get(wrap, default_wrap_mode)
    
    _WRAP_MODE_TO_FLOAT_MODE_MAP = {
        'left': 'right',
        'right': 'left',
        'none': 'left',
        # 'through': 'none',
    }
    @classmethod
    def _map_wrap_mode_to_float_mode(cls, wrap_mode) -> str | None:
        # use None instead of 'none' for not creating the span element but do nothing
        default_float_mode = None
        # default_float_mode = 'none'
        return cls._WRAP_MODE_TO_FLOAT_MODE_MAP.get(wrap_mode, default_float_mode)

    @staticmethod
    def _bonund_boxes(boxes):
        # boxes: list[(x,y,w,h)]
        y_min,y_max=None,None
        x_min,x_max=None,None
        for box in boxes:
            x,y,w,h = box
            x_low,x_high = min(x,x+w),max(x,x+w)
            y_low,y_high = min(y,y+h),max(y,y+h)
            if y_max is None or y_max < y_high: y_max = y_high
            if y_min is None or y_min > y_low:  y_min = y_low
            if x_max is None or x_max < x_high: x_max = x_high
            if x_min is None or x_min > x_low:  x_min = x_low
        return x_min,x_max,y_min,y_max

    @staticmethod
    def _generate_float_span(boxes, wrap_modes):
        # accept boxes and wrap modes
        # wrap_mode should not be through
        cls = ODTConverter
        assert len(boxes) == len(wrap_modes)
        box_count = len(boxes)
        result = ''
        if box_count == 0:
            pass
        elif box_count == 1:
            xy_boundary = cls._bonund_boxes(boxes)
            assert len(xy_boundary) == 4 and all(value is not None for value in xy_boundary)
            wrap_mode = wrap_modes[0]
            x_min,x_max,y_min,y_max = xy_boundary
            if wrap_mode == 'none':
                x_min,x_max = '0','100%'
            float_mode = cls._map_wrap_mode_to_float_mode(wrap_mode)
            result = (
                f'<span style="float:{float_mode};width:100%;height:{y_max};shape-outside:polygon('
                f'{x_min} {y_min},{x_max} {y_min},{x_max} {y_max},{x_min} {y_max}'
                ')"></span>'
            ) if float_mode is not None else ''
        else: # box_count > 0
            intervals = [(y,y+h) for x,y,w,h in boxes]
            assert intervals
            intervals,indices_group = merge_intervals(intervals)
            upper_paths, lower_paths = skyline_paths([(y,x,h,w) for x,y,w,h in boxes])
            element_strs = []
            y_base = Length(0, boxes[0][0].unit)
            for interval, indices, upper_path, lower_path in zip(intervals,indices_group,upper_paths,lower_paths):
                first_index = indices[0]
                wrap_mode = wrap_modes[first_index]
                float_mode = cls._map_wrap_mode_to_float_mode(wrap_mode)
                if wrap_mode == 'right':
                    assert float_mode is not None
                    y_low, y_high = interval
                    dy_low = y_low - y_base
                    dy_high = y_high - y_base
                    polygon_strs = []
                    y = upper_path[0][0]
                    dy = y - y_base
                    polygon_strs.append(f'0 {dy}')
                    for y,x in upper_path:
                        dy = y - y_base
                        polygon_strs.append(f'{x} {dy}')
                    y = upper_path[-1][0]
                    dy = y - y_base
                    polygon_strs.append(f'0 {dy}')
                    polygon_str = ','.join(polygon_strs)
                    element_str = (
                        f'<span style="float:{float_mode};width:100%;height:{dy};shape-outside:polygon('
                        f'{polygon_str}'
                        ')"></span>'
                    )
                    element_strs.append(element_str)
                    y_base = y_high
                elif wrap_mode == 'left':
                    assert float_mode is not None
                    y_low, y_high = interval
                    dy_low = y_low - y_base
                    dy_high = y_high - y_base
                    polygon_strs = []
                    y = lower_path[0][0]
                    dy = y - y_base
                    polygon_strs.append(f'100% {dy}')
                    for y,x in lower_path:
                        dy = y - y_base
                        polygon_strs.append(f'{x} {dy}')
                    y = lower_path[-1][0]
                    dy = y - y_base
                    polygon_strs.append(f'100% {dy}')
                    polygon_str = ','.join(polygon_strs)
                    element_str = (
                        f'<span style="float:{float_mode};width:100%;height:{dy};shape-outside:polygon('
                        f'{polygon_str}'
                        ')"></span>'
                    )
                    element_strs.append(element_str)
                    y_base = y_high
                elif wrap_mode == 'none':
                    assert float_mode is not None
                    y_low, y_high = interval
                    dy_low = y_low - y_base
                    dy_high = y_high - y_base
                    element_str = (
                        f'<span style="float:{float_mode};width:100%;height:{dy_high};shape-outside:polygon('
                        f'0 {dy_low},100% {dy_low},100% {dy_high},0 {dy_high}'
                        ')"></span>'
                    )
                    element_strs.append(element_str)
                    y_base = y_high
            result = ''.join(element_strs)

        return result

    def _process_paragraph_content_split(self, element: ET.Element, text_decoration: TextDecoration) -> tuple[str, list[str], list[str]]:
        """Process paragraph content, separating inline content, paragraph anchors, and page anchors."""
        # NOTE: Maybe respect element order
        inline_parts = []
        anchored_parts = []
        boxes = []
        wrap_modes = []
        page_anchors = []

        # Add element's direct text
        if element.text:
            inline_parts.append(escape(element.text))
            
        for child in element:
            anchor_type = child.get(f"{{{NAMESPACES['draw']}}}anchor-type")
            if not anchor_type:
                anchor_type = child.get(f"{{{NAMESPACES['text']}}}anchor-type")
            
            # Determine if this is a paragraph-anchored object or page-anchored
            is_para_anchored = (anchor_type == 'paragraph')
            is_page_anchored = (anchor_type == 'page')
            
            if is_para_anchored:
                box = self._get_element_box(child)
                wrap_props = self._get_element_wrap_properties(child)
                wrap_mode = self._map_wrap_properties_to_wrap_mode(*wrap_props)
                if box and wrap_props and wrap_mode != 'through':
                    assert wrap_mode in ('left', 'right', 'none')
                    boxes.append(box)
                    wrap_modes.append(wrap_mode)

            child_html = self._process_child_to_html(child, text_decoration)
            
            # FIXME following ignores the orignal elements order in content.xml
            if is_page_anchored:
                page_anchors.append(child_html)
            elif is_para_anchored:
                anchored_parts.append(child_html)
            else:
                inline_parts.append(child_html)
            
            # Tail text always belongs to the inline flow
            if child.tail:
                inline_parts.append(escape(child.tail))
        
        float_span = self._generate_float_span(boxes, wrap_modes)
        if float_span:
            anchored_parts.insert(0, float_span)
                
        return "".join(inline_parts), anchored_parts, page_anchors 

    def _process_heading(self, heading: ET.Element) -> str:
        """Process a heading element."""
        level = heading.get(f"{{{NAMESPACES['text']}}}outline-level", "1")
        level = min(int(level), 6)  # HTML only supports h1-h6
        
        style_name = heading.get(f"{{{NAMESPACES['text']}}}style-name", "")
        style_str = self._get_style_string(style_name)
        text_decoration = self._get_text_decoration(style_name)
        
        content = self._process_inline_content(heading, text_decoration)
        content = text_decoration.wrap(content)
        
        style_attr = f' style="{style_str}"' if style_str else ''
        return f'<h{level}{style_attr}>{content}</h{level}>'

    def _process_inline_content(self, element: ET.Element, text_decoration: TextDecoration=TextDecoration()) -> str:
        """Process inline content within a paragraph or heading."""
        parts = []
        
        # Add element's direct text
        if element.text:
            parts.append(escape(element.text))
        
        for child in element:
            parts.append(self._process_child_to_html(child, text_decoration))
            
            # Add tail text
            if child.tail:
                parts.append(escape(child.tail))
        
        return "".join(parts)
    
    def _process_child_to_html(self, child: ET.Element, text_decoration: TextDecoration) -> str:
        """Process a single child element to HTML."""
        tag = child.tag.split('}')[-1]
        
        # Check for positioning attributes on the element
        anchor_type = child.get(f"{{{NAMESPACES['draw']}}}anchor-type")
        element_style = []
        x = child.get(f"{{{NAMESPACES['svg']}}}x")
        y = child.get(f"{{{NAMESPACES['svg']}}}y")
        width = child.get(f"{{{NAMESPACES['svg']}}}width")
        height = child.get(f"{{{NAMESPACES['svg']}}}height")
        transform_str = child.get(f"{{{NAMESPACES['draw']}}}transform")
        
        # Parse transform if present
        transform_info = self._parse_odt_transform(transform_str) if transform_str else {}
        has_transform_position = transform_info.get('translate_x') or transform_info.get('translate_y')
        
        if (x and y) or has_transform_position or anchor_type in ('paragraph', 'page', 'char'):
            # Shapes with x/y coordinates, or transform with translate, or paragraph/page/char anchor
            # are positioned absolutely within their container
            element_style.append("position: absolute")

            
            # Use transform translate if available, otherwise use x/y
            if has_transform_position:
                element_style.append(f"left: {transform_info.get('translate_x', '0')}")
                element_style.append(f"top: {transform_info.get('translate_y', '0')}")
            else:
                if x: element_style.append(f"left: {x}")
                if y: element_style.append(f"top: {y}")
            
            # Apply rotation if present
            if transform_info.get('rotate'):
                angle_rad = -transform_info['rotate']  # Negate for CSS
                element_style.append(f"transform: rotate({angle_rad}rad)")
                element_style.append("transform-origin: 0 0")
        else:
            # As-char elements, unset anchor, or only partial coordinates → flow inline
            element_style.append("display: inline-block")
            element_style.append("vertical-align: text-bottom")
        
        # NOTE: currently only span and line-break enable nowrap for line-decoration.
        # NOTE: may come back for other in the future ?
        if tag == 'span':
            result = self._process_span(child, text_decoration)
            # NOTE just prevent text_decoration propagate to inner elements
            result = text_decoration.nowrap(result)
        elif tag == 's':
            # Spaces
            count = int(child.get(f"{{{NAMESPACES['text']}}}c", "1"))
            result = '&nbsp;' * count
        elif tag == 'tab':
            result = '&emsp;'
        elif tag == 'line-break':
            result = '<br>'
            result = text_decoration.nowrap(result)
        elif tag == 'a':
            result = self._process_link(child)
        elif tag == 'frame':
            result = self._process_frame(child)
        elif tag == 'bookmark' or tag == 'bookmark-start' or tag == 'bookmark-end':
            name = child.get(f"{{{NAMESPACES['text']}}}name", "")
            if name:
                result = f'<a id="{escape(name)}"></a>'
            result = ""
        elif tag == 'note':
            result = self._process_note(child)
        elif tag == 'soft-page-break':
            if self.show_page_breaks:
                result = '<span class="inline-page-break"></span>'
            result = ""
        elif tag == 'sequence':
            result = self._process_sequence(child)
        elif tag == 'note-ref':
            ref_name = child.get(f"{{{NAMESPACES['text']}}}ref-name", "")
            content = self._process_inline_content(child)
            result = f'<sup><a href="#ref-{ref_name}" class="footnote-ref">{content}</a></sup>'
        elif tag == 'custom-shape':
            result = self._process_custom_shape(child, child, element_style)
        elif tag == 'rect':
            result = self._process_drawing_rect(child, child, element_style)
        elif tag == 'ellipse':
            result = self._process_drawing_ellipse(child, child, element_style)
        elif tag == 'line':
            result = self._process_drawing_line(child, element_style)
        elif child.text:
            # Try to get any text content
            result = escape(child.text)
        else:
            result = ""
        # result = text_decoration.nowrap(result) if result else ""
        return result

    
    def _process_sequence(self, seq: ET.Element) -> str:
        """Process a sequence element (figure/table numbering)."""
        # The sequence text is the number itself
        seq_text = seq.text or ""
        return escape(seq_text)
    
    def _process_span(self, span: ET.Element, base_text_decoration: TextDecoration) -> str:
        """Process a text span element."""
        style_name = span.get(f"{{{NAMESPACES['text']}}}style-name", "")
        style_str = self._get_style_string(style_name)
        text_decoration = self._get_text_decoration(style_name)
        text_decoration.inherit(base_text_decoration)
        content = self._process_inline_content(span, text_decoration)
        content = text_decoration.wrap(content)
        if style_str:
            return f'<span style="{style_str}">{content}</span>'
        return content
    
    def _process_link(self, link: ET.Element) -> str:
        """Process a hyperlink element."""
        href = link.get(f"{{{NAMESPACES['xlink']}}}href", "#")
        content = self._process_inline_content(link)
        
        return f'<a href="{escape(href)}">{content}</a>'
    
    @staticmethod
    def _remap_z_index(z_index: int | str, is_position_absolute: bool, through: str | None) -> int | None:
        remapped_z_index = None
        if isinstance(z_index, str):
            try:
                z_index = int(z_index)
            except:
                z_index = None
        if z_index is not None:
            # z-index mapping example
            # 1,2,3,4    => 11,12,13,14
            # 0,-1,-2,-3 => -10,-11,-12,-13
            # -899,-900,-901,-902 => -909,-910,-910,-910
            remapped_z_index = z_index + 10 if z_index > 0 else z_index - 10
            remapped_z_index = max(-910, remapped_z_index)
        elif is_position_absolute:
            # supply default z_index value if position is absolute
            # let z be negative by default to let the text flow through it
            if through == 'foreground': remapped_z_index = 5
            elif through == 'background': remapped_z_index = -5
            else: remapped_z_index = -3
        else:
            # remapped_z_index = -2
            pass
        return remapped_z_index

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
                # NOTE: let user decide if they need pretty border wrap ?
                disable_draw_frame_border_box = True # better border line visually
                # disable_draw_frame_border_box = False
                if not disable_draw_frame_border_box:
                    style_parts.append("box-sizing: border-box")
        
        # Check for absolute positioning
        x = frame.get(f"{{{NAMESPACES['svg']}}}x")
        y = frame.get(f"{{{NAMESPACES['svg']}}}y")
        anchor_type = frame.get(f"{{{NAMESPACES['draw']}}}anchor-type")
        if not anchor_type:
            anchor_type = frame.get(f"{{{NAMESPACES['text']}}}anchor-type")
        
        
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
                # if cx: child_style.append(f"left: {cx}")
                # if cy: child_style.append(f"top: {cy}")
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
                # frame_content_parts.append(self._process_image(child, child_style, frame_name))
            elif tag == 'text-box':
                # Text box needs to be a positioning context for shapes inside
                # Get min-height from the text-box element
                tb_min_height = child.get(f"{{{NAMESPACES['fo']}}}min-height", "")
                # tb_style = ["position: relative"]  # Always relative for positioned children
                tb_style = []
                tb_style.extend(child_style)
                if tb_min_height:
                    tb_style.append(f"min-height: {tb_min_height}")
                
                content = self._process_text_box_content(child)
                s = "; ".join(tb_style)
                # frame_content_parts.append(f'<div class="text-box-container" style="{s}">{content}</div>')
                # NOTE: Setting font-size to be zero, to supress unwanted actual line-height 
                # as line-height usually setted as ratio to current font-size, 
                # don't set line-height to zero so that the inner text cloud inherit the line-height ratio with thier custom font sizes
                # NOTE: width is set to be wider for fitting the text overflow issue in web view but not in office, possible cause by different font
                compensation_style_str= (
                    "font-size:0;"
                    # "line-height:1.5;"
                    "width:110%;"
                )
                frame_content_parts.append(f'<span class="div text-box-container" style="{compensation_style_str}{s}">{content}</span>')
            elif tag == 'custom-shape':
                # frame_content_parts.append(self._process_custom_shape(frame, child, style_parts.copy() + child_style))
                frame_content_parts.append(self._process_custom_shape(frame, child, child_style))
            elif tag == 'rect':
                # frame_content_parts.append(self._process_drawing_rect(frame, child, style_parts.copy() + child_style))
                frame_content_parts.append(self._process_drawing_rect(frame, child, child_style))
            elif tag == 'ellipse':
                # frame_content_parts.append(self._process_drawing_ellipse(frame, child, style_parts.copy() + child_style))
                frame_content_parts.append(self._process_drawing_ellipse(frame, child, child_style))
            elif tag == 'line':
                # frame_content_parts.append(self._process_drawing_line(child, style_parts.copy() + child_style))
                frame_content_parts.append(self._process_drawing_line(child, child_style))
            elif tag == 'object':
                # OLE object - try to find replacement image
                replacement_img = frame.find(f".//{{{NAMESPACES['draw']}}}image")
                if replacement_img is not None:
                    # frame_content_parts.append(self._process_image(replacement_img, style_parts.copy() + child_style, frame_name))
                    frame_content_parts.append(self._process_image(replacement_img, child_style, frame_name))
        
        # If we have positioned children, the container must be relative
        # if as-char  should relative to anchor ?
        position_style_parts = []
        position_style_str = ''
        is_position_absolute = False
        if has_positioned_children:
            position_style_parts.append("position: relative")
        elif (x or y) and anchor_type != 'as-char':
            position_style_parts.append("position: absolute")
            is_position_absolute = True
            if x: position_style_parts.append(f"left: {x}")
            if y: position_style_parts.append(f"top: {y}")
        elif anchor_type == 'as-char':
            position_style_parts.append("position: relative")
            # as-char svg:x & svg:y are taken care by the helper (anchor, aligner, padder) later
            pass
        position_style_str = ';'.join(position_style_parts)

        # z-index assignment
        z_index = frame.get(f"{{{NAMESPACES['draw']}}}z-index", None)
        wrap,through = self._get_element_wrap_properties(frame)
        z_index = self._remap_z_index(z_index, is_position_absolute, through)
        if z_index is not None:
            style_parts.append(f'z-index: {z_index}')
        # WORKAROUND: To provide both view for absolute objects and text flows, 
        # as current absolute objects doesn't have collision box, 
        # and just let the text flow through, so setting opacity and/or z-index
        # to enable user to be able to view both.
        if is_position_absolute:
            # style_parts.append("opacity: 0.9")
            # style_parts.append("z-index: -10")
            pass
            
        # If we found content, return it
        if frame_content_parts:
            # Wrap in the main frame div
            style_str = "; ".join(style_parts)
            content = '\n'.join(part for part in frame_content_parts if part)
            if anchor_type == 'as-char':
                # Process svg:x
                x_is_defined = isinstance(x, str)
                x_value = 0
                if x_is_defined:
                    x_sign, x_number, x_unit = extract_sign_number_unit_str(x)
                    x_abs = x_number + x_unit
                    x_value = x_abs
                # Process svg:y
                y_is_defined = isinstance(y, str)
                if y_is_defined:
                    y_sign, y_number, y_unit = extract_sign_number_unit_str(y)
                    y_is_zero_or_positive = not is_sign_str_negative(y_sign) 
                    y_abs = y_number + y_unit
                    if y_is_zero_or_positive:
                        svgy_align_elements_str:str = (
                            f'<span class="svgy-positive-aligner"></span>'
                            f'<span class="svgy-positive-padder" style="height:{y_abs}"></span>'
                        )
                    else:
                        svgy_align_elements_str = f'<span class="svgy-negative-aligner-padder" style="height:{y_abs}"></span>'
                else:
                    # the height is defaulted to auto, to match the height of the contained frame
                    svgy_align_elements_str = f'<span class="svgy-negative-aligner-padder"></span>'
                return (
                    # f'<span style="display:inline-grid;grid-template-columns:0 auto;grid-template-rows:{x_value} auto auto;line-height:1.2;{position_style_str}">' 
                    # f'<span class="anchor-char" style="display:inline-grid;grid-template-columns:0 auto;grid-template-rows:{x_value} auto auto;line-height:0;{position_style_str}">' 
                    f'<span class="anchor-char" style="display:inline-grid;grid-template-columns:0 auto;grid-template-rows:{x_value} auto auto;{position_style_str}">' 
                    # f'<span class="anchor-as-char" style="display:inline-grid;grid-template-columns:0 auto;grid-template-rows:{x_value} auto auto;{position_style_str}">' 
                    f'{svgy_align_elements_str}' 
                    f'<span class="div draw-frame" style="grid-column:2;grid-row:3;{style_str}">{content}</span>'
                    f'</span>'
                )
            else:
                # NOTE: Use tag div instead of span because nesting div in span is invalid html and cause undefined behavior
                # NOTE: Use tag div to ensure it has block display to contain size
                # NOTE: display is set by div as block by default for draw-frame
                return f'<span class="div draw-frame" style="{style_str};{position_style_str}">{content}</span>'

        
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
                    # NOTE: HACK, Libreoffice seems doesn't respect margin-bottom, let's ignore it
                    style_str = self._get_style_string(style_name, lambda key: key not in {'margin-bottom'})
                    style_attr = f' style="{style_str}"' if style_str else ''
                    # NOTE: use span class=p instead of p for as-char shape/object
                    # parts.append(f'<p class="caption"{style_attr}>{content}</p>')
                    parts.append(f'<span class="p caption"{style_attr}>{content}</span>')
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
        
        # Base colors from style
        base_fill_color = shape_style.get('fill', '#e0e0e0' if 'fill' not in shape_style else 'none')
        base_stroke_color = shape_style.get('stroke', '#333333' if 'stroke' not in shape_style else 'none')
        stroke_width = shape_style.get('stroke-width', '1pt')
        
        # Override defaults if explicit NONE found in style dict (from fill="none")
        if shape_style.get('fill') == 'none':
            base_fill_color = 'none'
        if shape_style.get('stroke') == 'none':
            base_stroke_color = 'none'
        
        # ODT custom shapes usually have a viewBox coordinate system (e.g. 0 0 21600 21600)
        enhanced_geom = shape.find(f".//{{{NAMESPACES['draw']}}}enhanced-geometry")
        
        view_box = "0 0 21600 21600" # Default ODT viewbox
        subpaths = []
        
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
                subpaths = self._convert_path(raw_path, variables)
        
        # Check for text inside the shape
        text_content_parts = []
        # ODT puts text in a text-box or directly as P/List elements? 
        # Inside custom-shape it can have text:p
        for child in shape:
            tag = child.tag.split('}')[-1]
            if tag == 'p':
                # NOTE: use <span style="display:block"> instead of <p> for as-char shape
                # text_content_parts.append(f'<p style="margin:0; padding:0;">{self._process_inline_content(child)}</p>')
                text_content_parts.append(f'<span class="p" style="margin:0; padding:0;">{self._process_inline_content(child)}</span>')
            elif tag == 'list':
                text_content_parts.append(self._process_list(child))

        text_html = "".join(text_content_parts)

        # Construct SVG
        # We need to group subpaths by their fill/stroke requirements
        svg_paths_html = []
        
        if subpaths:
            # Group compatible paths to reduce DOM elements where possible
            # Compatible means same effective fill and stroke behavior
            current_group = []
            
            # Grouping key: (has_fill, has_stroke)
            current_key = None
            
            for sub in subpaths:
                # Determine effective colors for this subpath
                has_fill = sub['fill'] and base_fill_color != 'none'
                has_stroke = sub['stroke'] and base_stroke_color != 'none'
                
                key = (has_fill, has_stroke)
                
                if current_key is None:
                    current_key = key
                    current_group.append(sub['d'])
                elif key == current_key:
                    current_group.append(sub['d'])
                else:
                    # Flush current group
                    if current_group:
                        d_attr = " ".join(current_group)
                        fill_attr = base_fill_color if current_key[0] else "none"
                        stroke_attr = base_stroke_color if current_key[1] else "none"
                        # Use fill-rule="evenodd" to handle holes correctly (e.g. eyes in face)
                        svg_paths_html.append(f'<path d="{d_attr}" fill="{fill_attr}" stroke="{stroke_attr}" stroke-width="{stroke_width}" fill-rule="evenodd" vector-effect="non-scaling-stroke"/>')
                    
                    # Start new group
                    current_key = key
                    current_group = [sub['d']]
            
            # Flush final group
            if current_group:
                d_attr = " ".join(current_group)
                fill_attr = base_fill_color if current_key[0] else "none"
                stroke_attr = base_stroke_color if current_key[1] else "none"
                svg_paths_html.append(f'<path d="{d_attr}" fill="{fill_attr}" stroke="{stroke_attr}" stroke-width="{stroke_width}" fill-rule="evenodd" vector-effect="non-scaling-stroke"/>')
        else:
             # Fallback if no path but fallback rendering needed?
             pass
             
        svg_content = "\n".join(svg_paths_html)
              
        svg = f'''<svg width="{width}" height="{height}" viewBox="{view_box}" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">
            {svg_content}
        </svg>'''
        
        # If there is text, we need to overlay it. 
        # NOTE: ODT text inside shapes is usually centered or fully filling the shape box. adopt this apporach as approximation for now
        # We can use a relative container.
        # FIXME: should respect text box location in ODT
        
        style_str = "; ".join(style_parts)
        if "position" not in style_str:
            style_str += "; position: relative"
        if "display" not in style_str:
            style_str += "; display: inline-block"

        z_index = frame.get(f"{{{NAMESPACES['draw']}}}z-index", None)
        wrap, through = self._get_element_wrap_properties(frame)
        if z_index is not None:
            z_index = self._remap_z_index(z_index, True, through)
            style_str += f"; z-index: {z_index}"
            
        content = svg
        if text_html.strip():
            # Overlay text centered
            # NOTE: fix as-char issue, use span to avoid invalid html element hierarchy like <span><div></div></span>
            content += f'<span class="div" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: center; align-items: center; overflow: hidden;">{text_html}</span>'

        # NOTE: fix as-char issue, use span to avoid invalid html element hierarchy like <span><div></div></span>
        return f'<span class="div draw-custom-shape" style="{style_str}">{content}</span>'

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

    def _convert_path(self, path_data: str, variables: dict) -> list[dict]:
        """Convert ODT enhanced path to valid SVG path data chunks.
        
        Returns a list of dicts: {'d': str, 'fill': bool, 'stroke': bool}
        handling ODT commands like 'F' (No Fill), 'S' (No Stroke), 'N' (New Path).
        """
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
        subpaths = []
        current_path_cmds = []

        current_x = 0.0
        current_y = 0.0
        # Track start of subpath for Z (Close) - usually M sets this
        subpath_start_x = 0.0
        subpath_start_y = 0.0
        
        # Track subpath start state for implicit moves (U following N)
        is_subpath_start = True

        # Default state for new paths
        current_fill = True
        current_stroke = True
        
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
                    current_path_cmds.append(f"M {fmt(x)} {fmt(y)}")
                    current_x, current_y = x, y
                    subpath_start_x, subpath_start_y = x, y
                    is_subpath_start = False
                    i += 2
            elif cmd == 'L':
                # Abs Line: L x y
                if i + 1 < len(resolved_tokens):
                    x = resolved_tokens[i]
                    y = resolved_tokens[i+1]
                    current_path_cmds.append(f"L {fmt(x)} {fmt(y)}")
                    current_x, current_y = x, y
                    is_subpath_start = False
                    i += 2
            elif cmd == 'C':
                # Cubic Bezier: C x1 y1 x2 y2 x y
                if i + 5 < len(resolved_tokens):
                    coords = resolved_tokens[i:i+6]
                    current_path_cmds.append(f"C {' '.join(fmt(c) for c in coords)}")
                    current_x, current_y = coords[4], coords[5]
                    is_subpath_start = False
                    i += 6
            elif cmd == 'Z':
                current_path_cmds.append("Z")
                current_x, current_y = subpath_start_x, subpath_start_y
                # is_subpath_start remains False usually? 
                pass
            elif cmd == 'N':
                # End subpath - Flush current path
                if current_path_cmds:
                    subpaths.append({
                        'd': " ".join(current_path_cmds),
                        'fill': current_fill,
                        'stroke': current_stroke
                    })
                    current_path_cmds = []
                # Reset defaults for next subpath? 
                # ODF spec is vague but typically S/F resets or applies per subpath.
                # In common implementations, flags apply to the subpath they appear in (at end).
                # We assume flags (S, F) seen *before* N apply to the *just finished* subpath.
                # So we actually need to capture flags *before* processing N?
                # Wait, 'F' and 'S' are commands.
                # If we see F, we set current_fill = False.
                # If we see N, we commit.
                # Reset for next path?
                current_fill = True
                current_stroke = True
                is_subpath_start = True
                
            elif cmd == 'F':
                # No Fill for current subpath
                current_fill = False

            elif cmd == 'S':
                # No Stroke for current subpath
                current_stroke = False

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
                    current_path_cmds.append(f"A {fmt(rx)} {fmt(ry)} 0 0 0 {fmt(x)} {fmt(y)}")
                    
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
                    current_path_cmds.append(f"{action} {fmt(sx)} {fmt(sy)}")
                    
                    # Draw arcs
                    if abs(end_deg - start_deg) >= 360:
                        mid_rad = start_rad + math.pi
                        mid_x = cx + rx * math.cos(mid_rad)
                        mid_y = cy + ry * math.sin(mid_rad)
                        end_x = cx + rx * math.cos(end_rad)
                        end_y = cy + ry * math.sin(end_rad)
                        
                        current_path_cmds.append(f"A {fmt(rx)} {fmt(ry)} 0 1 1 {fmt(mid_x)} {fmt(mid_y)}")
                        current_path_cmds.append(f"A {fmt(rx)} {fmt(ry)} 0 1 1 {fmt(end_x)} {fmt(end_y)}")
                    else:
                        ex = cx + rx * math.cos(end_rad)
                        ey = cy + ry * math.sin(end_rad)
                        delta = end_deg - start_deg
                        large = 1 if abs(delta) > 180 else 0
                        sweep = 1 # Clockwise usually
                        current_path_cmds.append(f"A {fmt(rx)} {fmt(ry)} 0 {large} {sweep} {fmt(ex)} {fmt(ey)}")
                    
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
                
        # Flush any remaining commands
        if current_path_cmds:
            subpaths.append({
                'd': " ".join(current_path_cmds),
                'fill': current_fill,
                'stroke': current_stroke
            })

        return subpaths
    
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
        
        # use the applied style as default
        if style_name == '' and self.list_style_name_stack:
            style_name = self.list_style_name_stack[-1]
        self.list_style_name_stack.append(style_name)
        
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
        
        result = f'<{list_type}>{"".join(items_html)}</{list_type}>'

        self.list_style_name_stack.pop()
        return result
    
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
        # return f'<table{style_attr} border="1" cellspacing="0" cellpadding="4">{"".join(rows_html)}</table>'
        rows_html_str = "".join(rows_html)
        return f'<table{style_attr}>{rows_html_str}</table>'
    
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
    
    def _wrap_html(self, body_content: str, title: str = "") -> str:
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
        title_element_str = f'<title>{escape(title)}</title>' if title is not None else ''
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="generator" content="ODT to HTML Converter">
    {title_element_str}
    <style>
        body {{
            position: relative;
            z-index: -990;
            font-family: 'Noto Serif', 'Times New Roman', serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            color: #333;
            background-color: #f0f0f0;
        }}
        .anchor-page {{
            position: relative;
            z-index: -950;
            background-color: #fff;
            margin: 0 auto 30px auto;
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
            overflow: hidden; /* Ensure content stays within page */
        }}
        .anchor-page-content {{
            /* Position context for page anchors */
        }}
        .anchor-as-char {{
            display: inline-grid;
            position: relative;
            grid-template-columns: 0 auto; /* replace first item with custom svgx */
            grid-template-rows: 0 auto auto;
            line-height: 0;
        }}
        .svgy-positive-aligner {{
            display: inline-block;
            grid-column: 1;
            grid-row: 1;
            background-color: aqua;
            line-height:0;
        }}
        .svgy-positive-padder {{
            display: inline-block;
            grid-column: 1;
            grid-row: 2;
            background-color: chocolate;
            line-height:0;
        }}
        .svgy-negative-aligner-padder {{
            display: inline-block;
            grid-column: 1;
            grid-row: 3;
            background-color: cornflowerblue;
            line-height:0;
        }}
        .draw-frame {{
        }}
        /* p class for mimic p tag via span tag */
        .p {{
            display: block;
            margin: 0 0;
        }}
        .div {{
            display: block; 
        }}
        p {{
            /* hardcoded value */
            /* margin: 5em 0; */ /*for webpage use */
            margin: 0 0; /* for document use */
        }}
        h1, h2, h3, h4, h5, h6 {{
            margin-top: 1em;
            margin-bottom: 0.5em;
            color: #222;
        }}
        table {{
            border-collapse: collapse;
            /* margin: 1em 0; */
        }}
        th, td {{
            /* padding: 8px; */
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
            /*margin-top: 0.5em;*/
            margin-top: 0em;
            font-style: italic;
            color: #666;
            font-size: 0.9em;
        }}
        a {{
            color: #0066cc;
        }}
        ul, ol {{
            /* margin: 0.5em 0; */
            /* padding-left: 2em; */
        }}
        li {{
            /* margin: 0.25em 0; */
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
    parser.add_argument('--show-page-breaks', nargs='?', const=True, default=False, type=str_to_bool,
                        help='Show page break character in output HTML (default: False)')
                        
    # Title extraction arguments
    parser.add_argument('--title', help='Specify the title explicitly', default=None)
    
    # Feature flags for title extraction
    parser.add_argument('--title-from-metadata', nargs='?', const=True, default=True, type=str_to_bool,
                        help='Extract title from ODT metadata (default: True). Use --title-from-metadata=0 to disable.')
    parser.add_argument('--title-from-styled-title', nargs='?', const=True, default=True, type=str_to_bool,
                        help='Extract title from first "Title" styled paragraph (default: True). Use --title-from-styled-title=0 to disable.')
    parser.add_argument('--title-from-h1', nargs='?', const=True, default=True, type=str_to_bool,
                        help='Extract title from first Heading 1 (default: True). Use --title-from-h1=0 to disable.')
    parser.add_argument('--title-fallback', help='Fallback title if no other title found', default=None)
    parser.add_argument('--title-from-filename', nargs='?', const=True, default=False, type=str_to_bool,
                        help='Use filename as title if no other title found (default: False). Use --title-from-filename=1 to enable.')
    
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
        converter = ODTConverter(
            str(input_path), 
            show_page_breaks=args.show_page_breaks,
            title=args.title,
            title_from_metadata=args.title_from_metadata,
            title_from_styled_title=args.title_from_styled_title,
            title_from_h1=args.title_from_h1,
            title_from_filename=args.title_from_filename,
            title_fallback=args.title_fallback
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
        traceback.print_exception(e)
        print("Exit due to error.")
        sys.exit(1)


if __name__ == '__main__':
    main()
