# Copyright (c) 2019 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import functools
import json

import jsonschema
import six
import testtools

DEFAULT_DATA_JSON_PATH = 'default_data.json'

IGNORED_COMPANIES = ['*robots', 'April', 'Chelsio Communications',
                     'CloudRunner.io', 'Datera', 'Facebook',
                     'Fermi National Accelerator Laboratory', 'Github',
                     'H3C',
                     'Huaxin Hospital, First Hospital of Tsinghua University',
                     'InfluxDB', 'Kickstarter', 'National Security Agency',
                     'OpenStack Foundation', 'OpenStack Korea User Group',
                     'ProphetStor', 'SVA System Vertrieb Alexander GmbH',
                     'Sencha', 'Stark & Wayne LLC', 'Styra',
                     'Suranee University of Technology',
                     'The Linux Foundation', 'UTi Worldwide', 'Undead Labs',
                     'Violin Memory', 'docCloud', 'npm']


def dict_raise_on_duplicates(ordered_pairs):
    """Reject duplicate keys."""
    d = {}
    for k, v in ordered_pairs:
        if k in d:
            raise ValueError("duplicate key: %s (value: %s)" % (k, v))
        else:
            d[k] = v
    return d


class TestConfigFiles(testtools.TestCase):

    def _read_raw_file(self, file_name):
        if six.PY3:
            opener = functools.partial(open, encoding='utf8')
        else:
            opener = open
        with opener(file_name, 'r') as content_file:
            return content_file.read()

    def _read_file(self, file_name):
        return json.loads(self._read_raw_file(file_name))

    def _verify_ordering(self, array, key, msg):
        comparator = lambda x, y: (x > y) - (x < y)

        diff_msg = ''
        for i in range(len(array) - 1):
            if comparator(key(array[i]), key(array[i + 1])) > 0:
                diff_msg = ('Order fails at index %(index)s, '
                            'elements:\n%(first)s:\n%(second)s' %
                            {'index': i, 'first': array[i],
                             'second': array[i + 1]})
                break
        if diff_msg:
            self.fail(msg + '\n' + diff_msg)

    def _assert_not_in(self, field, collection, message):
        # We do not use self.assertNotIn because collection is extremely big.
        # assertNotIn mismatch error message is unreadable with it
        self.assertEqual(False, field in collection, message=message)

    def test_default_data_duplicate_keys(self):
        try:
            json.loads(self._read_raw_file(DEFAULT_DATA_JSON_PATH),
                       object_pairs_hook=dict_raise_on_duplicates)
        except ValueError as ve:
            self.fail(ve)

    def test_default_data_schema_conformance(self):
        default_data = self._read_file(DEFAULT_DATA_JSON_PATH)
        try:
            jsonschema.validate(default_data, self._read_file('schema.json'))
        except jsonschema.ValidationError as e:
            self.fail(e)

    def test_companies_in_alphabetical_order(self):
        companies = self._read_file(DEFAULT_DATA_JSON_PATH)['companies']
        self._verify_ordering(
            companies, key=lambda x: x['domains'][0],
            msg='List of companies should be ordered by the first domain')

    def test_users_in_alphabetical_order(self):
        users = self._read_file(DEFAULT_DATA_JSON_PATH)['users']
        self._verify_ordering(
            users,
            key=lambda x: (x.get('launchpad_id') or x.get('github_id') or ''),
            msg='List of users should be ordered by launchpad id or ldap id '
                'or github id')

    def _check_collision(self, storage, user, field, field_name):
        self.assertNotIn(
            field, storage,
            'Duplicate %s %s, collision between: %s and %s'
            % (field_name, field, storage[field], user))
        storage[field] = user

    def test_users_unique_profiles(self):
        users = self._read_file(DEFAULT_DATA_JSON_PATH)['users']
        storage = {}
        for user in users:
            if user.get('launchpad_id'):
                field = user['launchpad_id']
                self._assert_not_in(
                    field, storage,
                    message='Duplicate launchpad_id %s, collision between:\n%s\nand\n%s'
                    % (field, storage.get(field), user))
                storage[field] = user

            if user.get('gerrit_id'):
                field = user['gerrit_id']
                self._assert_not_in(
                    ('gerrit:%s' % field), storage,
                    message='Duplicate gerrit_id %s, collision between:\n%s\nand\n%s'
                    % (field, storage.get(field), user))
                storage['gerrit:%s' % field] = user

            for email in user['emails']:
                self._assert_not_in(
                    email, storage,
                    message='Duplicate email %s, collision between:\n%s\nand\n%s'
                    % (email, storage.get(email), user))
                storage[email] = user

    def test_default_data_whitespace_issues(self):
        data = self._read_raw_file(DEFAULT_DATA_JSON_PATH)
        line_n = 1
        for line in data.split('\n'):
            msg = 'Whitespace issue in "%s", line %s: ' % (line, line_n)
            self.assertEqual(-1, line.find('\t'),
                             message=msg + 'tab character')
            self.assertEqual(line.rstrip(), line,
                             message=msg + 'trailing spaces')
            line_n += 1

    def test_default_data_user_companies(self):
        data = self._read_file(DEFAULT_DATA_JSON_PATH)
        users = data['users']
        companies = data['companies']
        company_names = []
        for company in companies:
            company_names.append(company['company_name'])
            for alias in company.get('aliases', []):
                company_names.append(alias)

        for user in users:
            for company in user['companies']:
                if not company['company_name'] in IGNORED_COMPANIES:
                    error_msg = ('Company "%s" is unknown. Please add it into'
                                 ' the list of companies in default_data.json '
                                 'file' % company['company_name'])
                    self.assertIn(company['company_name'], company_names,
                                  error_msg)

    def test_default_data_users_one_open_interval(self):
        users = self._read_file(DEFAULT_DATA_JSON_PATH)['users']
        for user in users:
            ops = set([])
            for c in user['companies']:
                if not c['end_date']:
                    ops.add(c['company_name'])

            self.assertLessEqual(
                len(ops), 1, msg='More than 1 company is specified '
                                 'as current: %s. Please keep '
                                 'only one' % ', '.join(ops))
