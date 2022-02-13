# -*- coding: utf-8 -*-
# This file is part of Shuup.
#
# Copyright (c) 2012-2021, Shuup Commerce Inc. All rights reserved.
#
# This source code is licensed under the OSL-3.0 license found in the
# LICENSE file in the root directory of this source tree.
from __future__ import with_statement

import logging
from decimal import Decimal

from django.utils.translation import get_language

from shuup.core.models import Product, ProductAttribute
from shuup.utils.translation import cache_translations

logger = logging.getLogger(__name__)


def cache_product_things(request, products, language=None, attribute_identifiers=("author",)):
    # Cache necessary things for products. WARNING: This will cause queryset iteration.
    language = language or get_language()
    # TODO: Should we cache prices here?
    if attribute_identifiers:
        Product.cache_attributes_for_targets(
            ProductAttribute, products, attribute_identifiers=attribute_identifiers, language=language
        )
    products = cache_translations(products, (language,))
    return products


def build_line(line):
    try:
        prod_category = line.shop_product.product.product_category
    except AttributeError:
        prod_category = 'null'
    try:
        return {
            'name': line.product.name,
            'id': line.product.sku,
            'price': str(line.base_unit_price.amount.value.quantize(Decimal('.01'))),
            'brand': line.supplier.name,
            'dimension11': '',
            'category': str(prod_category),
            'quantity': int(line.quantity)
        }
    except AttributeError:
        pass
