# (c) 2016, Red Hat Inc.
#
# ansible-inventory is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ansible-inventory is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

########################################################
# ansible-inventory parses Ansible inventory and vars
# files, and outputs them as JSON in a Tower-compatible
# format.

import cmd
import getpass
import os
import sys

from ansible import constants as C
from ansible.cli import CLI
from ansible.errors import AnsibleError
from ansible.inventory import Inventory
from ansible.module_utils._text import to_text
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class InventoryCLI(CLI, cmd.Cmd):

    modules = []

    def __init__(self, args):

        super(InventoryCLI, self).__init__(args)

        self.groups = []
        self.hosts = []
        self.pattern = None
        self.variable_manager = None
        self.loader = None
        self.passwords = dict()

        self.modules = None
        cmd.Cmd.__init__(self)

    def parse(self):
        self.parser = CLI.base_parser(
            usage='%prog <host-pattern> [options]',
        )
        self.parser.add_option('-i', '--inventory-file', dest='inventory',
                          help="specify inventory host path (default=%s) or comma separated host list." % C.DEFAULT_HOST_LIST,
                          default=C.DEFAULT_HOST_LIST, action="callback", callback=CLI.expand_tilde, type=str)
        self.parser.add_option('--ask-vault-pass', default=C.DEFAULT_ASK_VAULT_PASS, dest='ask_vault_pass',
                          action='store_true',
                          help='ask for vault password')
        self.parser.add_option('--vault-password-file', default=C.DEFAULT_VAULT_PASSWORD_FILE, dest='vault_password_file',
                          help="vault password file", action="callback", callback=CLI.expand_tilde, type=str)

        super(InventoryCLI, self).parse()

        display.verbosity = self.options.verbosity

    def run(self):

        super(InventoryCLI, self).run()

        # hosts
        if len(self.args) != 1:
            self.pattern = 'all'
        else:
            self.pattern = self.args[0]

        self.loader = DataLoader()

        if self.options.vault_password_file:
            # read vault_pass from a file
            vault_pass = CLI.read_vault_password_file(self.options.vault_password_file, loader=self.loader)
            self.loader.set_vault_password(vault_pass)
        elif self.options.ask_vault_pass:
            vault_pass = self.ask_vault_passwords()[0]
            self.loader.set_vault_password(vault_pass)

        self.variable_manager = VariableManager()
        self.inventory = Inventory(loader=self.loader, variable_manager=self.variable_manager, host_list=self.options.inventory)
        self.variable_manager.set_inventory(self.inventory)

        hosts = self.inventory.list_hosts(self.pattern)
        if len(hosts) == 0:
            # Empty inventory
            display.warning("provided hosts list is empty, only localhost is available")

        results = {}
        results['_meta'] = {}
        results['_meta']['hostvars'] = {}

        for host in hosts:
            results['_meta']['hostvars'][host] = host.vars
            for hg in [x.name for x in host.groups]:
                if hg not in results:
                    results[hg] = {}
                    results[hg]['hosts'] = []
                    results[hg]['vars'] = self.inventory.groups[hg].vars
                if host not in results[hg]['hosts']:
                    results[hg]['hosts'].append(host)

        from pprint import pprint
        pprint(results)