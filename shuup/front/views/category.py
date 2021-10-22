# -*- coding: utf-8 -*-
# This file is part of Shuup.
#
# Copyright (c) 2012-2021, Shuup Commerce Inc. All rights reserved.
#
# This source code is licensed under the OSL-3.0 license found in the
# LICENSE file in the root directory of this source tree.
from __future__ import with_statement

from django.core.paginator import Paginator
from django.views.generic import DetailView, TemplateView

from shuup.core.models import Category, Product, Supplier
from shuup.front.utils.sorts_and_filters import (
    ProductListForm,
    get_product_queryset,
    get_query_filters,
    post_filter_products,
    sort_products,
)
from shuup.front.utils.views import cache_product_things
from shuup_elasticsearch.engine import SearchContext, SearchEngine


def get_context_data(context, request, category, product_filters):
    data = request.GET
    context["form"] = form = ProductListForm(request=request, shop=request.shop, category=category, data=data)
    form.full_clean()
    data = form.cleaned_data
    if "sort" in form.fields and not data.get("sort"):
        # Use first choice by default
        data["sort"] = form.fields["sort"].widget.choices[0][0]

    # TODO: Check if context cache can be utilized here
    products = (
        Product.objects.listed(customer=request.customer, shop=request.shop)
        .filter(**product_filters)
        .filter(get_query_filters(request, category, data=data))
        .prefetch_related("sales_unit", "sales_unit__translations")
    )

    products = get_product_queryset(products, request, category, data).distinct()
    products = post_filter_products(request, category, products, data)
    products = cache_product_things(request, products)
    products = sort_products(request, category, products, data)
    context["page_size"] = data.get("limit", 15)
    context["products"] = products

    if "supplier" in data:
        context["supplier"] = data.get("supplier")

    return context


class CategoryView(DetailView):
    template_name = "shuup/front/product/category.jinja"
    model = Category
    template_object_name = "category"

    def _get_products(self, search_results, **kwargs):
        products_ids = [item.object_id for item in search_results.results]
        products = (
            Product.objects.listed(shop=self.request.shop, customer=self.request.customer)
            .filter(get_query_filters(self.request, None, data=[]), pk__in=products_ids)
        )
        return products

    def get_queryset(self):
        search_context = SearchContext(category_id=self.kwargs.get("pk"))
        search_engine = SearchEngine(context=search_context)
        search_engine.search_products('', limit=1000)
        paginator = Paginator(
            products,
            self.product_search_results_limit if is_product_search else self.general_search_product_results_limit,
        )
        page_number = self.request.GET.get("search_page") or 1
        return self.model.objects.all_visible(
            customer=self.request.customer,
            shop=self.request.shop,
        )

    def get_product_filters(self):
        return {
            "shop_products__shop": self.request.shop,
            "variation_parent__isnull": True,
            "shop_products__categories__in": self.object.get_descendants(include_self=True),
            "shop_products__suppliers__in": Supplier.objects.enabled(shop=self.request.shop),
        }

    def get_context_data(self, **kwargs):
        context = super(CategoryView, self).get_context_data(**kwargs)
        search_context = SearchContext(category_id=kwargs.get("pk"))
        search_engine = SearchEngine(context=search_context)
        search_engine.search_products('', limit=1000)
        paginator = Paginator(
            products,
            self.product_search_results_limit if is_product_search else self.general_search_product_results_limit,
        )
        page_number = self.request.GET.get("search_page") or 1
        context["products_page"] = paginator.get_page(page_number)
        context["products_num_pages"] = paginator.num_pages
        context["products_count"] = paginator.count
        return get_context_data(context, self.request, self.object, self.get_product_filters())


class AllCategoriesView(TemplateView):
    template_name = "shuup/front/product/category.jinja"

    def get_product_filters(self):
        category_ids = Category.objects.all_visible(
            customer=self.request.customer,
            shop=self.request.shop,
        ).values_list("id", flat=True)
        return {
            "shop_products__shop": self.request.shop,
            "variation_parent__isnull": True,
            "shop_products__categories__id__in": category_ids,
            "shop_products__suppliers__in": Supplier.objects.enabled(shop=self.request.shop),
        }

    def get_context_data(self, **kwargs):
        context = super(AllCategoriesView, self).get_context_data(**kwargs)
        context["category"] = None
        return get_context_data(context, self.request, None, self.get_product_filters())
