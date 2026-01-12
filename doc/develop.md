# Commands for ODT to HTML test and debug

## Convert ODT to HTML

```bash
# Use the developed odt -> html tool to convert odt to html
python .\odt_to_html.py .\sample_test_drawing.odt sample_test_drawing.html
```

## Generate Screenshot for ODT or HTML

```bash
# Generate Test images from odt,html -> png
python .\odf_to_png.py .\sample_test_drawing.odt sample_test_drawing.odt.png
python .\html_to_png.py .\sample_test_drawing.html sample_test_drawing.html.png
```

## Extract content.xml from ODT file

```bash
# in project root
python .\script\extract_odt_content.py sample_test_drawing.odt content.xml
```

## Analyze html

this script analyzes and prints html tree structure. Also the content embeded base64 images is ignored for reducing interference of extreme long but unhelpful long base64 string for html structure understanding.

```
# in project root
python .\script\analyze_html.py target_sample.html
```