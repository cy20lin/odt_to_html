"""Analyze a.odt to understand structure."""
import zipfile
import re

z = zipfile.ZipFile('a.odt')
content = z.read('content.xml').decode('utf-8')

with open('analysis_output.txt', 'w', encoding='utf-8') as f:
    # 1. Inspect Strikethrough Context
    f.write("=== STRIKETHROUGH CONTEXT ===\n")
    # Find text that has strikethrough style
    # Looking for <text:span text:style-name="... matches
    # First find styles with line-through
    strike_styles = []
    style_matches = re.findall(r'<style:style style:name="([^"]+)"[^>]*>.*?text-line-through[^>]*>', content, re.DOTALL)
    for s in style_matches:
        strike_styles.append(s)
    
    # Also check styles.xml
    styles_content = z.read('styles.xml').decode('utf-8')
    style_matches_2 = re.findall(r'<style:style style:name="([^"]+)"[^>]*>.*?text-line-through[^>]*>', styles_content, re.DOTALL)
    for s in style_matches_2:
        strike_styles.append(s)
        
    f.write(f"Strikethrough styles found: {strike_styles}\n")
    
    if strike_styles:
        # Check usage in content
        for style in strike_styles:
            # Find usages
            # Simple regex to find the span and immediate context
            pattern = re.compile(r'(.{0,100}<text:span text:style-name="' + re.escape(style) + r'">.*?</text:span>.{0,100})', re.DOTALL)
            matches = pattern.findall(content)
            for m in matches:
                f.write(f"Usage of {style}:\n{m}\n---\n")

    # 2. Inspect Frame Coordinates
    f.write("\n=== FRAME COORDINATES ===\n")
    # Look for frames, especially "Frame4" or "Shape 3" from previous analysis
    frames = re.findall(r'<draw:frame [^>]*>', content)
    for frame in frames:
        if '選項設定視窗' in content: # If this file has the issue, print all frames to find the relevant one
             f.write(frame + "\n")

    # Also look at custom-shapes to see if they have transforms or positions
    shapes = re.findall(r'<draw:custom-shape [^>]*>', content)
    for shape in shapes[:10]:
         f.write(shape + "\n")

    # 3. Inspect Table Borders
    f.write("\n=== TABLE BORDERS ===\n")
    # Look for table styles in automatic-styles
    table_styles = re.findall(r'<style:style style:name="[^"]+" style:family="table-cell">.*?<style:table-cell-properties[^>]*>.*?</style:style>', content, re.DOTALL)
    for ts in table_styles:
        if 'border' in ts:
            f.write(ts + "\n")
            
    # Also Check styles.xml for table-cell styles
    table_styles_2 = re.findall(r'<style:style style:name="[^"]+" style:family="table-cell">.*?<style:table-cell-properties[^>]*>.*?</style:style>', styles_content, re.DOTALL)
    for ts in table_styles_2:
        if 'border' in ts:
            f.write("In styles.xml: " + ts + "\n")

print("Results written to analysis_output.txt")

