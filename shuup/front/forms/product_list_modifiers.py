# -*- coding: utf-8 -*-
# This file is part of Shuup.
#
# Copyright (c) 2012-2021, Shuup Commerce Inc. All rights reserved.
#
# This source code is licensed under the OSL-3.0 license found in the
# LICENSE file in the root directory of this source tree.
import decimal
import six
from collections import defaultdict
from django import forms
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.text import capfirst
from shuup.core.slugify import slugify
from django.utils.translation import get_language, ugettext_lazy as _
from itertools import chain

from shuup import configuration as shuup_config
from shuup.admin.forms.fields import Select2MultipleField
from shuup.core.models import (
    Attribute,
    AttributeType,
    Category,
    Manufacturer,
    ProductVariationVariable,
    ShopProduct,
    ShopProductVisibility, Product,
)
from shuup.core.utils import context_cache
from shuup.discounts.models import Discount
from shuup.front.utils.sorts_and_filters import (
    ProductListFormModifier,
    _get_category_configuration_key,
    get_configuration,
    get_form_field_label,
)
from shuup.utils.i18n import format_money


class FilterWidget(forms.SelectMultiple):
    def render(self, name, value, attrs=None, choices=(), renderer=None):
        if value is None:
            value = []
        choices_to_render = []
        for option_value, option_label in chain(self.choices, choices):
            choices_to_render.append((option_value, option_label))
        return mark_safe(
            render_to_string(
                "shuup/front/product/filter_choice.jinja",
                {"name": name, "values": value, "choices": choices_to_render, "one_choice": False},
            )
        )


class OneChoiceFilterWidget(forms.Select):
    def render(self, name, value, attrs=None, choices=(), renderer=None):
        if value is None:
            value = []
        choices_to_render = []
        for option_value, option_label in chain(self.choices, choices):
            choices_to_render.append((option_value, option_label))

        return mark_safe(
            render_to_string(
                "shuup/front/product/filter_choice.jinja",
                {"name": name, "values": value, "choices": choices_to_render, "one_choice": True},
            )
        )


class CommaSeparatedListField(forms.CharField):
    def to_python(self, value):
        if isinstance(value, (list, tuple)) and len(value) == 1:
            value = value[0].split(",")
        else:
            value = super(CommaSeparatedListField, self).to_python(value)
        return value

    def prepare_value(self, value):
        if isinstance(value, (list, tuple)) and len(value) == 1:
            value = value[0].split(",")
        return value


class SimpleProductListModifier(ProductListFormModifier):
    is_active_key = ""
    is_active_label = ""
    ordering_key = ""
    ordering_label = ""

    def should_use(self, configuration):
        if not configuration:
            return
        return bool(configuration.get(self.is_active_key))

    def get_ordering(self, configuration):
        if not configuration:
            return 1
        return configuration.get(self.ordering_key, 1)

    def get_admin_fields(self):
        return [
            (self.is_active_key, forms.BooleanField(label=self.is_active_label, required=False)),
            (self.ordering_key, forms.IntegerField(label=self.ordering_label, initial=1, required=False)),
        ]


class SortProductListByName(SimpleProductListModifier):
    is_active_key = "sort_products_by_name"
    is_active_label = _("Sort products by name")
    ordering_key = "sort_products_by_name_ordering"
    ordering_label = _("Ordering for sort by name")

    def get_fields(self, request, category=None):
        return [
            (
                "sort",
                forms.CharField(required=False, widget=forms.Select(), label=get_form_field_label("sort", _("Sort"))),
            )
        ]

    def get_choices_for_fields(self):
        return [
            (
                "sort",
                [
                    ("name_a", get_form_field_label("name_a", _("Name - A-Z"))),
                    ("name_d", get_form_field_label("name_d", _("Name - Z-A"))),
                ],
            ),
        ]

    def sort_products(self, request, products, data):
        sort = data.get("sort", "name_a")

        def _get_product_name_lowered_stripped(product):
            return product.name.lower().strip()

        if not sort:
            sort = ""

        key = sort[:-2] if sort.endswith(("_a", "_d")) else sort
        if key == "name":
            sorter = _get_product_name_lowered_stripped
            reverse = bool(sort.endswith("_d"))
            products = sorted(products, key=sorter, reverse=reverse)
        return products

    def get_admin_fields(self):
        default_fields = super(SortProductListByName, self).get_admin_fields()
        default_fields[0][1].help_text = _("Enable this to allow products to be sortable by product name.")
        default_fields[1][1].help_text = _(
            "Use a numeric value to set the order in which the the filter will appear on the " "product listing page."
        )
        return default_fields


class SortProductListByPrice(SimpleProductListModifier):
    is_active_key = "sort_products_by_price"
    is_active_label = _("Sort products by price")
    ordering_key = "sort_products_by_price_ordering"
    ordering_label = _("Ordering for sort by price")

    def get_fields(self, request, category=None):
        return [
            (
                "sort",
                forms.CharField(required=False, widget=forms.Select(), label=get_form_field_label("sort", _("Sort"))),
            )
        ]

    def get_choices_for_fields(self):
        return [
            (
                "sort",
                [
                    ("price_a", get_form_field_label("price_a", _("Price - Low to High"))),
                    ("price_d", get_form_field_label("price_d", _("Price - High to Low"))),
                ],
            ),
        ]

    def sort_products(self, request, products, data):
        sort = data.get("sort")

        def _get_product_price_getter_for_request(request):
            def _get_product_price(product):
                return product.get_price(request)

            return _get_product_price

        if not sort:
            sort = ""

        key = sort[:-2] if sort.endswith(("_a", "_d")) else sort
        if key == "price":
            reverse = bool(sort.endswith("_d"))
            sorter = _get_product_price_getter_for_request(request)
            return sorted(products, key=sorter, reverse=reverse)
        return products

    def get_admin_fields(self):
        default_fields = super(SortProductListByPrice, self).get_admin_fields()
        default_fields[0][1].help_text = _(
            "Enable this to allow products to be sortable by price (from low to high; from high to low)."
        )
        default_fields[1][1].help_text = _(
            "Use a numeric value to set the order in which the the filter will appear on the " "product listing page."
        )
        return default_fields


class SortProductListByCreatedDate(SimpleProductListModifier):
    is_active_key = "sort_products_by_date_created"
    is_active_label = _("Sort products by date created")
    ordering_key = "sort_products_by_date_created_ordering"
    ordering_label = _("Ordering for sort by date created")

    def get_fields(self, request, category=None):
        return [
            (
                "sort",
                forms.CharField(required=False, widget=forms.Select(), label=get_form_field_label("sort", _("Sort"))),
            )
        ]

    def get_choices_for_fields(self):
        return [
            (
                "sort",
                [
                    ("created_date_d", get_form_field_label("created_date_d", _("Date created"))),
                ],
            ),
        ]

    def sort_products(self, request, products, data):
        sort = data.get("sort")

        def _get_product_created_on_datetime(product):
            return product.created_on

        if not sort:
            sort = ""

        key = sort[:-2] if sort.endswith(("_a", "_d")) else sort
        if key == "created_date":
            sorter = _get_product_created_on_datetime
            reverse = bool(sort.endswith("_d"))
            products = sorted(products, key=sorter, reverse=reverse)
        return products

    def get_admin_fields(self):
        default_fields = super(SortProductListByCreatedDate, self).get_admin_fields()
        default_fields[0][1].help_text = _(
            "Enable this to allow products to be sortable from newest to oldest products."
        )
        default_fields[1][1].help_text = _(
            "Use a numeric value to set the order in which the filter will appear on the " "product listing page."
        )
        return default_fields


class SortProductListByAscendingCreatedDate(SortProductListByCreatedDate):
    is_active_key = "sort_products_by_ascending_created_date"
    is_active_label = _("Sort products by date created - oldest first")
    ordering_key = "sort_products_by_ascending_created_date_ordering"
    ordering_label = _("Ordering for sort by date created - oldest first")

    def get_choices_for_fields(self):
        return [
            (
                "sort",
                [
                    ("created_date_a", get_form_field_label("created_date_a", _("Date created - oldest first"))),
                ],
            ),
        ]

    def get_admin_fields(self):
        default_fields = super(SortProductListByAscendingCreatedDate, self).get_admin_fields()
        default_fields[0][1].help_text = _(
            "Enable this to allow products to be sortable from oldest to newest products."
        )
        default_fields[1][1].help_text = _(
            "Use a numeric value to set the order in which the filter will appear on the " "product listing page."
        )
        return default_fields


class ManufacturerProductListFilter(SimpleProductListModifier):
    is_active_key = "filter_products_by_manufacturer"
    is_active_label = _("Filter products by manufacturer")
    ordering_key = "filter_products_by_manufacturer_ordering"
    ordering_label = _("Ordering for filter by manufacturer")

    def get_fields(self, request, category=None):
        if not Manufacturer.objects.filter(Q(shops__isnull=True) | Q(shops=request.shop)).exists():
            return

        shop_products_qs = ShopProduct.objects.filter(shop=request.shop).exclude(
            visibility=ShopProductVisibility.NOT_VISIBLE
        )

        if category:
            shop_products_qs = shop_products_qs.filter(Q(primary_category=category) | Q(categories=category))

        queryset = Manufacturer.objects.filter(
            Q(product__shop_products__in=shop_products_qs), Q(shops=request.shop) | Q(shops__isnull=True)
        ).distinct()

        if not queryset.exists():
            return

        return [
            (
                "manufacturers",
                CommaSeparatedListField(
                    required=False,
                    label=get_form_field_label("manufacturers", _("Manufacturers")),
                    widget=FilterWidget(choices=[(mfgr.pk, mfgr.name) for mfgr in queryset]),
                ),
            ),
        ]

    def get_filters(self, request, data):
        manufacturers = data.get("manufacturers")
        if manufacturers:
            return Q(manufacturer__in=manufacturers)

    def get_admin_fields(self):
        default_fields = super(ManufacturerProductListFilter, self).get_admin_fields()
        default_fields[0][1].help_text = _(
            "Enable this to allow products to be filterable by manufacturer for this category."
        )
        default_fields[1][1].help_text = _(
            "Use a numeric value to set the order in which the manufacturer filters will appear on the "
            "product listing page."
        )
        return default_fields


class CategoryProductListFilter(SimpleProductListModifier):
    is_active_key = "filter_products_by_category"
    is_active_label = _("Filter products by category")
    ordering_key = "filter_products_by_category_ordering"
    ordering_label = _("Ordering for filter by category")

    def get_fields(self, request, category=None):
        if not Category.objects.filter(shops=request.shop).exists():
            return

        key, val = context_cache.get_cached_value(
            identifier="categoryproductfilter", item=self, context=request, category=category
        )
        if val:
            return val

        language = get_language()
        base_queryset = Category.objects.all_visible(request.customer, request.shop, language=language)
        if category:
            q = Q(
                Q(shop_products__categories=category), ~Q(shop_products__visibility=ShopProductVisibility.NOT_VISIBLE)
            )
            queryset = base_queryset.filter(q).exclude(pk=category.pk).distinct()
        else:
            # Show only first level when there is no category selected
            queryset = base_queryset.filter(parent=None)

        data = [
            (
                "categories",
                CommaSeparatedListField(
                    required=False,
                    label=get_form_field_label("categories", _("Categories")),
                    widget=FilterWidget(choices=[(cat.pk, cat.name) for cat in queryset]),
                ),
            )
        ]
        context_cache.set_cached_value(key, data)
        return data

    def get_filters(self, request, data):
        categories = data.get("categories")
        if not categories:
            return

        if not isinstance(categories, (list, tuple)):
            categories = list(categories)

        categories = [cat.strip() for cat in categories if cat]
        if categories:
            return Q(
                shop_products__categories__in=Category.objects.get_queryset_descendants(
                    Category.objects.filter(pk__in=categories), include_self=True
                )
            )

    def get_admin_fields(self):
        default_fields = super(CategoryProductListFilter, self).get_admin_fields()
        default_fields[0][1].help_text = _(
            "Enable this to allow products to be filterable by any visible product category. "
        )
        default_fields[1][1].help_text = _(
            "Use a numeric value to set the order in which the category list filters will appear on the "
            "product listing page."
        )
        return default_fields


class LimitProductListPageSize(SimpleProductListModifier):
    is_active_key = "limit_product_list_page_size"
    is_active_label = _("Limit page size")
    ordering_key = "limit_product_list_page_size_ordering"
    ordering_label = _("Ordering for limit page size")

    def get_fields(self, request, category=None):
        return [
            (
                "limit",
                forms.IntegerField(
                    required=False, widget=forms.Select(), label=get_form_field_label("limit", _("Products per page"))
                ),
            )
        ]

    def get_choices_for_fields(self):
        return [
            ("limit", [(12, 12), (24, 24), (36, 36), (48, 48)]),
        ]

    def get_admin_fields(self):
        default_fields = super(LimitProductListPageSize, self).get_admin_fields()
        default_fields[0][1].help_text = _(
            "Enable this to allow the customer to be able to select the number of products to display."
        )
        default_fields[1][1].help_text = _(
            "Use a numeric value to set the order in which the page size filter will appear on the "
            "product listing page."
        )
        return default_fields


class ProductVariationFilter(SimpleProductListModifier):
    is_active_key = "filter_products_by_variation_value"
    is_active_label = _("Filter products by variation")
    ordering_key = "filter_products_by_variation_value_ordering"
    ordering_label = _("Ordering for filter by variation")

    def get_fields(self, request, category=None):
        if not category:
            return

        key, val = context_cache.get_cached_value(
            identifier="productvariationfilter", item=self, context=request, category=category
        )
        if val:
            return val

        variation_values = defaultdict(set)
        for variation in ProductVariationVariable.objects.filter(
                Q(product__shop_products__categories=category),
                ~Q(product__shop_products__visibility=ShopProductVisibility.NOT_VISIBLE),
        ):
            for value in variation.values.all():
                # TODO: Use ID here instead of this "trick"
                choices = (value.value.replace(" ", "*"), value.value)
                variation_values[slugify(variation.name)].add(choices)

        fields = []
        for variation_key, choices in six.iteritems(variation_values):
            fields.append(
                (
                    "variation_%s" % variation_key,
                    CommaSeparatedListField(
                        required=False, label=capfirst(variation_key), widget=FilterWidget(choices=choices)
                    ),
                )
            )
        context_cache.set_cached_value(key, fields)
        return fields

    def get_queryset(self, queryset, data):
        if not any([key for key in data.keys() if key.startswith("variation")]):
            return

        for key, values in six.iteritems(data):
            if key.startswith("variation"):
                variation_query = Q()
                for value in list(values):
                    # TODO: When using id this should search value for id
                    variation_query |= Q(
                        variation_variables__values__translations__value__iexact=value.replace("*", " ")
                    )
                queryset = queryset.filter(variation_query)
        return queryset

    def get_admin_fields(self):
        default_fields = super(ProductVariationFilter, self).get_admin_fields()
        default_fields[0][1].help_text = _(
            "Enable this to allow products to be filterable by their different variations. "
            "For example, size or color."
        )
        default_fields[1][1].help_text = _(
            "Use a numeric value to set the order in which the variation filters will appear on the "
            "product listing page."
        )
        return default_fields


class ProductPriceFilter(SimpleProductListModifier):
    is_active_key = "filter_products_by_price"
    is_active_label = _("Filter products by price")
    ordering_key = "filter_products_by_price_ordering"
    ordering_label = _("Ordering for filter by price")
    range_min_key = "filter_products_by_price_range_min"
    range_max_key = "filter_products_by_price_range_max"
    range_size_key = "filter_products_by_price_range_size"

    def get_fields(self, request, category=None):
        if not category:
            return

        # TODO: Add cache
        configuration = get_configuration(request.shop, category)

        min_price = configuration.get(self.range_min_key)
        max_price = configuration.get(self.range_max_key)
        range_size = configuration.get(self.range_size_key)
        if not (min_price and max_price and range_size):
            return

        choices = get_price_ranges(request.shop, min_price, max_price, range_size)
        return [
            (
                "price_range",
                forms.MultipleChoiceField(
                    required=False, choices=choices, label=get_form_field_label("price_range", _("Price")),
                    widget=forms.CheckboxSelectMultiple
                ),
            ),
        ]

    def filter_products(self, request, products, data):
        selected_range = data.get("price_range")
        if not selected_range:
            return products
        min_price, max_price = selected_range[0].split("-", 1)
        if len(selected_range) > 1:
            min_price_value = selected_range[0].split('-', 1)[0]
            try:
                int(min_price_value)
            except ValueError:
                min_price = selected_range[0].split('-', 1)[1]
        min_price_value = decimal.Decimal(min_price or 0)
        max_price_value = decimal.Decimal(max_price or 0)
        filtered_products = []
        for product in products:
            price_value = product.get_price(request).amount.value
            if price_value >= min_price_value and (max_price == "" or price_value < max_price_value):
                filtered_products.append(product)
        return filtered_products

    def get_admin_fields(self):
        default_fields = super(ProductPriceFilter, self).get_admin_fields()
        default_fields[0][1].help_text = _(
            "Enable this to allow products to be filtered by price. "
            "Prices will be listed in groups from the price range minimum to price range maximum in increments of "
            "the configured price range step."
        )
        default_fields[1][1].help_text = _(
            "Use a numeric value to set the order in which the price range filters will appear on the "
            "product listing page."
        )
        min_field = forms.IntegerField(
            label=_("Price range minimum"),
            min_value=0,
            required=False,
            help_text=_("Set the minimum price for the filter. The first range will be from zero to this value."),
        )
        max_field = forms.IntegerField(
            label=_("Price range maximum"),
            min_value=0,
            required=False,
            help_text=_("Set the maximum price for the filter. The last range will include this value and above."),
        )
        range_step = forms.IntegerField(
            label=_("Price range step"),
            min_value=0,
            required=False,
            help_text=_("Set the price step for each range. Each range will increment by this value."),
        )
        return default_fields + [
            (self.range_min_key, min_field),
            (self.range_max_key, max_field),
            (self.range_size_key, range_step),
        ]


class AttributeProductListFilter(SimpleProductListModifier):
    is_active_key = "filter_products_by_products_attribute"
    is_active_label = _("Filter products by its attributes")
    ordering_key = "filter_products_by_attribute_ordering"
    product_attr_key = "filter_products_by_product_attribute_field"

    def _build_attribute_filter_fields(
            self,
            attributes,
    ):
        fields = []
        for attribute in attributes:
            if attribute.type == AttributeType.CHOICES and attribute.choices.exists():
                fields.append(
                    [
                        attribute.identifier,
                        CommaSeparatedListField(
                            required=False,
                            widget=FilterWidget(
                                choices=[(choice.id, choice.name) for choice in attribute.choices.all()],
                            ),
                            label=_(attribute.name),
                        ),
                    ]
                )

        return fields

    def _get_attributes_from_shop_config(self, shop):
        config = get_configuration(shop)
        filterable_attribute_pks = config.get(self.product_attr_key)

        attributes = Attribute.objects.all()
        if filterable_attribute_pks:
            return attributes.filter(pk__in=filterable_attribute_pks)

        return attributes

    def _get_attributes_from_category(self, shop, category):
        category_config = shuup_config.get(shop, _get_category_configuration_key(category))
        attributes = Attribute.objects.all()
        if category_config and category_config.get("override_default_configuration", False):
            filterable_attribute_pks = category_config.get(self.product_attr_key)
        else:
            config = get_configuration(shop)
            filterable_attribute_pks = config.get(self.product_attr_key)
        if filterable_attribute_pks:
            return attributes.filter(pk__in=filterable_attribute_pks)
        return attributes

    def get_fields(
            self,
            request,
            category=None,
    ):
        if category:
            attributes = self._get_attributes_from_category(request.shop, category)
        else:
            attributes = self._get_attributes_from_shop_config(request.shop)

        return self._build_attribute_filter_fields(attributes)

    def _get_product_attribute_query_strings(self, data):
        """
        Get product attribute in querystring that has truthy values
        """
        attribute_identifiers = Attribute.objects.all().values_list("identifier", flat=True)

        attribute_query_strings = [key for key, value in data.items() if value and key in attribute_identifiers]

        return attribute_query_strings

    def get_queryset(self, queryset, data):
        # Filter for chosen attributes
        attributes = self._get_product_attribute_query_strings(data)
        if not attributes:
            return queryset

        for attribute in attributes:
            values = data.get(attribute, [])
            queryset = queryset.filter(
                attributes__attribute__identifier=attribute,
                attributes__chosen_options__id__in=values,
            )

        return queryset

    def get_admin_fields(self):
        active, ordering = super(AttributeProductListFilter, self).get_admin_fields()
        active[1].help_text = _("Allow products to be filtered according to their attributes.")

        attributes = Select2MultipleField(
            model=Attribute,
            label=_("Attributes that can be filtered"),
            required=False,
            help_text=_("Select attributes that can used for filtering the products."),
        )

        return [active, (self.product_attr_key, attributes), ordering]

    def clean_hook(self, form):
        attribute_query_strings = self._get_product_attribute_query_strings(form.data)

        for attribute_query_string in attribute_query_strings:
            form.cleaned_data[attribute_query_string] = form.data.get(attribute_query_string).split(",")

        return super().clean_hook(form)


class DiscountedProductListFilter(SimpleProductListModifier):
    is_active_key = "filter_products_by_discounts"
    is_active_label = _("Filter products by discounts")
    ordering_key = "filter_products_by_discounts_ordering"
    ordering_label = _("Ordering for filter by discounts")

    def get_fields(self, request, category=None):
        discounts = Discount.objects.available(shop=request.shop)

        if category:
            queryset = Product.objects.filter(
                Q(product_discounts__in=discounts) | Q(shop_products__categories__category_discounts__in=discounts)
            ).distinct()
        else:
            queryset = Product.objects.filter(
                product_discounts__in=discounts
            ).distinct()

        if not queryset.exists():
            return

        return [
            (
                "discounts",
                forms.ChoiceField(
                    required=False, choices=[("discounted", "Tylko przecenione produkty")],
                    label=get_form_field_label("discounts", _("Discounts")),
                    widget=OneChoiceFilterWidget
                ),
            ),
        ]

    def get_filters(self, request, data):
        filter_discounts = data.get("discounts")

        if filter_discounts:
            discounts = Discount.objects.available(shop=request.shop)

            return Q(product_discounts__in=discounts)

    def filter_products(self, request, products, data):
        filter_discounts = data.get("discounts")
        if not filter_discounts:
            return products
        discounts = Discount.objects.available(shop=request.shop)

        queryset = Product.objects.filter(
            product_discounts__in=discounts
        ).distinct()
        return queryset

    def get_admin_fields(self):
        default_fields = super(DiscountedProductListFilter, self).get_admin_fields()
        default_fields[0][1].help_text = _(
            "Enable this to allow products to be filterable by discounts for this category."
        )
        default_fields[1][1].help_text = _(
            "Use a numeric value to set the order in which the discounts filters will appear on the "
            "product listing page."
        )
        return default_fields


def get_price_ranges(shop, min_price, max_price, range_step):
    if range_step == 0:
        return

    ranges = []
    # TODO: translations change
    min_price_value = format_money(shop.create_price(min_price))
    # ranges.append(("-%s" % min_price, _("Under %(min_limit)s") % {"min_limit": str(min_price_value)[:-3]}))
    ranges.append(("-%s" % min_price,
                   "Poniżej %(min_limit)s" % {"min_limit": str(min_price_value)[:3] + str(min_price_value)[-3:]}))

    for range_min in range(min_price, max_price, range_step):
        range_min_price = format_money(shop.create_price(range_min))
        range_max = range_min + range_step
        if range_max < max_price:
            range_max_price = format_money(shop.create_price(range_max))
            ranges.append(
                (
                    "%s-%s" % (range_min, range_max),
                    # _("%(min)s to %(max)s") % dict(min=str(range_min_price)[:-3], max=str(range_max_price)[:-3]),
                    "%(min)s do %(max)s" % dict(min=str(range_min_price)[:3] + str(range_min_price)[-3:],
                                                max=str(range_max_price)[:3] + str(range_max_price)[-3:]),
                )
            )

    max_price_value = format_money(shop.create_price(max_price))
    # ranges.append(("%s-" % max_price, _("%(max_limit)s & Above") % {"max_limit": str(max_price_value)[:-3]}))
    ranges.append(("%s-" % max_price,
                   "%(max_limit)s i powyżej" % {"max_limit": str(max_price_value)[:3] + str(max_price_value)[-3:]}))
    return ranges
