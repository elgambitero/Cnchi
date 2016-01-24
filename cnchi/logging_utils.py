#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# logging_utils.py
#
# Copyright © 2015-2016 Antergos
#
# This file is part of Cnchi.
#
# Cnchi is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# Cnchi is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# The following additional terms are in effect as per Section 7 of the license:
#
# The preservation of all legal notices and author attributions in
# the material or in the Appropriate Legal Notices displayed
# by works containing it is required.
#
# You should have received a copy of the GNU General Public License
# along with Cnchi; If not, see <http://www.gnu.org/licenses/>.

import logging
import uuid
import requests
import json
import os
from info import CNCHI_VERSION, CNCHI_RELEASE_STAGE


class Singleton(logging.Filter):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Singleton, cls).__new__(cls, *args)
            cls._instance.id = None
            cls._instance.install = None
            cls._instance.api_key = None
            cls._instance.have_install_id = False
            cls._instance.after_location_screen = False
        return cls._instance


class ContextFilter(Singleton):
    def __init__(self):
        super().__init__()

        if self.api_key is None:
            self.api_key = self.get_bugsnag_api()

    def filter(self, record):
        uid = str(uuid.uuid1()).split("-")
        record.uuid = uid[3] + "-" + uid[1] + "-" + uid[2] + "-" + uid[4]
        record.id = self.id
        record.install = self.install
        return True

    def get_and_save_install_id(self, is_location_screen=False):
        if self.have_install_id:
            return

        if is_location_screen:
            self.after_location_screen = True

        if 'development' == CNCHI_RELEASE_STAGE:
            self.install = 'development'
            self.id = '0.0.0.0'
            self.have_install_id = True
            return

        info = None
        url = self.get_url_for_id_request()
        headers = {'X-Cnchi-Installer': CNCHI_VERSION}

        try:
            r = requests.get(url, headers=headers)
            info = json.loads(r.json())
        except Exception as err:
            logger = logging.getLogger()
            msg = "Unable to get an Id for this installation. Error: {0}".format(err.args)
            logger.error(msg)
            return

        try:
            self.id = info['ip']
            self.install = info['id']
            self.have_install_id = True
        except (TypeError, KeyError):
            self.have_install_id = False

    @staticmethod
    def get_bugsnag_api():
        config_path = '/etc/raven.conf'
        bugsnag_api = None

        if os.path.exists(config_path):
            with open(config_path) as bugsnag_conf:
                bugsnag_api = bugsnag_conf.readline().strip()

        return bugsnag_api

    def get_url_for_id_request(self):
        build_server = None
        if self.api_key and 'development' != CNCHI_RELEASE_STAGE:
            build_srv = ['http://build', 'antergos', 'com']
            build_srv_query = ['/hook', 'cnchi=', self.api_key]
            build_server = '.'.join(build_srv) + '?'.join(build_srv_query)
        return build_server

    def bugsnag_before_notify_callback(self, notification=None):
        if notification is not None:
            if self.after_location_screen and not self.have_install_id:
                self.get_and_save_install_id()

            notification.user = {
                "id": self.id,
                "name": "Antergos User",
                "install_id": self.install}
            return notification

    def send_install_result(self, result):
        try:
            build_server = self.get_url_for_id_request()
            if build_server:
                url = "{0}&install_id={1}&result={2}"
                url = url.format(build_server, self.install, result)
                headers = {'X-Cnchi-Installer': CNCHI_VERSION}
                r = requests.get(url, headers=headers)
                res = json.loads(r.json())
        except Exception as ex:
            logger = logging.getLogger()
            template = "Can't send install result. An exception of type {0} occured. Arguments:\n{1!r}"
            message = template.format(type(ex).__name__, ex.args)
            logger.error(message)
