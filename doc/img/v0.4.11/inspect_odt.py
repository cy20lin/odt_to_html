import re
import sys

try:
    with open('content.xml', 'r', encoding='utf-16') as f:
        content = f.read()
except:
    with open('content.xml', 'r', encoding='utf-8') as f:
        content = f.read()

# Find style gr5
pattern = r'(<style:style[^>]*style:name="gr5".*?</style:style>)'
match = re.search(pattern, content, re.DOTALL)

if match:
    style_xml = match.group(1)
    print("Style XML found:")
    print(style_xml)
    
    # Extract graphic properties
    props_match = re.search(r'<style:graphic-properties(.*?)/?>', style_xml, re.DOTALL)
    if props_match:
        print("\nGraphic Properties Attributes:")
        # Split attributes for readability
        attrs = re.findall(r'(\S+?)="(.*?)"', props_match.group(1))
        for key, value in attrs:
            print(f"  {key} = {value}")
    else:
        print("\nNo graphic properties found.")
else:
    print("Style 'gr5' not found")
