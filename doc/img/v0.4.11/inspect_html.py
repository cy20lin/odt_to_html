from bs4 import BeautifulSoup
import sys

try:
    with open('sample_test_drawing.html', 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find the section "In Frame Drawing" or text
    # It might be in a h1/h2 or p
    found = soup.find(string="In Frame Drawing")
    if found:
        print("Found section header.")
        # Look for following elements
        parent = found.parent
        # Scan siblings or look for drawing-frame in the doc
        pass
    
    # Explicitly look for the frame structure
    print("\nScanning for drawing-frame:")
    frames = soup.find_all(class_="drawing-frame")
    for frame in frames:
        print(f"\nFrame: style='{frame.get('style')}'")
        # Check children styling
        children = frame.find_all(recursive=True)
        for child in children:
            style = child.get('style', '')
            if 'position: absolute' in style:
                print(f"  Absolute Child <{child.name}>: style='{style}' text='{child.get_text()[:50]}...'")
            elif child.name == 'p':
                 print(f"  Paragraph <{child.name}>: style='{style}' (Should be relative from CSS)")

except Exception as e:
    print(e)
