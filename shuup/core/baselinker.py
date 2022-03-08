import io
import json
import logging
import uuid
from decimal import Decimal
from urllib.parse import urlparse

import redis
import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.images import ImageFile

from shuup.core.models import Shop, Product, ShopProduct, ProductMedia, ProductMediaKind, Supplier, \
    ShopProductVisibility
from shuup.core.slugify import slugify
from shuup.simple_supplier.models import StockCount
from shuup.utils.filer import filer_image_from_upload, ensure_media_file
from project.celery import app

logger = logging.getLogger(__name__)


def create_redis_connection():
    return redis.StrictRedis(
        host=urlparse(getattr(settings, 'CELERY_BROKER_URL')).netloc.split(':')[0], port=6379, db=0
    )


@app.task(rate_limit='5/s')
def create_single_product(product, ids_to_add, supplier_id):
    connector = BaseLinkerConnector(Supplier.objects.get(pk=supplier_id))

    # if str(product['product_id']) in ids_to_add and str(product['category_id']) in allowed_categories:
    if str(product['product_id']) in ids_to_add:
        product_obj, created = Product.objects.update_or_create(tax_class_id=1,
                                                                sku=product['sku'],
                                                                sales_unit_id=1,
                                                                type_id=1,
                                                                defaults={
                                                                    'baselinker_id': product[
                                                                        'product_id'], })
        product_obj.set_current_language('pl')
        description = ''
        for desc in ['description',
                     'description_extra1',
                     'description_extra2',
                     'description_extra3',
                     'description_extra4']:
            if product[desc]:
                description += f"{product[desc]}\n"
        product_obj.name = product['name']
        product_obj.description = connector._strip_html_tags(description)
        product_obj.slug = slugify(product['name'])
        product_obj.save()
        if created:
            for iterator, product_image_url in enumerate(product['images']):
                connector._download_and_save_image(product_image_url, product_obj, iterator)
        if not product_obj.shop_products.exists():
            shop_product_obj = ShopProduct.objects.create(default_price_value=product['price_brutto'],
                                                          product_id=product_obj.pk,
                                                          shop_id=1)
            shop_product_obj.set_current_language('pl')
            shop_product_obj.name = product['name']
            shop_product_obj.slug = slugify(shop_product_obj.name)
            shop_product_obj.suppliers.add(connector.shop)
            shop_product_obj.save()


def perform_request(payload):
    url = "https://api.baselinker.com/connector.php"
    files = []
    headers = {}
    response = requests.request("POST", url, headers=headers, data=payload, files=files)
    return response.json()


class BaseLinkerConnector:

    def __init__(self, shop: Supplier):
        self.shop = shop
        self.token = shop.bl_token.token
        self.storage = shop.bl_token.storage
        self.inventory = shop.bl_token.inventory
        self.order_status_id = shop.bl_token.order_status_id

    def check_if_product_still_available(self, product_id: str, count: int = 1, variant_id: str = None):
        if self.shop.bl_token.new_api:
            return self.check_if_product_still_available_new(product_id=product_id, count=count, variant_id=variant_id)
        return self.check_if_product_still_available_old(product_id=product_id, count=count, variant_id=variant_id)

    def get_current_storage(self, product_id: str, variant_id: str = None):
        if self.shop.bl_token.new_api:
            return self.get_current_storage_new(product_id=product_id, variant_id=variant_id)
        return self.get_current_storage_old(product_id=product_id, variant_id=variant_id)

    def check_if_product_still_available_old(self, product_id: str, count: int = 1, variant_id: str = None):
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
        except (KeyError, TypeError):
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

    def get_current_storage_old(self, product_id: str, variant_id: str = None):
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

    def check_if_product_still_available_new(self, product_id: str, count: int = 1, variant_id: str = None):
        is_available = False
        payload = {'token': self.token,
                   'method': 'getInventoryProductsData',
                   'parameters': '''{
                   "inventory_id": "%s",
                   "products": [%s]}''' % (self.inventory, product_id)}
        data = requests.post(
            'https://api.baselinker.com/connector.php',
            data=payload).json()
        try:
            if variant_id:
                if list(data['products'][product_id][variant_id]['stock'].variants())[0] >= count:
                    is_available = True
            elif list(data['products'][product_id]['stock'].values())[0] >= count:
                is_available = True
        except (KeyError, TypeError):
            is_available = False
        return is_available

    def get_current_storage_new(self, product_id: str, variant_id: str = None):
        payload = {'token': self.token,
                   'method': 'getInventoryProductsData',
                   'parameters': '''{
                   "inventory_id": "%s",
                   "products": [%s]}''' % (self.inventory, product_id)}
        data = requests.post(
            'https://api.baselinker.com/connector.php',
            data=payload).json()
        if variant_id:
            quantity = list(data['products'][product_id][variant_id]['stock'].variants())[0]
        else:
            quantity = list(data['products'][product_id]['stock'].values())[0]
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
            "price_brutto": str(round(line.taxful_price.amount.value/line.quantity, 2)),
            "tax_rate": line.product.tax_class.name,
            "quantity": line.quantity,
            "weight": str(round(line.product.net_weight, 2))
        }

    def add_order(self, basket, comment):

        payload = {'token': self.token,
                   'method': 'addOrder'}
        parameters = {
            "order_status_id": self.order_status_id,
            "date_add": basket.order_date.timestamp(),
            "user_comments": comment if comment else '',
            "admin_comments": "",
            "phone": basket.shipping_address.phone,
            "email": basket.shipping_address.email,
            "user_login": basket.shipping_address.name,
            "currency": basket.currency,
            "payment_method": basket.payment_method.name,
            "payment_method_cod": "0",
            "paid": "1",
            "delivery_price": self.get_shipping_costs(basket),
            "want_invoice": "0",
            "extra_field_1": "Fishster",
            "products": [self._build_product(line) for line in basket.get_lines()]
        }
        if basket.shipping_address:
            try:
                delivery_method = basket.shipping_method.name
            except AttributeError:
                delivery_method = None
            parameters = {**parameters, **{"delivery_method": delivery_method,
                                           "delivery_fullname": basket.shipping_address.name,
                                           "delivery_address": f'{basket.shipping_address.street} '
                                                               f'{basket.shipping_address.street2} '
                                                               f'{basket.shipping_address.street3}',
                                           "delivery_city": basket.shipping_address.city,
                                           "delivery_postcode": basket.shipping_address.postal_code,
                                           "phone": basket.shipping_address.phone,
                                           "delivery_country_code": basket.shipping_address.country.code,
                                           "delivery_point_id": "",
                                           "delivery_point_name": "",
                                           "delivery_point_address": "",
                                           "delivery_point_postcode": "",
                                           "delivery_point_city": "",
                                           "invoice_fullname": basket.shipping_address.name,
                                           "invoice_company": "",
                                           "invoice_nip": "",
                                           "invoice_address": f'{basket.shipping_address.street} '
                                                              f'{basket.shipping_address.street2} '
                                                              f'{basket.shipping_address.street3}',
                                           "invoice_city": basket.shipping_address.city,
                                           "invoice_postcode": basket.shipping_address.postal_code,
                                           "invoice_country_code": basket.shipping_address.country.code,
                                           }}
        payload['parameters'] = json.dumps(parameters)
        perform_request(payload)

    def update_stocks(self):
        for _ in range(1, 1000):
            payload = {'token': self.token,
                       'method': 'getProductsList'}
            parameters = {f"storage_id": self.storage, "page": _}
            payload['parameters'] = json.dumps(parameters)
            stock = perform_request(payload)
            if not stock.get('products'):
                break
            bl_data = {str(x['product_id']): x for x in stock['products']}
            for entry in bl_data.values():
                try:
                    prod = Product.objects.get(sku=entry['sku'])
                    stock = prod.simple_supplier_stock_count.first()
                    if not stock:
                            stock = StockCount.objects.create(
                                product=prod, supplier=prod.shop_products.first().suppliers.first()
                            )
                    count = entry['quantity']
                    sp = prod.shop_products.first()
                    sp.default_price_value = entry['price_brutto']
                    if count <= 0:
                        sp.visibility = ShopProductVisibility.SEARCHABLE
                    else:
                        sp.visibility = ShopProductVisibility.ALWAYS_VISIBLE
                    sp.save()
                    stock.physical_count = count
                    stock.logical_count = count
                    stock.save()
                except Exception as e:
                    logger.debug(e)
                    continue

    def update_new_stocks(self):
        for _ in range(1, 1000):
            payload = {'token': self.token,
                       'method': 'getInventoryProductsList'}
            parameters = {f"inventory_id": self.inventory, "page": _}
            payload['parameters'] = json.dumps(parameters)
            stock = perform_request(payload)
            if not stock.get('products'):
                break
            bl_data = stock['products']
            for entry in bl_data.values():
                try:
                    prod = Product.objects.get(sku=entry['sku'])
                    stock = prod.simple_supplier_stock_count.first()
                    if not stock:
                        stock = StockCount.objects.create(
                            product=prod, supplier=prod.shop_products.first().suppliers.first()
                        )
                    try:
                        count = int(list(entry.get('stock').values())[0])
                    except Exception:
                        count = 0
                    sp = prod.shop_products.first()
                    sp.default_price_value = Decimal(list(entry['prices'].values())[0])
                    if count <= 0:
                        sp.visibility = ShopProductVisibility.SEARCHABLE
                    else:
                        sp.visibility = ShopProductVisibility.ALWAYS_VISIBLE
                    sp.save()
                    stock.physical_count = count
                    stock.logical_count = count
                    stock.save()
                except Exception as e:
                    logger.debug(e)
                    continue

        # for _ in range(1, 1000):
        #     payload = {'token': self.token,
        #                'method': 'getProductsList'}
        #     parameters = {f"storage_id": self.storage, "page": _}
        #     payload['parameters'] = json.dumps(parameters)
        #     stock = perform_request(payload)
        #     if not stock.get('products'):
        #         break
        #     products_list = [x['product_id'] for x in stock['products']]
        #     bl_data = {str(x['product_id']): x for x in stock['products']}
        #
        #     shop_products_id_map = {
        #         x['product__baselinker_id']: x['pk'] for x in
        #                             ShopProduct.objects.filter(
        #                                 product__baselinker_id__in=products_list
        #                             ).values('pk', 'product__baselinker_id')
        #     }
        #     data = []
        #     for bl_id, database_id in shop_products_id_map.items():
        #         try:
        #             if bl_data[bl_id]['price_brutto'] != 0:
        #                 data.append({'id': database_id, 'default_price_value': Decimal(bl_data[bl_id]['price_brutto']).quantize(Decimal('0.01'))})
        #         except KeyError as e:
        #                 logger.error(e)
        #     ShopProduct.objects.bulk_update([ShopProduct(**kv) for kv in data], ['default_price_value'])
        #     ids = [x['id'] for x in data]
        #     existing_prods = [{'id': x.pk, 'default_price_value': x.default_price_value.quantize(Decimal('0.01'))} for x
        #                       in ShopProduct.objects.filter(id__in=ids).only('pk', 'default_price_value')]
        #     to_save = [x['id'] for x in data if x not in existing_prods]
        #     for sp in ShopProduct.objects.filter(pk__in=to_save):
        #         sp.save()
        #     for product in Product.objects.annotate(
        #             Count('simple_supplier_stock_count')
        #     ).exclude(
        #         simple_supplier_stock_count__count__gt=0
        #     ):
        #         try:
        #             StockCount.objects.create(
        #                 product=product, supplier=product.shop_products.first().suppliers.first()
        #             )
        #         except Exception as e:
        #             continue
        #
        #     stock_id_map = {
        #         x['product__baselinker_id']: x['pk'] for x in
        #         StockCount.objects.filter(
        #             product__baselinker_id__in=products_list
        #         ).values('pk', 'product__baselinker_id')
        #     }
        #     data = []
        #     for bl_id, database_id in stock_id_map.items():
        #         try:
        #             data.append({'id': database_id,
        #                          'logical_count': Decimal(bl_data[bl_id]["quantity"]),
        #                          'physical_count': Decimal(bl_data[bl_id]["quantity"])})
        #         except KeyError as e:
        #             logger.error(e)
        #     StockCount.objects.bulk_update([StockCount(**kv) for kv in data], ['logical_count', 'physical_count'])

    def get_shipping_costs(self, basket):
        waive_limit = basket.shipping_method.behavior_components.filter(waivingcostbehaviorcomponent__isnull=False).first()
        if waive_limit:
            if waive_limit.waive_limit_value <= basket.taxful_total_price_of_products.amount.value:
                return 0
        costs = []
        for component in basket.shipping_method.behavior_components.all():
            try:
                costs.append(getattr(component, 'price_value'))
            except AttributeError:
                continue
        return float(sum(costs))

    def sync_prods_with_bl(self):
        try:
            categories = self.shop.bl_categories
        except ObjectDoesNotExist:
            return
        allowed_categories = []
        for category_id, category_data in categories.categories.items():
            if category_data['active']:
                allowed_categories.append(category_id)

        ids_to_add = []
        bl_ids = Product.objects.exclude(baselinker_id=None).values_list('baselinker_id', flat=True)
        for _ in range(1, 100):
            payload = {'token': self.token,
                       'method': 'getProductsList'}
            parameters = {"storage_id": self.storage, "page": _}
            payload['parameters'] = json.dumps(parameters)
            stock = perform_request(payload)
            products_list = stock.get('products')
            if not products_list:
                break
            ids_to_add.extend([x['product_id'] for x in stock['products'] if x['product_id'] not in bl_ids])

        chunks = []
        for i in range(0, len(ids_to_add), 1000):
            chunks.append(ids_to_add[i:i + 1000])

        for chunk in chunks:
            payload = {'token': self.token,
                       'method': 'getProductsData'}

            parameters = {"storage_id": self.storage, "products": chunk}
            payload['parameters'] = json.dumps(parameters)
            data = perform_request(payload)
            product_list = data.get('products')
            if product_list:
                for product in product_list.values():
                    create_single_product(product, ids_to_add, self.shop.pk)

    def _download_and_save_image(self, url, product, iterator):
        img = requests.get(url).content
        image = ImageFile(io.BytesIO(img), name=f'{str(uuid.uuid4())}.jpg')
        filer_file = filer_image_from_upload(request=None, path=None, upload_data=image)
        file = ensure_media_file(Shop.objects.first(), filer_file)
        product_media = ProductMedia.objects.create(kind=ProductMediaKind.IMAGE,
                                                    file=file.file,
                                                    product=product)
        product_media.shops.add(Shop.objects.first())
        if iterator == 0:
            product.primary_image = product_media
            product.save()

    def get_categories(self):
        payload = {'token': self.token,
                   'method': 'getCategories'}
        parameters = {"storage_id": self.storage}
        payload['parameters'] = json.dumps(parameters)
        return perform_request(payload)

    def _strip_html_tags(self, description):
        soup = BeautifulSoup(description)
        return ''.join(soup.findAll(text=True))
