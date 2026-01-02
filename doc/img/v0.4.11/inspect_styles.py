import xml.etree.ElementTree as ET

NAMESPACES = {
    'style': 'urn:oasis:names:tc:opendocument:xmlns:style:1.0',
    'fo': 'urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0',
    'draw': 'urn:oasis:names:tc:opendocument:xmlns:drawing:1.0',
    'svg': 'urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0',
}
for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)

tree = ET.parse('content.xml')
root = tree.getroot()

print("Searching for styles 'fr1' and 'gr2'...")

for style in root.findall(".//{urn:oasis:names:tc:opendocument:xmlns:style:1.0}style"):
    name = style.get(f"{{{NAMESPACES['style']}}}name")
    if name in ['fr1', 'gr2', 'Frame_20_contents']:
        print(f"\nStyle: {name}")
        for child in style:
            print(f"  Prop: {child.tag}")
            for k, v in child.attrib.items():
                print(f"    {k}: {v}")
