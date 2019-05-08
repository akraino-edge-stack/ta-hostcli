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

import sys
import re
from datetime import datetime
from dateutil import tz
from cliff.show import ShowOne
from cliff.lister import Lister
from cliff.command import Command


DEFAULT = 'default'
ALL = 'all'
DISPLAY = 'display'
HELP = 'help'
SORT = 'sort'
DATA = 'data'
CHOICES = 'choices'     # allowed values for an argument (coming from argparse 'choices' facility)
VALUES = 'values'       # allowed values for an argument, even if the argument supports adding multiple instances
FIELDS = 'fields'       # filtered list of expected columns in the response (translates to argparse's 'columns' of)
COLUMNS = 'columns'     # same as fields
DETAILED = 'detailed'   # Makes the command to show all accessible details of the requsted objects.
                        # Should not be positional (so should not be the first in the arguments list)
TIME = 'time'
UTC = 'utc'


class HelperBase(object):
    """Helper base class validating arguments and doing the business logic (send query and receive and process table in response)"""
    def __init__(self):
        self.operation = 'get'
        self.endpoint = ''
        self.arguments = []
        self.columns = []
        self.detailed = []
        self.fieldmap = {}
        self.message = ''
        self.no_positional = False
        self.mandatory_positional = False
        self.usebody = False
        self.resource_prefix = ''
        self.default_sort = None
        self.positional_count = 1 # how many mandatory arguments are

    def get_parser_with_arguments(self, parser):
        args = self.arguments[:]
        if self.no_positional is False:
            for i in range (0, self.positional_count):
                first = args.pop(0)
                parser.add_argument(first,
                                    metavar=first.upper(),
                                    nargs=None if self.mandatory_positional else '?',
                                    default=self.fieldmap[first].get(DEFAULT, ALL),
                                    help=self.fieldmap[first][HELP])
        for e in args:
            # This is very similar to 'choices' facility of argparse, however it allows multiple choices combined...
            multichoices = ''
            default = self.fieldmap[e].get(DEFAULT, ALL)
            if e in [DETAILED, UTC]:
                parser.add_argument('--%s' % e, dest=e,  action='store_true', help=self.fieldmap[e][HELP])
                continue
            if e == SORT:
                # ...and is needed here to list the allowed arguments in the help
                multichoices = ' [%s]' % ','.join([self.fieldmap[i][DISPLAY] for i in self.columns])
                if self.default_sort:
                    default = '%s:%s' % (self.fieldmap[self.default_sort[0]][DISPLAY], self.default_sort[1])
            elif VALUES in self.fieldmap[e]:
                multichoices = ' [%s]' % ','.join(self.fieldmap[e][VALUES])
            parser.add_argument('--%s' % e,
                                dest=e,
                                metavar=e.upper(),
                                required=False,
                                default=default,
                                type=str,
                                choices=self.fieldmap[e].get(CHOICES, None),
                                help=self.fieldmap[e][HELP] + multichoices)
        return parser

    def send_receive(self, app, parsed_args):
        parsed_args = self.validate_parameters(parsed_args)
        if parsed_args.fields:
            self.arguments.append(FIELDS)
        arguments = {k: v for k, v in sorted(vars(parsed_args).items()) if k in self.arguments and
                                                                           k != COLUMNS and
                                                                           v != ALL and
                                                                           v is not False}
        if not arguments:
            arguments = None
        req = app.client_manager.resthandler
        response = req._operation(self.operation,
                                  '%s%s' %(self.resource_prefix, self.endpoint),
                                  arguments if self.usebody else None,
                                  None if self.usebody else arguments,
                                  False)
        if not response.ok:
            raise Exception('Request response is not OK (%s)' % response.reason)
        result = response.json()
        if 0 != result['code']:
            raise Exception(result['description'])
        return result

    def validate_parameters(self, args):
        if 'starttime' in self.arguments:
            args.starttime = HelperBase.convert_timezone_to_utc(args.starttime)
        if 'endtime' in self.arguments:
            args.endtime = HelperBase.convert_timezone_to_utc(args.endtime)
        args.fields = ALL
        if hasattr(args, COLUMNS):
            args.columns = list(set(j for i in args.columns for j in i.split(',')))
            if args.columns:
                args.fields = ','.join([self.get_key_by_value(k) for k in sorted(args.columns)])
        for a in self.arguments:
            argval = getattr(args, a)
            if isinstance(argval, str):
                for p in argval.split(','):
                    if argval != ALL and VALUES in self.fieldmap[a] and p not in self.fieldmap[a][VALUES]:
                        raise Exception('%s is not supported by %s argument' % (p, a))
        return args

    @staticmethod
    def validate_datetime(dt):
        if dt == ALL:
            return dt
        formats = ['%Y-%m-%dT%H:%M:%S.%fZ',
                   '%Y-%m-%dT%H:%M:%SZ',
                   '%Y-%m-%dT%H:%MZ',
                   '%Y-%m-%dZ']
        for f in formats:
            try:
                retval = dt
                if 'Z' != retval[-1]:
                    retval += 'Z'
                retval = datetime.strptime(retval, f).__str__()
                retval = '%s.000' % retval if len(retval) <= 19 else retval[:-3]
                return retval.replace(' ', 'T') + 'Z'
            except ValueError:
                pass
        raise Exception('Datetime format (%s) is not supported' % dt)

    @staticmethod
    def convert_utc_to_timezone(timestr):
        timestr = timestr.replace('Z', '')
        # max resolution for strptime is microsec
        if len(timestr) > 26:
            timestr = timestr[:26]
        from_zone = tz.tzutc()
        to_zone = tz.tzlocal()
        utc = datetime.strptime(HelperBase.validate_datetime(timestr + 'Z'), '%Y-%m-%dT%H:%M:%S.%fZ')
        utc = utc.replace(tzinfo=from_zone)
        ret = str(utc.astimezone(to_zone))
        return ret[:23] if '.' in ret else ret[:19] + '.000'

    @staticmethod
    def convert_timezone_to_utc(timestr):
        if timestr[-1] == 'Z' or timestr == ALL:
            # we assume that UTC will always have a Z character at the end
            return timestr
        formats = ['%Y-%m-%dT%H:%M:%S.%f',
                   '%Y-%m-%dT%H:%M:%S',
                   '%Y-%m-%dT%H:%M',
                   '%Y-%m-%d']
        origstr = timestr
        timestr = timestr.replace(' ', 'T')
        if len(timestr) > 26:
            timestr = timestr[:26]
        from_zone = tz.tzlocal()
        to_zone = tz.tzutc()
        for f in formats:
            try:
                localtime = datetime.strptime(timestr, f)
                localtime = localtime.replace(tzinfo=from_zone)
                ret = str(localtime.astimezone(to_zone))
                retval = ret[:23] if '.' in ret else ret[:19] + '.000'
                return retval.replace(' ', 'T') + 'Z'
            except ValueError:
                pass
        raise Exception('Datetime format (%s) is not supported' % origstr)

    def filter_columns(self, args):
        if getattr(args, DETAILED, False) is True:
            self.columns.extend(self.detailed)
        if ALL != args.fields:
            for i in range(len(self.columns) - 1, -1, -1):
                if self.columns[i] not in args.fields:
                    del self.columns[i]
        return [self.fieldmap[f][DISPLAY] for f in self.columns]

    def get_key_by_value(self, val):
        for k, v in self.fieldmap.items():
            if DISPLAY in v and val == v[DISPLAY]:
                return k
        raise Exception('No column named %s' % val)

    def get_sorted_keys(self, parsed_args, data):
        keylist = data.keys()
        if hasattr(parsed_args, SORT):
            sortexp = parsed_args.sort
            if sortexp != ALL:
                # The next one generates two lists, one with the field names (to be sorted),
                # and another with the directions. True if reversed, false otherwise
                # also if no direction is added for a field, then it adds an ':asc' by default.
                skeys, sdir = zip(*[(self.get_key_by_value(x[0]), False if 'asc' in x[1].lower() else True)
                                    for x in (('%s:asc' % x).split(":") for x in reversed(sortexp.split(',')))])
                for k, d in zip(skeys, sdir):
                    keylist.sort(key=lambda x: data[x][k], reverse=d)
        return keylist

    @staticmethod
    def construct_message(text, result):
        p = re.compile('\#\#(\w+)')
        while True:
            m = p.search(text)
            if not m:
                break
            text = p.sub(result[DATA][m.group(1)], text, 1)
        return '%s\n' % text


class ListerHelper(Lister, HelperBase):
    """Helper class for Lister"""
    def __init__(self, app, app_args, cmd_name=None):
        Lister.__init__(self, app, app_args, cmd_name)
        HelperBase.__init__(self)

    def get_parser(self, prog_name):
        parser = super(ListerHelper, self).get_parser(prog_name)
        return self.get_parser_with_arguments(parser)

    def take_action(self, parsed_args):
        try:
            result = self.send_receive(self.app, parsed_args)
            header = self.filter_columns(parsed_args)
            data = []
            for k in self.get_sorted_keys(parsed_args, result[DATA]):
                row = [HelperBase.convert_utc_to_timezone(result[DATA][k][i])
                       if not getattr(parsed_args, UTC, False) and i == TIME
                       else result[DATA][k][i] for i in self.columns]
                data.append(row)
            if self.message:
                self.app.stdout.write(self.message + '\n')
            return header, data
        except Exception as exp:
            self.app.stderr.write('Failed with error:\n%s\n' % str(exp))
            sys.exit(1)


class ShowOneHelper(ShowOne, HelperBase):
    """Helper class for ShowOne"""
    def __init__(self, app, app_args, cmd_name=None):
        ShowOne.__init__(self, app, app_args, cmd_name)
        HelperBase.__init__(self)

    def get_parser(self, prog_name):
        parser = super(ShowOneHelper, self).get_parser(prog_name)
        return self.get_parser_with_arguments(parser)

    def take_action(self, parsed_args):
        try:
            result = self.send_receive(self.app, parsed_args)
            header = self.filter_columns(parsed_args)
            sorted_keys = self.get_sorted_keys(parsed_args, result[DATA])
            if self.message:
                self.app.stdout.write(self.message + '\n')
            for k in sorted_keys:
                data = [HelperBase.convert_utc_to_timezone(result[DATA][k][i])
                        if not getattr(parsed_args, UTC, False) and i == TIME
                        else result[DATA][k][i] for i in self.columns]
                if k != sorted_keys[-1]:
                    self.formatter.emit_one(header, data, self.app.stdout, parsed_args)
                    self.app.stdout.write('\n')
            return header, data
        except Exception as exp:
            self.app.stderr.write('Failed with error:\n%s\n' % str(exp))
            sys.exit(1)


class CommandHelper(Command, HelperBase):
    """Helper class for Command"""
    def __init__(self, app, app_args, cmd_name=None):
        Command.__init__(self, app, app_args, cmd_name)
        HelperBase.__init__(self)

    def get_parser(self, prog_name):
        parser = super(CommandHelper, self).get_parser(prog_name)
        return self.get_parser_with_arguments(parser)

    def take_action(self, parsed_args):
        try:
            result = self.send_receive(self.app, parsed_args)
            if self.message:
                self.app.stdout.write(HelperBase.construct_message(self.message, result))
        except Exception as exp:
            self.app.stderr.write('Failed with error:\n%s\n' % str(exp))
            sys.exit(1)
