import pytest
import os
from odt_to_html import ODTConverter

TEST_ODT = "sample_test_drawing.odt"

@pytest.fixture
def converter():
    if not os.path.exists(TEST_ODT):
        pytest.skip(f"Test file {TEST_ODT} not found")
    return ODTConverter(TEST_ODT)

def test_round_rectangle_conversion(converter):
    """Verify Round Rectangle uses Arcs (A) and implicit Lines (L) correctly."""
    html = converter.convert()
    
    # Extract the SVG path for the round rectangle
    # We look for the path that contains the characteristic arc commands
    # Expected pattern involves "A 3600 3600" for corners
    
    assert "A 3600 3600" in html, "Round Rectangle should use elliptical arcs (A) for corners"
    assert "fill=\"#e0e0e0\"" in html, "Round Rectangle should have correct fill color"

def test_sun_shape_conversion(converter):
    """Verify Sun shape rendering, specifically the central circle size."""
    html = converter.convert()
    
    # The fix for Sun shape involved correcting the U command radius
    # The central circle should have radii 5400
    # Search for "A 5400 5400"
    
    assert "A 5400 5400" in html, "Sun shape central circle should have 5400 radius"
    
    # Also verify rays are present (implicit command repetition check)
    # Rays are drawn with Lines. We can check for a sequence of L commands or coordinates.
    # Just checking that the path is not truncated is hard without full parse, 
    # but we can check for presence of known ray coordinates or length.
    
    # Check for the presence of the Sun shape's unique path data start
    # "M 0 10800 L ..." or the U command part
    assert "U 10800 10800" not in html, "U command should be converted to SVG path commands"

def test_can_shape_conversion(converter):
    """Verify Can/Database shape for implicit command repetition."""
    html = converter.convert()
    
    # The Can shape uses implicit Curve (C) commands
    # "M 44 0 C 20 0 ... C 68 21600 ..."
    # The regression broke the second C.
    # We check if the generated path contains multiple C commands or expected coordinate strings.
    
    # Unique substring for Can shape path data?
    # It has "C 20 0 0 1227.27"
    assert "C 20 0 0 1227.27" in html, "Can shape should contain cubic bezier curves"
    
    # Check for the top/bottom ellipses which rely on implicit C
    # "C 68 5400 88 4172.73 88 2700" 
    assert "88 4172.73 88 2700" in html, "Can shape should contain full implicit curve data"

if __name__ == "__main__":
    # Allow running directly
    pytest.main([__file__])
