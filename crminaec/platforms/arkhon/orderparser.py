"""
Kelebek Furniture HTML Order Parser
Integrated with crminaec Data-First Architecture
"""
import logging
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

# Set up a logger so we can track parsing issues without printing to stdout
logger = logging.getLogger(__name__)

class KelebekOrderParser:
    """Parses Kelebek HTML order exports into structured data."""
    
    # Define expected fields at the class level for easy updates if Kelebek changes their HTML
    EXPECTED_FIELDS = [
        'urk', 'ura', 'adet', 'brm', 'byt_x', 'byt_y', 'byt_z',
        'ozk', 'oza', 'rnk', 'rna', 'govdernk', 'govderna',
        'konfigurasyon', 'konfigurasyonXML', 'nitelikdetay'
    ]

    @classmethod
    def parse_html(cls, html_content: str) -> Dict[str, Any]:
        """
        Extracts product rows and hidden input configurations from the Kelebek HTML table.
        
        Args:
            html_content (str): The raw HTML string uploaded by the user.
            
        Returns:
            Dict: A dictionary containing 'items' (list of products) and 'customer' (dict of details).
        """
        if not html_content:
            logger.warning("Empty HTML content provided to parser.")
            return {'items': [], 'customer': {}}

        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            products: List[Dict[str, Any]] = []
            
            # --- 1. EXTRACT CUSTOMER INFO (Best Effort) ---
            customer = {
                'first_name': '', 'last_name': '', 'email': '', 'phone': '', 'address': ''
            }
            
            # Search for common Kelebek/ProSAP hidden inputs or IDs related to the customer
            search_map = {
                'first_name': ['MusteriAdi', 'Ad', 'Müşteri Adı'],
                'last_name': ['MusteriSoyadi', 'Soyad', 'Müşteri Soyadı'],
                'email': ['MusteriEmail', 'EPosta', 'Email', 'E-Posta'],
                'phone': ['MusteriTelefon', 'CepTel', 'Telefon', 'Cep Telefonu'],
                'address': ['FaturaAdresi', 'Adres', 'Teslimat Adresi']
            }
            
            for field, keys in search_map.items():
                for key in keys:
                    # Try input name or id
                    inp = soup.find('input', {'name': key}) or soup.find('input', {'id': key})
                    if inp and inp.get('value'):
                        value = inp.get('value')
                        if isinstance(value, str):
                            customer[field] = value.strip()
                            break

            # --- 2. EXTRACT PRODUCTS ---
            rows = soup.find_all('tr')
            
            for row in rows:
                # The unique identifier for an order row in Kelebek's system is 'pozno'
                pozno_input = row.find('input', {'name': 'pozno'})
                if not pozno_input:
                    continue
                    
                pozno_val = pozno_input.get('value')
                if not pozno_val:
                    continue

                # Initialize the product dictionary
                product: Dict[str, Any] = {'pozno': pozno_val}
                
                # Extract all expected configuration fields safely
                for field in cls.EXPECTED_FIELDS:
                    inp = row.find('input', {'name': field})
                    # If the input exists, get its value (default to empty string if missing)
                    # If the input doesn't exist at all in the row, store it as None
                    product[field] = inp.get('value', '') if inp else None
                    
                products.append(product)

            logger.info(f"Successfully parsed {len(products)} products from Kelebek HTML.")
            return {'items': products, 'customer': customer}

        except Exception as e:
            logger.error(f"Failed to parse Kelebek order HTML: {e}")
            # Return empty structure to prevent 500 crashes
            return {'items': [], 'customer': {}}