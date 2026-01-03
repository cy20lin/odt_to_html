import re

def remove_base64_images(html_content):
    """
    Removes <img> tags where the src attribute contains 'data:image/'
    (indicating a base64 embed).

    Args:
        html_content (str): The input HTML string with potential embedded images.

    Returns:
        str: The HTML string with base64 <img> tags removed.
    """
    # This regex specifically targets <img> tags whose src attribute
    # begins with 'data:image/' (case-insensitive for 'src' and 'data:image')
    # and ends with an optional trailing slash and the closing '>'
    pattern = re.compile(r'<img\s+[^>]*?src=["\']data:image/[^>]*?>', re.IGNORECASE | re.DOTALL)
    
    # Replace all matches with an empty string
    cleaned_html = pattern.sub('data:image/...', html_content)
    
    return cleaned_html

# --- Example Usage ---
html_with_embeds = """
<!DOCTYPE html>
<html>
<body>
    <h1>Original HTML with Base64 Images</h1>
    <p>This image should be removed:</p>
    <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=" alt="Red Dot">
    
    <p>This regular image should be kept:</p>
    <img src="https://example.com/logo.png" alt="External Logo">

    <p>Another embedded image to remove:</p>
    <img class="icon" src='data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBAQFBAYEBQQGBgUHCQYHCAoKCgwhITECAgsQDhAoEBEQEhAVFRoUFhgSFwUWGhAKHCQdHSAcISAgHColJR8b/wgBBQQGBQYFBwYIBgYGHgoHCQsKCAoKChSEhITECAsQDgQoERAREBJAVFRoUFhgSFwUWGhEKHCPdHSAcISAgHColJR8b/wAARCAABAAEDAREAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAACF/8QAFQEBAAAAAAAAAAAAAAAAAAAAAAH/xAAWAQEBAQAAAAAAAAAAAAAAAAAAAgH/xAAXEQEAAwAAAAAAAAAAAAAAAAAAAgEx/9oADAMBAAIRAxEAPwAUtQn//Z' alt="Another embed">

    <p>Final paragraph.</p>
</body>
</html>
"""
import sys
print(sys.argv)

f = open(sys.argv[1], 'r', encoding='utf-8') 
source = f.read()
# cleaned_html_output = remove_base64_images(html_with_embeds)
result = remove_base64_images(source)

print("--- Cleaned HTML Output ---")
# print(cleaned_html_output)
# print(cleaned_html_output)
ff = open(sys.argv[2], 'w', encoding='utf-8')
ff.write(result)
print(result)