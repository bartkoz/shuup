from django.db import models
from shuup.core.models import ShuupModel, Shop, Product


class BaseLinkerToken(ShuupModel):

    shop = models.OneToOneField(
        Shop, related_name="bl_token", on_delete=models.CASCADE
    )
    token = models.CharField(max_length=100)
    storage = models.CharField(max_length=20)


class BaseLinkerProductLink(ShuupModel):

    product = models.OneToOneField(
        Product, related_name="bl_product_link", on_delete=models.CASCADE
    )
    bl_id = models.IntegerField()
