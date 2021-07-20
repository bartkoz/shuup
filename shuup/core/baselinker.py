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

    def add_order(self, **kwargs):
        # TODO: hardcoded order status id
        payload = {'token': self.token,
                   'method': 'addOrder'}
        parameters = {
            "order_status_id": "53894",
            "date_add": "1495963282",
            "user_comments": "User comment",
            "admin_comments": "Seller test comments",
            "phone": "693123123",
            "email": "test@test.com",
            "user_login": "nick1",
            "currency": "GBP",
            "payment_method": "PayPal",
            "payment_method_cod": "0",
            "paid": "1",
            "delivery_method": "Expedited shipping",
            "delivery_price": "10",
            "delivery_fullname": "John Doe",
            "delivery_company": "Company",
            "delivery_address": "Long Str 12",
            "delivery_city": "London",
            "delivery_postcode": "E2 8HQ",
            "delivery_country_code": "GB",
            "delivery_point_id": "",
            "delivery_point_name": "",
            "delivery_point_address": "",
            "delivery_point_postcode": "",
            "delivery_point_city": "",
            "invoice_fullname": "John Doe",
            "invoice_company": "Company",
            "invoice_nip": "GB8943245",
            "invoice_address": "Long Str 12",
            "invoice_city": "London",
            "invoice_postcode": "E2 8HQ",
            "invoice_country_code": "GB",
            "want_invoice": "0",
            "extra_field_1": "field test 1",
            "extra_field_2": "",
            "products": [
                {
                    "storage": "db",
                    "storage_id": 0,
                    "product_id": "5434",
                    "variant_id": 52124,
                    "name": "Harry Potter and the Chamber of Secrets",
                    "sku": "LU4235",
                    "ean": "1597368451236",
                    "price_brutto": 20.00,
                    "tax_rate": 23,
                    "quantity": 2,
                    "weight": 1
                }
            ]
        }
        payload['parameters'] = parameters
        perform_request(payload)
