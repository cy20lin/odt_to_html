"""
Sample ODT Generator

Creates a sample ODT file with various features for testing the ODT to HTML converter.
ODT files are ZIP archives containing XML content following the ODF specification.
"""

import base64
import io
import zipfile
from pathlib import Path


def create_sample_image_png() -> bytes:
    """Create a simple 100x100 red square PNG image."""
    # This is a minimal valid PNG: 100x100 solid red square
    # Created using minimal PNG structure
    import struct
    import zlib
    
    width, height = 100, 100
    
    def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        chunk_len = struct.pack('>I', len(data))
        chunk_crc = struct.pack('>I', zlib.crc32(chunk_type + data) & 0xffffffff)
        return chunk_len + chunk_type + data + chunk_crc
    
    # PNG signature
    signature = b'\x89PNG\r\n\x1a\n'
    
    # IHDR chunk
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    ihdr = png_chunk(b'IHDR', ihdr_data)
    
    # IDAT chunk (image data)
    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'  # Filter type: None
        for x in range(width):
            raw_data += b'\xff\x00\x00'  # Red pixel (RGB)
    
    compressed = zlib.compress(raw_data, 9)
    idat = png_chunk(b'IDAT', compressed)
    
    # IEND chunk
    iend = png_chunk(b'IEND', b'')
    
    return signature + ihdr + idat + iend


def create_sample_odt(output_path: str) -> None:
    """Create a sample ODT file with various features for testing."""
    
    # Create a simple test image
    test_image = create_sample_image_png()
    
    # manifest.xml - lists all files in the package
    manifest_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
    <manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/>
    <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
    <manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>
    <manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>
    <manifest:file-entry manifest:full-path="Pictures/test_image.png" manifest:media-type="image/png"/>
</manifest:manifest>'''

    # meta.xml - document metadata
    meta_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
                      xmlns:dc="http://purl.org/dc/elements/1.1/"
                      xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
                      office:version="1.2">
    <office:meta>
        <dc:title>Sample ODT Document for Testing</dc:title>
        <dc:creator>ODT to HTML Converter Test Suite</dc:creator>
        <meta:creation-date>2024-01-01T00:00:00</meta:creation-date>
    </office:meta>
</office:document-meta>'''

    # styles.xml - document styles
    styles_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
                        xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
                        xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
                        xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
                        xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
                        office:version="1.2">
    <office:font-face-decls>
        <style:font-face style:name="Liberation Serif" svg:font-family="'Liberation Serif'" style:font-family-generic="roman"/>
        <style:font-face style:name="Liberation Sans" svg:font-family="'Liberation Sans'" style:font-family-generic="swiss"/>
        <style:font-face style:name="Liberation Mono" svg:font-family="'Liberation Mono'" style:font-family-generic="modern"/>
    </office:font-face-decls>
    <office:styles>
        <style:style style:name="Standard" style:family="paragraph">
            <style:paragraph-properties fo:margin-top="0cm" fo:margin-bottom="0.5cm"/>
            <style:text-properties style:font-name="Liberation Serif" fo:font-size="12pt"/>
        </style:style>
        <style:style style:name="Heading_1" style:family="paragraph">
            <style:paragraph-properties fo:margin-top="0.5cm" fo:margin-bottom="0.25cm"/>
            <style:text-properties style:font-name="Liberation Sans" fo:font-size="18pt" fo:font-weight="bold"/>
        </style:style>
        <style:style style:name="Heading_2" style:family="paragraph">
            <style:paragraph-properties fo:margin-top="0.4cm" fo:margin-bottom="0.2cm"/>
            <style:text-properties style:font-name="Liberation Sans" fo:font-size="14pt" fo:font-weight="bold"/>
        </style:style>
        <style:style style:name="Bold" style:family="text">
            <style:text-properties fo:font-weight="bold"/>
        </style:style>
        <style:style style:name="Italic" style:family="text">
            <style:text-properties fo:font-style="italic"/>
        </style:style>
        <style:style style:name="Underline" style:family="text">
            <style:text-properties style:text-underline-style="solid"/>
        </style:style>
        <style:style style:name="Caption" style:family="paragraph">
            <style:paragraph-properties fo:text-align="center"/>
            <style:text-properties fo:font-style="italic" fo:font-size="10pt"/>
        </style:style>
    </office:styles>
</office:document-styles>'''

    # content.xml - main document content with all test features
    content_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
                         xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
                         xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
                         xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
                         xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
                         xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
                         xmlns:xlink="http://www.w3.org/1999/xlink"
                         xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
                         office:version="1.2">
    <office:automatic-styles>
        <style:style style:name="P1" style:family="paragraph" style:parent-style-name="Standard">
            <style:paragraph-properties fo:text-align="center"/>
        </style:style>
        <style:style style:name="T1" style:family="text">
            <style:text-properties fo:font-weight="bold" fo:color="#ff0000"/>
        </style:style>
        <style:style style:name="T2" style:family="text">
            <style:text-properties fo:font-style="italic" fo:color="#0000ff"/>
        </style:style>
        <style:style style:name="fr1" style:family="graphic">
            <style:graphic-properties draw:fill-color="#cccccc" svg:stroke-color="#333333"/>
        </style:style>
        <text:list-style style:name="L1">
            <text:list-level-style-bullet text:level="1" text:bullet-char="•"/>
            <text:list-level-style-bullet text:level="2" text:bullet-char="◦"/>
        </text:list-style>
        <text:list-style style:name="L2">
            <text:list-level-style-number text:level="1" style:num-format="1"/>
            <text:list-level-style-number text:level="2" style:num-format="a"/>
        </text:list-style>
    </office:automatic-styles>
    <office:body>
        <office:text>
            <!-- Heading 1 -->
            <text:h text:style-name="Heading_1" text:outline-level="1">Sample Document for Testing</text:h>
            
            <!-- Regular paragraph -->
            <text:p text:style-name="Standard">This is a sample ODT document created for testing the ODT to HTML converter. It contains various features to verify proper conversion.</text:p>
            
            <!-- Heading 2 -->
            <text:h text:style-name="Heading_2" text:outline-level="2">Text Formatting</text:h>
            
            <!-- Paragraph with inline formatting -->
            <text:p text:style-name="Standard">This paragraph contains <text:span text:style-name="T1">bold red text</text:span> and <text:span text:style-name="T2">italic blue text</text:span>. It also has a<text:note text:id="ftn1" text:note-class="footnote"><text:note-citation>1</text:note-citation><text:note-body><text:p>This is the first footnote with some explanation text.</text:p></text:note-body></text:note> footnote reference.</text:p>
            
            <!-- Another paragraph with more footnotes -->
            <text:p text:style-name="Standard">Here is more text with another footnote<text:note text:id="ftn2" text:note-class="footnote"><text:note-citation>2</text:note-citation><text:note-body><text:p>This is the second footnote demonstrating multiple footnotes work correctly.</text:p></text:note-body></text:note> to demonstrate the feature properly.</text:p>
            
            <!-- Heading 2 -->
            <text:h text:style-name="Heading_2" text:outline-level="2">Lists</text:h>
            
            <!-- Unordered list -->
            <text:p text:style-name="Standard">Unordered list:</text:p>
            <text:list text:style-name="L1">
                <text:list-item>
                    <text:p>First bullet item</text:p>
                </text:list-item>
                <text:list-item>
                    <text:p>Second bullet item</text:p>
                    <text:list>
                        <text:list-item>
                            <text:p>Nested item one</text:p>
                        </text:list-item>
                        <text:list-item>
                            <text:p>Nested item two</text:p>
                        </text:list-item>
                    </text:list>
                </text:list-item>
                <text:list-item>
                    <text:p>Third bullet item</text:p>
                </text:list-item>
            </text:list>
            
            <!-- Ordered list -->
            <text:p text:style-name="Standard">Ordered list:</text:p>
            <text:list text:style-name="L2">
                <text:list-item>
                    <text:p>First numbered item</text:p>
                </text:list-item>
                <text:list-item>
                    <text:p>Second numbered item</text:p>
                </text:list-item>
                <text:list-item>
                    <text:p>Third numbered item</text:p>
                </text:list-item>
            </text:list>
            
            <!-- Heading 2 -->
            <text:h text:style-name="Heading_2" text:outline-level="2">Tables</text:h>
            
            <!-- Simple table -->
            <table:table table:name="Table1">
                <table:table-column table:number-columns-repeated="3"/>
                <table:table-row>
                    <table:table-cell>
                        <text:p>Header 1</text:p>
                    </table:table-cell>
                    <table:table-cell>
                        <text:p>Header 2</text:p>
                    </table:table-cell>
                    <table:table-cell>
                        <text:p>Header 3</text:p>
                    </table:table-cell>
                </table:table-row>
                <table:table-row>
                    <table:table-cell>
                        <text:p>Cell A1</text:p>
                    </table:table-cell>
                    <table:table-cell>
                        <text:p>Cell B1</text:p>
                    </table:table-cell>
                    <table:table-cell>
                        <text:p>Cell C1</text:p>
                    </table:table-cell>
                </table:table-row>
                <table:table-row>
                    <table:table-cell table:number-columns-spanned="2">
                        <text:p>Merged cells A2-B2</text:p>
                    </table:table-cell>
                    <table:covered-table-cell/>
                    <table:table-cell>
                        <text:p>Cell C2</text:p>
                    </table:table-cell>
                </table:table-row>
            </table:table>
            
            <!-- Heading 2 -->
            <text:h text:style-name="Heading_2" text:outline-level="2">Images and Figures</text:h>
            
            <!-- Image with caption -->
            <text:p text:style-name="Standard">Below is a test image:</text:p>
            <text:p text:style-name="P1">
                <draw:frame draw:name="TestImage" svg:width="2.5cm" svg:height="2.5cm">
                    <draw:image xlink:href="Pictures/test_image.png" xlink:type="simple" xlink:show="embed" xlink:actuate="onLoad"/>
                </draw:frame>
            </text:p>
            <text:p text:style-name="Caption">Figure <text:sequence text:name="Figure">1</text:sequence>: A red test square image</text:p>
            
            <!-- Heading 2 -->
            <text:h text:style-name="Heading_2" text:outline-level="2">Drawing Objects</text:h>
            
            <!-- Simple shape -->
            <text:p text:style-name="Standard">Below is a drawing object:</text:p>
            <text:p text:style-name="P1">
                <draw:frame draw:name="Shape1" svg:width="3cm" svg:height="2cm">
                    <draw:custom-shape draw:style-name="fr1">
                        <draw:enhanced-geometry draw:type="rectangle"/>
                        <text:p>Text in shape</text:p>
                    </draw:custom-shape>
                </draw:frame>
            </text:p>
            
            <!-- Page break -->
            <text:soft-page-break/>
            
            <!-- Heading 2 -->
            <text:h text:style-name="Heading_2" text:outline-level="2">After Page Break</text:h>
            
            <text:p text:style-name="Standard">This content appears after the page break.</text:p>
            
            <!-- Hyperlink -->
            <text:p text:style-name="Standard">Here is a <text:a xlink:href="https://example.com">hyperlink to example.com</text:a> for testing.</text:p>
            
            <!-- Text with special characters -->
            <text:p text:style-name="Standard">Special characters: &lt; &gt; &amp; "quotes" — em-dash • bullet</text:p>
            
            <!-- Multiple spaces and tabs -->
            <text:p text:style-name="Standard">Text with<text:s text:c="5"/>multiple spaces and<text:tab/>a tab character.</text:p>
            
            <!-- Line break -->
            <text:p text:style-name="Standard">First line<text:line-break/>Second line after line break</text:p>
            
        </office:text>
    </office:body>
</office:document-content>'''

    # Create the ODT file (ZIP archive)
    output = Path(output_path)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as odt:
        # mimetype must be first and uncompressed
        odt.writestr('mimetype', 'application/vnd.oasis.opendocument.text', compress_type=zipfile.ZIP_STORED)
        
        # Add XML files
        odt.writestr('META-INF/manifest.xml', manifest_xml)
        odt.writestr('meta.xml', meta_xml)
        odt.writestr('styles.xml', styles_xml)
        odt.writestr('content.xml', content_xml)
        
        # Add test image
        odt.writestr('Pictures/test_image.png', test_image)
    
    print(f"Created sample ODT: {output}")


if __name__ == '__main__':
    import sys
    output = sys.argv[1] if len(sys.argv) > 1 else 'sample_test.odt'
    create_sample_odt(output)
