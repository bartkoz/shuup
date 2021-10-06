# This file is part of Shuup.
#
# Copyright (c) 2012-2021, Shuup Commerce Inc. All rights reserved.
#
# This source code is licensed under the OSL-3.0 license found in the
# LICENSE file in the root directory of this source tree.
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.db.transaction import atomic
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.generic import FormView
from django.views import View

from shuup.admin.form_part import FormPartsViewMixin
from shuup.admin.modules.settings.forms.system import OrderSettingsFormPart
from shuup.admin.toolbar import PostActionButton, Toolbar
from shuup.utils.form_group import FormGroup


class SystemSettingsView(FormPartsViewMixin, FormView):
    form_class = None
    template_name = "shuup/admin/settings/edit.jinja"
    base_form_part_classes = [OrderSettingsFormPart]

    @atomic
    def form_valid(self, form):
        return self.save_form_parts(form)

    def get_form(self, form_class=None):
        kwargs = self.get_form_kwargs()
        kwargs["initial"] = dict(self.request.GET.items())
        fg = FormGroup(**kwargs)
        form_parts = self.get_form_parts(None)
        for form_part in form_parts:
            for form_def in form_part.get_form_defs():
                fg.form_defs[form_def.name] = form_def
        fg.instantiate_forms()
        return fg

    def save_form_parts(self, form):
        has_changed = False
        form_parts = self.get_form_parts(None)
        for form_part in form_parts:
            saved_form = form[form_part.name]
            if saved_form.has_changed():
                has_changed = form_part.save(saved_form)

        if has_changed:
            messages.success(self.request, _("Changes saved."))
        else:
            messages.info(self.request, _("No changes detected."))
        return redirect("shuup_admin:settings.list")

    def get_context_data(self, **kwargs):
        context = super(SystemSettingsView, self).get_context_data(**kwargs)
        context["toolbar"] = Toolbar(
            [
                PostActionButton(
                    icon="fa fa-check-circle",
                    form_id="settings_form",
                    text=_("Save system settings"),
                    extra_css_class="btn-success",
                )
            ],
            view=self,
        )
        return context


class ResetCacheView(View):

    def get(self, request, *args, **kwargs):
        if request.user.is_superuser:
            call_command('clear_cache')
        return HttpResponseRedirect(reverse('dashboard'))


class ResetElasticSearchView(View):

    def get(self, request, *args, **kwargs):
        if request.user.is_superuser:
            call_command('recreate_elasticsearch')
        return HttpResponseRedirect(reverse('dashboard'))
