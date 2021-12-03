# -*- coding: utf-8 -*-
# This file is part of Shuup.
#
# Copyright (c) 2012-2021, Shuup Commerce Inc. All rights reserved.
#
# This source code is licensed under the OSL-3.0 license found in the
# LICENSE file in the root directory of this source tree.
from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.views.generic import FormView
from logging import getLogger

from shuup.apps.provides import get_provide_objects
from shuup.core.baselinker import BaseLinkerConnector, create_redis_connection
from shuup.core.models import OrderStatus
from shuup.front.basket import get_basket_order_creator
from shuup.front.checkout import CheckoutPhaseViewMixin
from shuup.front.signals import checkout_complete

logger = getLogger(__name__)


class ConfirmForm(forms.Form):
    product_ids = forms.CharField(widget=forms.HiddenInput(), required=True)
    accept_terms = forms.BooleanField(required=True, label=mark_safe('Akceptuję <a class="btn-link" href="/regulamin" target="_blank">regulamin</a>'))
    marketing = forms.BooleanField(required=False, label=_(u"I want to receive marketing material"), initial=False)
    comment = forms.CharField(widget=forms.Textarea(), required=False, label=_(u"Comment"))

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        self.current_product_ids = kwargs.pop("current_product_ids", "")
        super(ConfirmForm, self).__init__(*args, **kwargs)

        # check whether we already asked for marketing permissions before
        # if so, make the field hidden and set the initial value
        customer = self.request.customer
        if customer.options and customer.options.get("marketing_permission_asked"):
            self.fields["marketing"].widget = forms.HiddenInput()
            self.fields["marketing"].initial = customer.marketing_permission

        for provider_cls in get_provide_objects("checkout_confirm_form_field_provider"):
            provider = provider_cls()
            for definition in provider.get_fields(request=self.request):
                self.fields[definition.name] = definition.field

        field_properties = settings.SHUUP_CHECKOUT_CONFIRM_FORM_PROPERTIES
        for field, properties in field_properties.items():
            for prop in properties:
                setattr(self.fields[field], prop, properties[prop])

    def clean(self):
        product_ids = set(self.cleaned_data.get("product_ids", "").split(","))
        if product_ids != self.current_product_ids:
            raise forms.ValidationError(
                _("There has been a change in product availability. Please review your cart and reconfirm your order.")
            )


class ConfirmPhase(CheckoutPhaseViewMixin, FormView):
    identifier = "confirm"
    # TODO: translations change
    # title = _("Confirmation")
    title = _("Podsumowanie")
    template_name = "shuup/front/checkout/confirm.jinja"
    form_class = ConfirmForm

    def process(self):
        self.basket.customer_comment = self.storage.get("comment")
        self.basket.marketing_permission = self.storage.get("marketing")

    def is_valid(self):
        # check that all form keys starting with "accept_" must have a valid value
        not_accepted_keys = [
            key for key in self.storage.keys() if key.startswith("accept_") and not self.storage.get(key)
        ]
        return bool(len(not_accepted_keys) == 0)

    def _get_product_ids(self):
        return [str(product_id) for product_id in self.basket.get_product_ids_and_quantities().keys()]

    def get_form_kwargs(self):
        kwargs = super(ConfirmPhase, self).get_form_kwargs()
        kwargs["request"] = self.request
        kwargs["current_product_ids"] = set(self._get_product_ids())
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(ConfirmPhase, self).get_context_data(**kwargs)
        basket = self.basket

        basket.calculate_taxes()
        errors = list(basket.get_validation_errors())
        context["basket"] = basket
        context["errors"] = errors
        context["orderable"] = not errors
        context["product_ids"] = ",".join(self._get_product_ids())
        return context

    def form_valid(self, form):
        for key, value in form.cleaned_data.items():
            self.storage[key] = value
        if settings.USE_BASELINKER:
            self.verify_with_baselinker()
            # self.update_baselinker_storage()
            # self.add_baselinker_order(form.cleaned_data.get('comment'))
        self.process()
        self.basket.save()
        self.basket.storage.add_log_entry(self.basket, _("Starting to create order."))

        order = self.create_order()
        # self.checkout_process.complete()  # Inform the checkout process it's completed

        # make sure to set marketing permission asked once
        if "marketing" in form.fields and order.customer:
            if not order.customer.options or not order.customer.options.get("marketing_permission_asked"):
                order.customer.options = order.customer.options or {}
                order.customer.options["marketing_permission_asked"] = True
                order.customer.save(update_fields=["options"])
        return redirect("/checkout/payment/")
        # if order.require_verification:
        #     response = redirect("shuup:order_requires_verification", pk=order.pk, key=order.key)
        # else:
        #     response = redirect("shuup:order_process_payment", pk=order.pk, key=order.key)
        #
        # # checkout_complete.send(sender=type(self), request=self.request, user=self.request.user, order=order)
        #
        # return response

    def create_order(self):
        basket = self.basket
        assert basket.shop == self.request.shop
        basket.orderer = self.request.person
        basket.customer = self.request.customer
        basket.creator = self.request.user
        if "impersonator_user_id" in self.request.session:
            basket.creator = get_user_model().objects.get(pk=self.request.session["impersonator_user_id"])
        basket.status = OrderStatus.objects.get_default_initial()
        order_creator = get_basket_order_creator()
        order = order_creator.create_order(basket)
        # basket.finalize()
        basket.extra_data['order_pk'] = order.pk
        basket.save()
        return order

    def verify_with_baselinker(self):
        for item in self.basket.get_lines():
            bl_connector = BaseLinkerConnector(item.shop_product.suppliers.first())
            is_available = bl_connector.check_if_product_still_available(product_id=item.product.baselinker_id,
                                                                         count=int(item.quantity))
            if not is_available:
                self.basket.delete()
                raise forms.ValidationError(
                    _(f'{item.product.name} nie jest juz dostępny, płatność nie została pobrana.'))

    def update_baselinker_storage(self):
        for item in self.basket.get_lines():
            bl_connector = BaseLinkerConnector(item.shop_product.suppliers.first())
            product_id = item.product.baselinker_id
            quantity = int(item.quantity)
            # TODO: make it work with variants
            variant_id = None
            current_quantity = bl_connector.get_current_storage(product_id=item.product.baselinker_id)
            final_quantity = current_quantity - item.quantity
            bl_connector.update_product_quantity(product_id=product_id,
                                                 count=final_quantity)

    def add_baselinker_order(self, comment):
        from shuup_multivendor.basket import SupplierBasket
        for supplier_tuple in self.basket.supplier_baskets:
            for supplier_basket in supplier_tuple:
                if isinstance(supplier_basket, SupplierBasket):
                    if supplier_basket.get_lines():
                        bl_connector = BaseLinkerConnector(supplier_basket.supplier)
                        bl_connector.add_order(supplier_basket, comment)
