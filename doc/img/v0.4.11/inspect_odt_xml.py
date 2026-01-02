import xml.etree.ElementTree as ET
import sys
import os

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

for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)

def pretty_print(elem, level=0):
    indent = "  " * level
    tag = elem.tag.split('}')[-1]
    attribs = " ".join([f'{k.split("}")[-1]}="{v}"' for k, v in elem.attrib.items()])
    text = elem.text.strip() if elem.text else ""
    print(f"{indent}<{tag} {attribs}>")
    if text:
        print(f"{indent}  {text}")
    for child in elem:
        pretty_print(child, level + 1)
    print(f"{indent}</{tag}>")

try:
    tree = ET.parse('content.xml')
    root = tree.getroot()
    
    # search for "In Frame Drawing"
    found = False
    for elem in root.iter():
        if elem.text and "In Frame Drawing" in elem.text:
            print("Found 'In Frame Drawing' in element:")
            # Find closest parent that matters (listing paragraphs around it)
            # Actually let's just print the parent of this text
            # But ElementTree doesn't store parent pointers easily.
            # So I will just iterate and look for the specific draw:frame that follows this text? 
            # Or maybe the text is IN a frame?
            pass
            
    # Better approach: Look for headings with that text, then look at the following elements.
    # Or just look for all draw:frame elements and print them.
    # The user implies there is a section "In Frame Drawing".
    
    print("\nScanning for frames...")
    frames = root.findall(f".//{{{NAMESPACES['draw']}}}frame")
    for i, frame in enumerate(frames):
        # Check if this frame is likely the one.
        # Maybe it has specific children mentioned: arrow, Sun, Text box with Bold Text
        has_arrow = False
        has_sun = False
        has_text_box = False
        
        # Check by name or content
        raw = ET.tostring(frame, encoding='unicode')
        if "arrow" in raw.lower() or "sun" in raw.lower() or "bold text" in raw.lower():
            print(f"Frame {i} Match:")
            pretty_print(frame)
            
except Exception as e:
    print(e)
