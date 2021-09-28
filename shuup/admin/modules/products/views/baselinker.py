from django.views.generic import FormView

from shuup.admin.modules.products.forms.base_forms import BaselinkerCategoryForm
from shuup.core.baselinker import BaseLinkerConnector
from shuup.core.models._baselinker import BaseLinkerCategories


class BaselinkerCategoryView(FormView):

    form_class = BaselinkerCategoryForm
    template_name = 'shuup/admin/products/baselinker.jinja'

    def _get_baselinker_categories_for_supplier(self, supplier):
        obj, created = BaseLinkerCategories.objects.get_or_create(shop=supplier)
        if created:
            bl_connector = BaseLinkerConnector(supplier)
            categories = {x["category_id"]: {"name": x["name"], "active": False}
                          for x in
                          bl_connector.get_categories()["categories"]}
            obj.categories = categories
            obj.save()
        return obj

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self._get_baselinker_categories_for_supplier(
            self.request.user.vendor_users.first().supplier
        )
        return kwargs

    def form_valid(self, form):
        for id, value in form.cleaned_data.items():
            form.instance.categories[id]['active'] = value
        form.instance.save()
        super().form_valid(form)