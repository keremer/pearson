# portal/platforms/arkhon/routes.py
from flask import Blueprint, request, render_template, send_file
from crminaec.core.models import db, Order, Customer, OrderItem
from crminaec.platforms.arkhon.orderparser import parse_order_html
from crminaec.core.reporting import multi_exporter
import io

arkhon_bp = Blueprint('arkhon', __name__, url_prefix='/arkhon',
                      template_folder='templates')

@arkhon_bp.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        # Get uploaded files
        excel_file = request.files.get('excel')
        html_file = request.files.get('order_html')

        # 1. Parse customer info from Excel (simplified – for demo)
        # 2. Create Customer and Order records
        # 3. Parse order HTML and create OrderItem records
        # 4. Commit

        # For now, just return success
        return "Order imported. ID: ..."
    return render_template('arkhon/upload.html')