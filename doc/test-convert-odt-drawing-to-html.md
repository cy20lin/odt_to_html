```bash
# Use the developed odt -> html tool to convert odt to html
python .\odt_to_html.py .\sample_test_drawing.odt sample_test_drawing.html
# Generate Test images from odt,html -> png
python .\odf_to_png.py .\sample_test_drawing.odt sample_test_drawing.odt.png
python .\html_to_png.py .\sample_test_drawing.html sample_test_drawing.html.png
```