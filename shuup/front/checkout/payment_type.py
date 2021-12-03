from django import forms
from django.views.generic import FormView
from django.utils.translation import ugettext_lazy as _

from shuup.front.checkout import CheckoutPhaseViewMixin
from shuup.utils.form_group import FormGroup
from shuup_stripe_multivendor.context_provider import get_payment_context_provider
from shuup.core.models import Order, get_person_contact


class PaymentTypeForm(forms.Form):

    payment_method = forms.ChoiceField(choices=[('p24', 'Przelewy 24'), ('card', 'Karta')],
                                       widget=forms.RadioSelect, label=_('Metoda Płatności'))


class PaymentTypeFormCardLocked(forms.Form):

    payment_method = forms.ChoiceField(choices=[('p24', 'Przelewy 24'), ('card', 'Karta')],
                                       widget=forms.RadioSelect, label=_('Metoda Płatności'),
                                       disabled=True,
                                       initial='card')

class PaymentTypeFormP224Locked(forms.Form):

    payment_method = forms.ChoiceField(choices=[('p24', 'Przelewy 24'), ('card', 'Karta')],
                                       widget=forms.RadioSelect, label=_('Metoda Płatności'),
                                       disabled=True,
                                       initial='p24')


class PaymentType(CheckoutPhaseViewMixin, FormView):
    identifier = "payment_type"
    title = _("Wybierz metodę wysyłki")

    template_name = "shuup/front/checkout/payment_method.jinja"

    def _should_lock(self):
        return all([x.status == 'succeeded' for x
                    in get_payment_context_provider(
                payment_processor=self.basket.payment_method.payment_processor,
                payer=get_person_contact(self.request.user)
            ).get_payment_context_for_basket(self.basket).payment_intents])

    def get_form(self, form_class=None):
        fg = FormGroup(**self.get_form_kwargs())
        if self._should_lock():
            if self.basket.extra_data.get('selected_payment_method') == 'card':
                fg.add_form_def('payment_type', form_class=PaymentTypeFormCardLocked)
            else:
                fg.add_form_def('payment_type', form_class=PaymentTypeFormP224Locked)
        else:
            fg.add_form_def('payment_type', form_class=PaymentTypeForm)
        return fg

    def is_valid(self):
        return True

    def form_valid(self, form):
        self.basket.extra_data['selected_payment_method'] = form.cleaned_data['payment_type']['payment_method']
        self.basket.save()
        return super().form_valid(form)

    def process(self):
        return
