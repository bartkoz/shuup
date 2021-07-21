import json
from datetime import datetime

import requests
from shuup.core.models import Shop


def perform_request(payload):
    url = "https://api.baselinker.com/connector.php"
    files = []
    headers = {}
    response = requests.request("POST", url, headers=headers, data=payload, files=files)
    return response.json()


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
            elif data['products'][product_id]['quantity'] > count:
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
            "price_brutto": line.taxful_price.amount.value,
            "tax_rate": line.product.tax_class.name,
            "quantity": line.quantity,
            "weight": line.product.height
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
            parameters = {**parameters, **{"delivery_method": basket.shipping_method.carrier.name,
                                           "delivery_fullname": basket.shipping_address.name,
                                           "delivery_address": f'{basket.shipping_address.street} '
                                                               f'{basket.shipping_address.street2} '
                                                               f'{basket.shipping_address.street3}',
                                           "delivery_city": basket.shipping_address.city,
                                           "delivery_postcode": basket.shipping_address.postal_code,
                                           "delivery_country_code": basket.shipping_address.country,
                                           "delivery_point_id": "",
                                           "delivery_point_name": "",
                                           "delivery_point_address": "",
                                           "delivery_point_postcode": "",
                                           "delivery_point_city": "",
                                           }}
        payload['parameters'] = json.dumps(parameters)
        perform_request(payload)
