# -*- coding: utf-8 -*-
# This file is part of Shuup.
#
# Copyright (c) 2012-2021, Shuup Commerce Inc. All rights reserved.
#
# This source code is licensed under the OSL-3.0 license found in the
# LICENSE file in the root directory of this source tree.
from django.utils.safestring import mark_safe
from django.views.generic import TemplateView, View

from shuup.front.basket import get_basket_command_dispatcher, get_basket_view
from shuup.front.utils.views import build_line


class DefaultBasketView(TemplateView):
    template_name = "shuup/front/basket/default_basket.jinja"

    def get_context_data(self, **kwargs):
        context = super(DefaultBasketView, self).get_context_data()
        basket = self.request.basket  # noqa (F821) type: shuup.front.basket.objects.BaseBasket
        context["basket"] = basket
        context["errors"] = list(basket.get_validation_errors())
        context['products'] = mark_safe([x for x in [build_line(line) for line in basket.get_final_lines()] if x])
        context['delivery'] = sum([x.taxful_price.amount.value for x in basket.get_final_lines() if x.type.name == 'SHIPPING'])
        return context


class BasketView(View):
    def dispatch(self, request, *args, **kwargs):
        command = request.POST.get("command")
        if command:
            return get_basket_command_dispatcher(request).handle(command)
        else:
            return get_basket_view()(request, *args, **kwargs)
