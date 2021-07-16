import requests
from shuup.core.models import Shop


def perform_request(payload):
    url = "https://api.baselinker.com/connector.php"
    files = []
    headers = {}
    response = requests.request("POST", url, headers=headers, data=payload, files=files)
    return response.json()


class BaseLinkerConnector:

    def __init__(self, shop: Shop, storage_id: int):
        self.token = shop.bl_token
        self.storage_id = storage_id

    def check_if_product_still_available(self, product_id: int, variant_id: int = None):
        is_available = False
        payload = {'token': self.token,
                   'method': 'getProductsData',
                   'parameters': '''{
                   "storage_id": "%s",
                   "products": [11768832]}''' % (self.storage_id,)}
        data = perform_request(payload)
        if variant_id:
            if data['products'][product_id][variant_id]['quantity'] > 0:
                is_available = True
        elif data['products'][product_id]['quantity'] > 0:
            is_available = True
        return is_available

    def update_product_quantity(self, product_id: int, count: int, variant_id: int = None):
        parameters = '''{
        "storage_id": "bl_1", 
        "products":''' + str([product_id, variant_id or 0, count]) + '}'
        payload = {'token': self.token,
                   'method': 'updateProductsQuantity',
                   'parameters': str(parameters)}
        perform_request(payload)

    def add_order(self, **kwargs):
        # TODO:
        payload = {'token': self.token,
                   'method': 'updateProductsQuantity'}
        parameters = {
            "order_status_id": "49601",
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
