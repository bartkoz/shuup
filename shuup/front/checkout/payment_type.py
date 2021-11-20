from django import forms
from django.views.generic import FormView
from django.utils.translation import ugettext_lazy as _

from shuup.front.checkout import CheckoutPhaseViewMixin
from shuup.utils.form_group import FormGroup


class PaymentTypeForm(forms.Form):

    payment_method = forms.ChoiceField(choices=[('p24', 'Przelewy 24'), ('card', 'Karta')], widget=forms.RadioSelect, label=_('Metoda Płatności'))


class PaymentType(CheckoutPhaseViewMixin, FormView):
    identifier = "payment_type"
    title = _("Wybierz metodę płatności")

    template_name = "shuup/front/checkout/payment_method.jinja"

    def get_form(self, form_class=None):
        fg = FormGroup(**self.get_form_kwargs())
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
