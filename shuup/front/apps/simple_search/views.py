# -*- coding: utf-8 -*-
# This file is part of Shuup.
#
# Copyright (c) 2012-2021, Shuup Commerce Inc. All rights reserved.
#
# This source code is licensed under the OSL-3.0 license found in the
# LICENSE file in the root directory of this source tree.
from __future__ import unicode_literals

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchVector, SearchRank
from django.views.generic import ListView

from shuup.core.models import Product
from shuup.front.template_helpers.product import is_visible
from shuup.front.utils.sorts_and_filters import (
    ProductListForm,
    get_product_queryset,
    get_query_filters,
    post_filter_products,
    sort_products,
)
from shuup.front.utils.views import cache_product_things
from shuup.core.models import SearchQuery as Sq


class SearchView(ListView):
    form_class = ProductListForm
    template_name = "shuup/simple_search/search.jinja"
    model = Product
    context_object_name = "products"

    def dispatch(self, request, *args, **kwargs):
        self.form = ProductListForm(request=self.request, shop=self.request.shop, category=None, data=self.request.GET)
        return super(SearchView, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Product.objects.none()

    def get_context_data(self, **kwargs):
        context = super(SearchView, self).get_context_data(**kwargs)
        query_params = self.request.GET
        context["form"] = self.form
        if query_params:
            params = '&'.join([f'{k}={v}' for k, v in query_params.items()])
            if settings.ENVIRONMENT == 'STAGING':
                context["search"] = f"{'https://' if self.request.is_secure() else 'http://'}{self.request.get_host()}/sklep/search-async/?{params}"
            else:
                context["search"] = f"{'https://' if self.request.is_secure() else 'http://'}{self.request.get_host()}/search-async/?{params}"
        return context


class AsyncSearchResults(ListView):

    form_class = ProductListForm
    template_name = "shuup/simple_search/search_async.jinja"
    model = Product
    context_object_name = "products"
    paginate_by = 12

    def dispatch(self, request, *args, **kwargs):
        self.form = ProductListForm(request=self.request, shop=self.request.shop, category=None, data=self.request.GET)
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        if not self.form.is_valid():
            return Product.objects.none()
        data = self.form.cleaned_data
        if not (data and data.get("q")):  # pragma: no cover
            return Product.objects.none()
        products = Product.objects.filter(get_query_filters(self.request, None, data=data), shop_products__visibility=3)
        query = data.get("q")
        query = SearchQuery(query)
        search_vector = SearchVector('translations__name', 'translations__description')
        sort = self.request.GET.get('sort')
        if sort:
            if sort == 'created_date_d':
                products = products.order_by('-pk')
            elif sort == 'price_a':
                products = products.order_by('shop_products__default_price_value')
            elif sort == 'price_d':
                products = products.order_by('-shop_products__default_price_value')
            return products
        products = products.annotate(
            search=search_vector, rank=SearchRank(search_vector, query))\
            .filter(
            search=query).order_by(
            "-rank"
        )
        # lista = []
        # for prod in products:
        #     lista.append([prod.name, 10 if any([val in prod.name for val in [query.capitalize(), query.upper(), query.lower()]]) else 0, 1 if any([val in prod.description for val in [query.capitalize(), query.upper(), query.lower()]]) else 0])
        # lista = sorted(lista, key=lambda x: sum([x[1], x[2]]), reverse=True)
        # products.sort(key=lambda x: sum([10 if any([val in x.name for val in [query.capitalize(), query.upper(), query.lower()]]) else 0, 1 if any([val in x.description for val in [query.capitalize(), query.upper(), query.lower()]]) else 0]), reverse=True)
        return products

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = self.form
        products = context["products"]
        query_params = self.request.GET
        if query_params:
            context["params"] = '&'.join([f'{k}={v}' for k, v in query_params.items() if k != 'page'])
        if products:
            data = self.form.cleaned_data
            # products = sort_products(self.request, None, products, data)
            context["products"] = products
            context['products_count'] = self.get_queryset().count()
        context["no_results"] = self.form.is_valid() and not products
        return context

    def get(self, request, *args, **kwargs):
        query = request.GET.get("q")
        Sq.objects.create(query=query)
        return super().get(request, *args, **kwargs)
