from pathlib import Path
import re
from lxml import html

def test_css_and_js_present():
    data = Path('templates/index.html').read_text()
    assert re.search(r'\.main-content-body\s*{[^}]*overflow-x:\s*hidden', data)
    assert re.search(r'\.table-scroll-wrapper\s*{[^}]*overflow-x:\s*auto', data)
    assert re.search(r"dom:\s*'<\"table-controls-top\"lf>rt<\"table-controls-bottom\"ip>'", data)
    assert "table.wrap('<div class=\"table-scroll-wrapper\"></div>');" in data
    assert re.search(r'\.table-controls-top,\n\.table-controls-bottom\s*{[^}]*position:\s*sticky', data)

def test_controls_not_in_scroll_area():
    snippet = '''
    <div class="dataTables_wrapper">
      <div class="table-controls-top"></div>
      <div class="table-scroll-wrapper"><table></table></div>
      <div class="table-controls-bottom"></div>
    </div>
    '''
    doc = html.fromstring(snippet)
    scroll = doc.xpath('//*[@class="table-scroll-wrapper"]')[0]
    top = doc.xpath('//*[@class="table-controls-top"]')[0]
    bottom = doc.xpath('//*[@class="table-controls-bottom"]')[0]
    assert top not in scroll.iterdescendants()
    assert bottom not in scroll.iterdescendants()

