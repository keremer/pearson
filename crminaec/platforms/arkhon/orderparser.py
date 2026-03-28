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
    def parse_html(cls, html_content: str) -> List[Dict[str, Any]]:
        """
        Extracts product rows and hidden input configurations from the Kelebek HTML table.
        
        Args:
            html_content (str): The raw HTML string uploaded by the user.
            
        Returns:
            List[Dict[str, Any]]: A list of parsed product dictionaries.
        """
        if not html_content:
            logger.warning("Empty HTML content provided to parser.")
            return []

        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            products: List[Dict[str, Any]] = []

            # Search through all table rows
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
            return products

        except Exception as e:
            logger.error(f"Failed to parse Kelebek order HTML: {e}")
            # Returning an empty list ensures the calling route doesn't crash with a 500 Error
            return []