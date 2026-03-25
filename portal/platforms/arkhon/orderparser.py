# portal/platforms/arkhon/order_parser.py
from bs4 import BeautifulSoup


def parse_order_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    products = []

    # Each product row is a <tr> that contains hidden inputs with the same 'pozno' value
    # We'll iterate over all rows that have a hidden input with name="pozno"
    rows = soup.find_all('tr', recursive=True)
    for row in rows:
        pozno_input = row.find('input', {'name': 'pozno'})
        if not pozno_input:
            continue
        pozno = pozno_input.get('value')
        # Now extract other fields from this row
        product = {'pozno': pozno}
        for field in ['urk', 'ura', 'adet', 'brm', 'byt_x', 'byt_y', 'byt_z',
                      'ozk', 'oza', 'rnk', 'rna', 'govdernk', 'govderna',
                      'konfigurasyon', 'konfigurasyonXML', 'nitelikdetay']:
            inp = row.find('input', {'name': field})
            if inp:
                product[field] = inp.get('value')
        # Also get the product name from the <td> that contains it (ura is the code, but we need the name)
        # Actually 'ura' is the product name (e.g., "Alt Dolap 45 cm")
        # And we may want the description from the <td> if needed.
        products.append(product)
    return products