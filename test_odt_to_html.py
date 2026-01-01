"""
Test Suite for ODT to HTML Converter

Uses pytest to verify all conversion features work correctly.
Run with: pytest test_odt_to_html.py -v
"""

import os
import re
import tempfile
from pathlib import Path

import pytest

# Import the modules we're testing
from odt_to_html import ODTConverter
from create_sample_odt import create_sample_odt, create_sample_image_png


@pytest.fixture(scope="module")
def sample_odt_path(tmp_path_factory):
    """Create a sample ODT file for testing."""
    tmp_dir = tmp_path_factory.mktemp("odt_test")
    odt_path = tmp_dir / "sample_test.odt"
    create_sample_odt(str(odt_path))
    return odt_path


@pytest.fixture(scope="module")
def converted_html(sample_odt_path):
    """Convert the sample ODT to HTML and return the content."""
    # Default behavior should now be show_page_breaks=True
    converter = ODTConverter(str(sample_odt_path))
    return converter.convert()


@pytest.fixture(scope="module")
def converted_html_no_page_breaks(sample_odt_path):
    """Convert the sample ODT to HTML without page break markers."""
    converter = ODTConverter(str(sample_odt_path), show_page_breaks=False)
    return converter.convert()


class TestSampleODTGeneration:
    """Tests for the sample ODT file generator."""
    
    def test_sample_odt_created(self, sample_odt_path):
        """Verify the sample ODT file is created."""
        assert sample_odt_path.exists()
        assert sample_odt_path.stat().st_size > 0
    
    def test_sample_odt_is_valid_zip(self, sample_odt_path):
        """Verify the sample ODT is a valid ZIP archive."""
        import zipfile
        assert zipfile.is_zipfile(sample_odt_path)
    
    def test_sample_odt_contains_required_files(self, sample_odt_path):
        """Verify the sample ODT contains required ODF files."""
        import zipfile
        with zipfile.ZipFile(sample_odt_path, 'r') as odt:
            namelist = odt.namelist()
            assert 'mimetype' in namelist
            assert 'content.xml' in namelist
            assert 'styles.xml' in namelist
            assert 'META-INF/manifest.xml' in namelist
    
    def test_sample_image_generation(self):
        """Verify the PNG image generator creates valid PNG data."""
        png_data = create_sample_image_png()
        # PNG signature
        assert png_data[:8] == b'\x89PNG\r\n\x1a\n'
        # Should have reasonable size for a 100x100 RGB image
        assert len(png_data) > 100


class TestBasicConversion:
    """Tests for basic ODT to HTML conversion."""
    
    def test_conversion_produces_html(self, converted_html):
        """Verify conversion produces valid HTML structure."""
        assert '<!DOCTYPE html>' in converted_html
        assert '<html' in converted_html
        assert '</html>' in converted_html
        assert '<head>' in converted_html
        assert '</head>' in converted_html
        assert '<body>' in converted_html
        assert '</body>' in converted_html
    
    def test_html_has_charset(self, converted_html):
        """Verify HTML has proper charset declaration."""
        assert 'charset="UTF-8"' in converted_html or "charset='UTF-8'" in converted_html
    
    def test_html_has_viewport(self, converted_html):
        """Verify HTML has viewport meta tag for responsiveness."""
        assert 'viewport' in converted_html
    
    def test_html_no_external_fonts(self, converted_html):
        """Verify HTML doesn't load external fonts (offline requirement)."""
        assert 'fonts.googleapis.com' not in converted_html
        assert '@import url(' not in converted_html


class TestHeadings:
    """Tests for heading conversion."""
    
    def test_h1_heading(self, converted_html):
        """Verify H1 headings are converted."""
        assert '<h1' in converted_html
        assert '</h1>' in converted_html
        assert 'Sample Document for Testing' in converted_html
    
    def test_h2_headings(self, converted_html):
        """Verify H2 headings are converted."""
        assert '<h2' in converted_html
        assert '</h2>' in converted_html
        assert 'Text Formatting' in converted_html
        assert 'Lists' in converted_html
        assert 'Tables' in converted_html


class TestTextFormatting:
    """Tests for text formatting conversion."""
    
    def test_bold_text(self, converted_html):
        """Verify bold text is converted with font-weight."""
        # The sample has T1 style with bold
        assert 'font-weight' in converted_html or '<b>' in converted_html or '<strong>' in converted_html
    
    def test_italic_text(self, converted_html):
        """Verify italic text is converted."""
        assert 'font-style' in converted_html or '<i>' in converted_html or '<em>' in converted_html
    
    def test_colored_text(self, converted_html):
        """Verify colored text is converted."""
        # Red and blue text in sample
        assert '#ff0000' in converted_html.lower() or 'color: red' in converted_html.lower()
        assert '#0000ff' in converted_html.lower() or 'color: blue' in converted_html.lower()
    
    def test_spans_for_formatting(self, converted_html):
        """Verify span elements are used for inline formatting."""
        assert '<span' in converted_html
        assert '</span>' in converted_html

    def test_strikethrough_text(self, converted_html):
        """Verify strikethrough text is converted."""
        # Check for text-decoration: line-through style
        assert 'line-through' in converted_html
        assert 'strikethrough' in converted_html


class TestLists:
    """Tests for list conversion."""
    
    def test_unordered_list(self, converted_html):
        """Verify unordered lists are converted."""
        assert '<ul>' in converted_html
        assert '</ul>' in converted_html
    
    def test_ordered_list(self, converted_html):
        """Verify ordered lists are converted."""
        assert '<ol>' in converted_html
        assert '</ol>' in converted_html
    
    def test_list_items(self, converted_html):
        """Verify list items are converted."""
        assert '<li>' in converted_html
        assert '</li>' in converted_html
    
    def test_list_content(self, converted_html):
        """Verify list item content is preserved."""
        assert 'First bullet item' in converted_html
        assert 'First numbered item' in converted_html
    
    def test_nested_lists(self, converted_html):
        """Verify nested lists are converted."""
        assert 'Nested item one' in converted_html
        assert 'Nested item two' in converted_html


class TestTables:
    """Tests for table conversion."""
    
    def test_table_element(self, converted_html):
        """Verify table elements are converted."""
        assert '<table' in converted_html
        assert '</table>' in converted_html
    
    def test_table_rows(self, converted_html):
        """Verify table rows are converted."""
        assert '<tr>' in converted_html
        assert '</tr>' in converted_html
    
    def test_table_cells(self, converted_html):
        """Verify table cells are converted."""
        assert '<td' in converted_html
        assert '</td>' in converted_html
    
    def test_table_content(self, converted_html):
        """Verify table cell content is preserved."""
        assert 'Header 1' in converted_html
        assert 'Cell A1' in converted_html
    
    def test_merged_cells(self, converted_html):
        """Verify merged cells have colspan attribute."""
        assert 'colspan="2"' in converted_html
        assert 'Merged cells A2-B2' in converted_html


class TestImages:
    """Tests for image conversion."""
    
    def test_image_element(self, converted_html):
        """Verify image elements are converted."""
        assert '<img' in converted_html
    
    def test_image_embedded_base64(self, converted_html):
        """Verify images are embedded as base64 data URIs."""
        assert 'data:image/png;base64,' in converted_html
    
    def test_image_has_src(self, converted_html):
        """Verify images have src attribute."""
        assert 'src="data:' in converted_html


class TestDrawingObjects:
    """Tests for drawing object conversion."""
    
    def test_svg_generated(self, converted_html):
        """Verify drawing objects generate SVG elements."""
        assert '<svg' in converted_html
        assert '</svg>' in converted_html
    
    def test_drawing_has_dimensions(self, converted_html):
        """Verify SVG has width and height."""
        # Look for SVG with width/height attributes
        svg_match = re.search(r'<svg[^>]+width="[\d.]+"[^>]+height="[\d.]+"', converted_html)
        assert svg_match is not None
    
    def test_text_in_shape(self, converted_html):
        """Verify text inside shapes is preserved."""
        assert 'Text in shape' in converted_html


class TestFootnotes:
    """Tests for footnote conversion."""
    
    def test_footnote_references(self, converted_html):
        """Verify footnote references are converted."""
        assert 'footnote-ref' in converted_html or 'ref-ftn' in converted_html
    
    def test_footnote_section(self, converted_html):
        """Verify footnotes section is generated at end."""
        assert 'class="footnotes"' in converted_html or 'Footnotes' in converted_html
    
    def test_footnote_content(self, converted_html):
        """Verify footnote content is preserved."""
        assert 'first footnote' in converted_html
        assert 'second footnote' in converted_html
    
    def test_footnote_backlinks(self, converted_html):
        """Verify footnotes have back-reference links."""
        assert 'footnote-backref' in converted_html or '↩' in converted_html


class TestPageBreaks:
    """Tests for page break handling."""
    
    def test_page_break_visible_when_enabled(self, converted_html):
        """Verify page breaks are visible when option is enabled."""
        assert 'page-break' in converted_html
        assert 'Page Break' in converted_html
    
    def test_page_break_not_visible_when_disabled(self, converted_html_no_page_breaks):
        """Verify page breaks are not visible when option is disabled."""
        # Check for the specific page-break div with span, not heading text containing "Page Break"
        assert 'class="page-break"' not in converted_html_no_page_breaks
    
    def test_content_after_page_break(self, converted_html):
        """Verify content after page break is preserved."""
        assert 'After Page Break' in converted_html
        assert 'appears after the page break' in converted_html


class TestHyperlinks:
    """Tests for hyperlink conversion."""
    
    def test_hyperlink_element(self, converted_html):
        """Verify hyperlinks are converted."""
        assert '<a href=' in converted_html
    
    def test_hyperlink_url(self, converted_html):
        """Verify hyperlink URLs are preserved."""
        assert 'https://example.com' in converted_html
    
    def test_hyperlink_text(self, converted_html):
        """Verify hyperlink text is preserved."""
        assert 'hyperlink to example.com' in converted_html


class TestSpecialCharacters:
    """Tests for special character handling."""
    
    def test_angle_brackets_escaped(self, converted_html):
        """Verify angle brackets are properly escaped."""
        # The original contains &lt; and &gt;
        assert '&lt;' in converted_html
        assert '&gt;' in converted_html
    
    def test_ampersand_escaped(self, converted_html):
        """Verify ampersands are properly escaped."""
        assert '&amp;' in converted_html
    
    def test_em_dash(self, converted_html):
        """Verify em-dash is preserved."""
        assert '—' in converted_html or '&mdash;' in converted_html


class TestWhitespace:
    """Tests for whitespace handling."""
    
    def test_multiple_spaces(self, converted_html):
        """Verify multiple spaces are preserved."""
        assert '&nbsp;' in converted_html
    
    def test_tabs(self, converted_html):
        """Verify tabs are converted."""
        assert '&emsp;' in converted_html or 'tab' in converted_html.lower()
    
    def test_line_breaks(self, converted_html):
        """Verify line breaks are converted."""
        assert '<br>' in converted_html or '<br/>' in converted_html


class TestFigureCaptions:
    """Tests for figure captions and sequence numbers."""
    
    def test_figure_number(self, converted_html):
        """Verify figure numbers are preserved."""
        # The sample has "Figure 1"
        assert 'Figure' in converted_html
    
    def test_caption_text(self, converted_html):
        """Verify caption text is preserved."""
        assert 'red test square' in converted_html


class TestOutputFile:
    """Tests for file output functionality."""
    
    def test_write_html_file(self, sample_odt_path, tmp_path):
        """Verify HTML can be written to file."""
        html_path = tmp_path / "output.html"
        converter = ODTConverter(str(sample_odt_path))
        html_content = converter.convert()
        html_path.write_text(html_content, encoding='utf-8')
        
        assert html_path.exists()
        assert html_path.stat().st_size > 0
    
    def test_html_file_readable(self, sample_odt_path, tmp_path):
        """Verify output HTML file is valid UTF-8."""
        html_path = tmp_path / "output.html"
        converter = ODTConverter(str(sample_odt_path))
        html_content = converter.convert()
        html_path.write_text(html_content, encoding='utf-8')
        
        # Read back and verify
        content = html_path.read_text(encoding='utf-8')
        assert '<!DOCTYPE html>' in content


class TestErrorHandling:
    """Tests for error handling."""
    
    def test_nonexistent_file(self):
        """Verify proper error for non-existent file."""
        converter = ODTConverter('/nonexistent/path/file.odt')
        with pytest.raises(FileNotFoundError):
            converter.convert()
    
    def test_invalid_odt_file(self, tmp_path):
        """Verify proper error for invalid ODT file."""
        invalid_file = tmp_path / "invalid.odt"
        invalid_file.write_text("This is not a valid ODT file")
        
        converter = ODTConverter(str(invalid_file))
        with pytest.raises(ValueError):
            converter.convert()


class TestCLI:
    """Tests for command-line interface."""
    
    def test_cli_help(self):
        """Verify CLI help works."""
        import subprocess
        result = subprocess.run(
            ['python', 'odt_to_html.py', '--help'],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        assert result.returncode == 0
        assert 'input' in result.stdout
        assert 'output' in result.stdout
        assert '--no-page-breaks' in result.stdout
    
    def test_cli_conversion(self, sample_odt_path, tmp_path):
        """Verify CLI conversion works."""
        import subprocess
        html_path = tmp_path / "cli_output.html"
        
        result = subprocess.run(
            ['python', 'odt_to_html.py', str(sample_odt_path), str(html_path)],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        
        assert result.returncode == 0
        assert html_path.exists()
        assert 'Successfully converted' in result.stdout
    
    def test_cli_with_page_breaks(self, sample_odt_path, tmp_path):
        """Verify CLI --no-page-breaks option works."""
        import subprocess
        html_path = tmp_path / "cli_no_page_breaks.html"
        
        result = subprocess.run(
            ['python', 'odt_to_html.py', str(sample_odt_path), str(html_path), '--no-page-breaks'],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        
        assert result.returncode == 0
        content = html_path.read_text(encoding='utf-8')
        assert 'page-break' not in content


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
