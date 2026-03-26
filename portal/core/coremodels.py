# portal/platforms/arkhon/models.py
from datetime import datetime

from portal.core.database import db  # shared db instance


class Customer(db.Model):
    __tablename__ = 'arkhon_customers'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    tc_no = db.Column(db.String(11))
    address = db.Column(db.Text)
    city = db.Column(db.String(50))
    district = db.Column(db.String(50))

class Order(db.Model):
    __tablename__ = 'arkhon_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('arkhon_customers.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Numeric(12,2))
    status = db.Column(db.String(20), default='draft')
    payment_plan = db.Column(db.Text)  # store JSON
    offer_number = db.Column(db.String(20))

class OrderItem(db.Model):
    __tablename__ = 'arkhon_order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('arkhon_orders.id'))
    pozno = db.Column(db.Integer)
    product_code = db.Column(db.String(50))
    product_name = db.Column(db.String(200))
    quantity = db.Column(db.Integer)
    unit = db.Column(db.String(10))
    width = db.Column(db.Integer)  # mm
    depth = db.Column(db.Integer)
    height = db.Column(db.Integer)
    config = db.Column(db.Text)    # konfigurasyon
    config_xml = db.Column(db.Text)
    details = db.Column(db.Text)