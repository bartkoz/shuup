# -*- coding: utf-8 -*-
# This file is part of Shuup.
#
# Copyright (c) 2012-2021, Shuup Commerce Inc. All rights reserved.
#
# This source code is licensed under the OSL-3.0 license found in the
# LICENSE file in the root directory of this source tree.
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _

from shuup.admin.base import AdminModule, MenuEntry
from shuup.admin.menu import SETTINGS_MENU_CATEGORY
from shuup.admin.utils.urls import admin_url


class SettingsModule(AdminModule):
    name = _("System Settings")
    breadcrumbs_menu_entry = MenuEntry(name, url="shuup_admin:settings.list")

    def get_urls(self):
        return [admin_url("^settings/$", "shuup.admin.modules.settings.views.SystemSettingsView", name="settings.list"),
                admin_url("^settings/reset_cache$", "shuup.admin.modules.settings.views.ResetCacheView", name="settings.reset_cache"),
                admin_url("^settings/reset_elasticsearch$", "shuup.admin.modules.settings.views.ResetElasticSearchView", name="settings.reset_elastic")]

    def get_menu_entries(self, request):
        return [
            MenuEntry(
                text=self.name,
                icon="fa fa-home",
                url="shuup_admin:settings.list",
                category=SETTINGS_MENU_CATEGORY,
                ordering=4,
            ),
            MenuEntry(
                text='Reset cache',
                icon="fa fa-home",
                url="shuup_admin:settings.reset_cache",
                category=SETTINGS_MENU_CATEGORY,
                ordering=99999,
            ),
            MenuEntry(
                text='Reset ES',
                icon="fa fa-home",
                url="shuup_admin:settings.reset_elastic",
                category=SETTINGS_MENU_CATEGORY,
                ordering=99999,
            )
        ]
