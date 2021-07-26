import json
import logging
from decimal import Decimal
from urllib.parse import urlparse

import redis
import requests
from django.conf import settings

from shuup.core.models import Shop, Product
from shuup.simple_supplier.models import StockCount

logger = logging.getLogger(__name__)


def perform_request(payload):
    url = "https://api.baselinker.com/connector.php"
    files = []
    headers = {}
    response = requests.request("POST", url, headers=headers, data=payload, files=files)
    return response.json()


def create_redis_connection():
    return redis.StrictRedis(
        host=urlparse(getattr(settings, 'CELERY_BROKER_URL')).netloc.split(':')[0], port=6379, db=0
    )


class BaseLinkerConnector:

    def __init__(self, shop: Shop):
        self.token = shop.bl_token.token
        self.storage = shop.bl_token.storage

    def check_if_product_still_available(self, product_id: str, count: int = 1, variant_id: str = None):
        is_available = False
        payload = {'token': self.token,
                   'method': 'getProductsData',
                   'parameters': '''{
                   "storage_id": "%s",
                   "products": [%s]}''' % (self.storage, product_id)}
        data = requests.post(
            'https://api.baselinker.com/connector.php',
            data=payload).json()
        try:
            if variant_id:
                if data['products'][product_id][variant_id]['quantity'] >= count:
                    is_available = True
            elif data['products'][product_id]['quantity'] >= count:
                is_available = True
        except KeyError:
            is_available = False
        return is_available

    def update_product_quantity(self, product_id: str, count: str, variant_id: str = None):
        payload = {'token': self.token,
                   'method': 'updateProductsQuantity',
                   'parameters': '''{
                       "storage_id": "%s",
                       "products": [
                           [%s, %s, %s]]}''' % (self.storage, product_id, variant_id or 0, count)
                   }
        requests.post(
            'https://api.baselinker.com/connector.php',
            data=payload)

    def get_current_storage(self, product_id: str, variant_id: str = None):
        payload = {'token': self.token,
                   'method': 'getProductsData',
                   'parameters': '''{
                   "storage_id": "%s",
                   "products": [%s]}''' % (self.storage, product_id)}
        data = requests.post(
            'https://api.baselinker.com/connector.php',
            data=payload).json()
        if variant_id:
            quantity = data['products'][product_id][variant_id]['quantity']
        else:
            quantity = data['products'][product_id]['quantity']
        return quantity

    def _build_product(self, line):
        return {
            "storage": "db",
            "storage_id": 0,
            "product_id": line.product.baselinker_id,
            "variant_id": 0,
            "name": line.product.name,
            "sku": line.product.sku,
            "ean": "1597368451236",
            "price_brutto": str(round(line.taxful_price.amount.value, 2)),
            "tax_rate": line.product.tax_class.name,
            "quantity": line.quantity,
            "weight": str(round(line.product.net_weight, 2))
        }

    def add_order(self, basket):

        # TODO: hardcoded order status id
        payload = {'token': self.token,
                   'method': 'addOrder'}
        parameters = {
            "order_status_id": "53894",
            "date_add": basket.order_date.timestamp(),
            "user_comments": "todo user comment",
            "admin_comments": "",
            "phone": basket.orderer.phone,
            "email": basket.orderer.email,
            "user_login": basket.orderer.user.username,
            "currency": basket.currency,
            "payment_method": basket.payment_method.name,
            "payment_method_cod": "0",
            "paid": "1",
            "delivery_method": None,
            "delivery_price": 0,
            "invoice_fullname": f'{basket.orderer.first_name} {basket.orderer.last_name}',
            "invoice_company": "",
            "invoice_nip": "",
            "invoice_address": "",
            "invoice_city": "",
            "invoice_postcode": "",
            "invoice_country_code": "",
            "want_invoice": "0",
            "products": [self._build_product(line) for line in basket.get_lines()]
        }
        if basket.shipping_address:
            try:
                delivery_method = basket.shipping_method.carrier.name
            except AttributeError:
                delivery_method = None
            parameters = {**parameters, **{"delivery_method": delivery_method,
                                           "delivery_fullname": basket.shipping_address.name,
                                           "delivery_address": f'{basket.shipping_address.street} '
                                                               f'{basket.shipping_address.street2} '
                                                               f'{basket.shipping_address.street3}',
                                           "delivery_city": basket.shipping_address.city,
                                           "delivery_postcode": basket.shipping_address.postal_code,
                                           "delivery_country_code": basket.shipping_address.country.code,
                                           "delivery_point_id": "",
                                           "delivery_point_name": "",
                                           "delivery_point_address": "",
                                           "delivery_point_postcode": "",
                                           "delivery_point_city": "",
                                           }}
        payload['parameters'] = json.dumps(parameters)
        perform_request(payload)

    def update_stocks(self):
        payload = {'token': self.token,
                   'method': 'getProductsList'}
        parameters = {"storage_id": "bl_1"}
        payload['parameters'] = json.dumps(parameters)
        stock = perform_request(payload)
        for product in stock['products']:
            try:
                prod = Product.objects.get(sku=product['sku'])
                shop_prod = prod.shop_products.first()
                current_price = Decimal(product['price_brutto'])
                if current_price != shop_prod.default_price_value:
                    shop_prod.default_price_value = Decimal(product['price_brutto'])
                    shop_prod.save(update_fields=['default_price_value'])
                stock_obj, _ = StockCount.objects.get_or_create(product_id=prod.id,
                                                                supplier=shop_prod.suppliers.first())
                stock_count = Decimal(product["quantity"])
                if stock_count != stock_obj.physical_count:
                    stock_obj.logical_count = stock_count
                    stock_obj.physical_count = stock_count
                    stock_obj.stock_value_value = shop_prod.default_price_value * Decimal(product["quantity"])
                    stock_obj.save(update_fields=['logical_count', 'physical_count', 'stock_value_value'])
            except Exception as e:
                logger.error(e)
