from django.db import models
from jsonfield import JSONField

from shuup.core.models import ShuupModel, Supplier


class BaseLinkerToken(ShuupModel):

    shop = models.OneToOneField(
        Supplier, related_name="bl_token", on_delete=models.CASCADE
    )
    token = models.CharField(max_length=100)
    storage = models.CharField(max_length=20)
    order_status_id = models.CharField(max_length=50)


class BaseLinkerCategories(ShuupModel):

    shop = models.OneToOneField(
        Supplier, related_name="bl_categories", on_delete=models.CASCADE
    )
    categories = JSONField()
