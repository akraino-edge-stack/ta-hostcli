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
import sys
import time

from cliff.commandmanager import CommandManager

from keystoneauth1.exceptions.http import BadGateway

from osc_lib import shell
from osc_lib import utils
from osc_lib import clientmanager
from osc_lib.api import auth
from osc_lib.cli import client_config as cloud_config

from openstackclient.i18n import _

from hostcli import resthandler


class HOSTCLI(shell.OpenStackShell):
    LOG = logging.getLogger(__name__)
    def __init__(self):
        super(HOSTCLI, self).__init__(
            description='HOSTCLI',
            version='0.1',
            command_manager=CommandManager('hostcli.commands')
            )
        self.failure_count = 30

    def build_option_parser(self, description, version):
        parser = super(HOSTCLI, self).build_option_parser(
            description,
            version)
        parser = auth.build_auth_plugins_option_parser(parser)
        #HACK: Add the api version so that we wont use version 2
        #This part comes from openstack module so it cannot be imported
        parser.add_argument('--os-identity-api-version',
                            metavar='<identity-api-version>',
                            default=utils.env('OS_IDENTITY_API_VERSION'),
                            help=_('Identity API version, default=%s '
                                   '(Env: OS_IDENTITY_API_VERSION)') % 3,
                           )

        return parser

    def initialize_app(self, argv):
        self.LOG.debug('initialize_app')
        super(HOSTCLI, self).initialize_app(argv)
        try:
            self.cloud_config = cloud_config.OSC_Config(
                override_defaults={
                    'interface': None,
                    'auth_type': self._auth_type,
                },
                pw_func=shell.prompt_for_password,
            )
        except (IOError, OSError):
            self.log.critical("Could not read clouds.yaml configuration file")
            self.print_help_if_requested()
            raise
        if not self.options.debug:
            self.options.debug = None

        setattr(clientmanager.ClientManager,
                resthandler.API_NAME,
                clientmanager.ClientCache(getattr(resthandler, 'make_instance')))
        self.client_manager = clientmanager.ClientManager(
            cli_options=self.cloud,
            api_version=self.api_version,
            pw_func=shell.prompt_for_password,
        )

    def _final_defaults(self):

        super(HOSTCLI, self)._final_defaults()
        # Set the default plugin to token_endpoint if url and token are given
        if self.options.url and self.options.token:
            # Use service token authentication
            self._auth_type = 'token_endpoint'
        else:
            self._auth_type = 'password'


    def prepare_to_run_command(self, cmd):
        self.LOG.debug('prepare_to_run_command %s', cmd.__class__.__name__)
        error = Exception()
        for count in range(0, self.failure_count):
            try:
                return super(HOSTCLI, self).prepare_to_run_command(cmd)
            except BadGateway as error:
                self.LOG.debug('Got BadGateway %s, counter %d', str(error), count)
                time.sleep(2)
        raise error

    def clean_up(self, cmd, result, err):
        self.LOG.debug('clean_up %s', cmd.__class__.__name__)
        if err:
            self.LOG.debug('got an error: %s', err)

def main(argv=sys.argv[1:]):
    hostcli = HOSTCLI()
    return hostcli.run(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
