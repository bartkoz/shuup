# -*- coding: utf-8 -*-
# This file is part of Shuup.
#
# Copyright (c) 2012-2021, Shuup Commerce Inc. All rights reserved.
#
# This source code is licensed under the OSL-3.0 license found in the
# LICENSE file in the root directory of this source tree.
from __future__ import with_statement

from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.utils.safestring import mark_safe
from django.views.generic import DetailView
from shuup.front.utils.views import build_line

from shuup.core.models import Order
from shuup.front.signals import order_complete_viewed


class OrderCompleteView(DetailView):
    template_name = "shuup/front/order/complete.jinja"
    model = Order
    context_object_name = "order"

    def render_to_response(self, context, **response_kwargs):
        order_complete_viewed.send(sender=self, order=self.object, request=self.request)
        return super(OrderCompleteView, self).render_to_response(context, **response_kwargs)

    def get_object(self, queryset=None):
        return get_object_or_404(self.model, pk=self.kwargs["pk"], key=self.kwargs["key"])

    def _build_action_field(self, line, order_id, revenue):
        return {
            'id': str(order_id),
            'revenue': str(revenue),
            'tax': "0",
            'shipping': str(line.raw_taxful_price.value.quantize(Decimal("0.01"))),
            'coupon': ''
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product_orders = []
        for order in self.get_object().order_group.group.grouped_orders.all():
            prod_obj = {}
            prod_obj['order_lines'] = ([x for x in [build_line(line) for line in order.order.lines.all()] if x])
            for line in order.order.lines.all():
                if 'shipping' in line.extra_data.get('source_line_id'):
                    prod_obj['action_field'] = self._build_action_field(line, order.order.pk, order.order.taxful_total_price.value.quantize(Decimal("0.01")))
                    break
            product_orders.append(prod_obj)
        context['products'] = mark_safe(product_orders)
        return context


class OrderRequiresVerificationView(DetailView):
    template_name = "shuup/front/order/requires_verification.jinja"
    model = Order

    def get_object(self, queryset=None):
        return get_object_or_404(self.model, pk=self.kwargs["pk"], key=self.kwargs["key"])

    def get_context_data(self, **kwargs):
        context = super(OrderRequiresVerificationView, self).get_context_data(**kwargs)
        if self.object.user and self.object.user.password == "//IMPLICIT//":
            from shuup.shop.views.activation_views import OneShotActivationForm

            context["activation_form"] = OneShotActivationForm()
        return context

    def get(self, request, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)
