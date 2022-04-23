from django.db import models
from jsonfield import JSONField

from shuup.core.models import ShuupModel, Supplier, Product


class BaseLinkerToken(ShuupModel):

    shop = models.OneToOneField(
        Supplier, related_name="bl_token", on_delete=models.CASCADE
    )
    token = models.CharField(max_length=100)
    storage = models.CharField(max_length=20)
    order_status_id = models.CharField(max_length=50)
    inventory = models.CharField(max_length=20, null=True)
    new_api = models.BooleanField(default=False)


class BaseLinkerCategories(ShuupModel):

    shop = models.OneToOneField(
        Supplier, related_name="bl_categories", on_delete=models.CASCADE
    )
    categories = JSONField()


class BaseLinkerProductProperties(ShuupModel):

    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="bl_product_properties")
    data = JSONField()


class SearchQuery(ShuupModel):
    query = models.CharField(max_length=512)
