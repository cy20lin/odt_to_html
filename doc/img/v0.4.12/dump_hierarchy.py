import xml.etree.ElementTree as ET

NAMESPACES = {
    'draw': 'urn:oasis:names:tc:opendocument:xmlns:drawing:1.0',
    'svg': 'urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0',
    'style': 'urn:oasis:names:tc:opendocument:xmlns:style:1.0',
    'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
}
for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)

tree = ET.parse('content.xml')
root = tree.getroot()

def dump_node(node, level=0):
    indent = "  " * level
    tag = node.tag.split('}')[-1]
    
    # Check if interesting
    if tag in ['frame', 'custom-shape', 'p', 'text-box']:
        name = node.get(f"{{{NAMESPACES['draw']}}}name", "")
        style = node.get(f"{{{NAMESPACES['draw']}}}style-name", "")
        x = node.get(f"{{{NAMESPACES['svg']}}}x", "")
        y = node.get(f"{{{NAMESPACES['svg']}}}y", "")
        anchor = node.get(f"{{{NAMESPACES['draw']}}}anchor-type", "")
        
        info = f"{tag}"
        if name: info += f" name='{name}'"
        if style: info += f" style='{style}'"
        if x: info += f" x='{x}'"
        if y: info += f" y='{y}'"
        if anchor: info += f" anchor='{anchor}'"
        
        text_content = ""
        if tag == 'p':
            text_content = "".join(node.itertext()).strip()[:30]
            if text_content: info += f" text='{text_content}'"
            
        print(f"{indent}{info}")
        
    for child in node:
        dump_node(child, level + 1)

print("Dumping hierarchy...")
dump_node(root)
