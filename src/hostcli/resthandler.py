# Copyright 2019 Nokia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import logging
import requests
import os

API_NAME = 'resthandler'
LOG = logging.getLogger(__name__)

def make_instance(instance):
    return RestRequest(instance)

class RestRequest(object):
    """ RestRequest object
        This module can be used in the context of hostcli rest implementations.
        Example usage is:
            def take_action(self, parsed_args):
                req = self.app.client_manager.resthandler
                ret = req.get("has/v1/cluster", decode_json=True)
                status = ret['data']
                columns = ('admin-state',
                           'running-state',
                           'role'
                          )
                data = (status['admin-state'],
                        status['running-state'],
                        status['role']
                        )
                return (columns, data)
        Why:
            This module will fill the needed information for authentication.
            The authentication will be based on keystone.
        Notes:
            The object will fill the prefix to the request. So it's not mandatory
            to write it. This information will be populated from the endpoint of rest frame.
    """
    def __init__(self, app_instance):
        self.instance = app_instance
        if self.instance._auth_required:
            self.token = self.instance.auth_ref.auth_token
            self.auth_ref = self.instance.auth_ref
            self.url = self.auth_ref.service_catalog.url_for(service_type="restfulapi",
                                                             service_name="restfulframework",
                                                             interface=self.instance.interface)
        else:
            if 'OS_REST_URL' in os.environ:
                self.url = os.environ['OS_REST_URL']
            else:
                raise Exception("OS_REST_URL environment variable missing")

    def get(self, url, data=None, params=None, decode_json=True):
        return self._operation("get", url, data=data, params=params, decode_json=decode_json)

    def post(self, url, data=None, params=None, decode_json=True):
        return self._operation("post", url, data=data, params=params, decode_json=decode_json)

    def put(self, url, data=None, params=None, decode_json=True):
        return self._operation("put", url, data=data, params=params, decode_json=decode_json)

    def patch(self, url, data=None, params=None, decode_json=True):
        return self._operation("patch", url, data=data, params=params, decode_json=decode_json)

    def delete(self, url, data=None, params=None, decode_json=True):
        return self._operation("delete", url, data=data, params=params, decode_json=decode_json)

    def _operation(self, oper, url, data=None, params=None, decode_json=True):

        operation = getattr(requests, oper, None)

        if not operation:
            raise NameError("Operation %s not found" % oper)

        if not url.startswith("http"):
            url = self.url + '/' + url

        LOG.debug("Working with url %s" % url)

        # Disable request debug logs
        logging.getLogger("requests").setLevel(logging.WARNING)

        # HACK:Check if the authentication will expire and if so then renew it
        if self.instance._auth_required and self.auth_ref.will_expire_soon():
            LOG.debug("Session will expire soon... Renewing token")
            self.instance._auth_setup_completed = False
            self.instance._auth_ref = None
            self.token = self.instance.auth_ref.auth_token
        else:
            LOG.debug("Session is solid. Using existing token.")

        # Add security headers
        arguments = {}
        headers = {'User-Agent': 'HostCli'}

        if self.instance._auth_required:
            headers.update({'X-Auth-Token': self.token})

        if data:
            if isinstance(data, dict):
                arguments["json"] = data
                headers["Content-Type"] = "application/json"
            else:
                arguments["data"] = data
                headers["Content-Type"] = "text/plain"

        arguments["headers"] = headers

        if params:
            arguments["params"] = params

        ret = operation(url, **arguments)

        if decode_json:
            ret.raise_for_status()
            try:
                return ret.json()
            except ValueError:
                return {}
        else:
            return ret
