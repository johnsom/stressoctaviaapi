# Copyright 2017 Rackspace, US Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import functools
import timeit

from oslo_config import cfg
from oslo_log import log as logging
import requests
from taskflow import task

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class BaseOctaviaTask(task.Task):
    """Base task to load code common to the tasks."""

    def __init__(self, **kwargs):
        super(BaseOctaviaTask, self).__init__(**kwargs)
        self.get = functools.partial(self._request, 'GET')
        self.post = functools.partial(self._request, 'POST')
        self.put = functools.partial(self._request, 'PUT')
        self.delete = functools.partial(self._request, 'DELETE')

    def _request(self, method, url, token=None, data=None,
                params=None):
        headers = {
            'Content-type': 'application/json',
            'User-Agent': 'Stress_Octavia_API',
            'X-Auth-Token': token
        }

        url = '{}/{}'.format(CONF.test_params.api_endpoint, str(url))
        LOG.debug("url = %s", url)
        LOG.debug("data = %s", data)
        LOG.debug("params = %s", str(params))

        retry = True
        retry_count = 0
        while retry:
            r = requests.request(method, url, data=data,
                                 params=params, headers=headers)
            LOG.debug("Octavia Response Code: {0}".format(r.status_code))
            LOG.debug("Octavia Response Body: {0}".format(r.content))
            LOG.debug("Octavia Response Headers: {0}".format(r.headers))
            if r.status_code > 199 and r.status_code < 300:
                retry = False
            elif r.status_code == 409 or r.status_code == 503:
                LOG.debug('{0} to {1} returned {2}. '
                          'Retrying.'.format(method, url, r.status_code))
                retry_count += 1
            else:
                LOG.error('{0} to {1} returned {2} with '
                          'message: {3}'.format(method, url,
                                                r.status_code, r.content))
                raise Exception('{0} to {1} failed. Aborting.'.format(
                    method, url))
        if retry_count > 0:
            LOG.info('{0} to {1} retried {2} '
                     'times.'.format(method, url, retry_count))
        return r


class CreateLoadBalancer(BaseOctaviaTask):
    """Task to create a load balancer."""

    def execute(self, token, name):

        LOG.info('{0} - Creating load balancer: {1}'.format(self.name, name))
        data=('{{"loadbalancer": {{"vip_subnet_id": "{subnet}",'
              '"name": "{name}"}}}}'.format(
            subnet=CONF.test_params.vip_subnet_id, name=name))

        r = self.post('v2.0/lbaas/loadbalancers', token=token, data=data)

        return r.json()['loadbalancer']['id']


class WaitForActive(BaseOctaviaTask):
    """Task to wait for a load balancer to go active."""

    def execute(self, token, lb_id):

        start_time = timeit.default_timer()
        for i in range(CONF.test_params.retries_check_active):
            r = self.get('v2.0/lbaas/loadbalancers/{0}'.format(lb_id),
                     token=token)
            status = r.json()['loadbalancer']['provisioning_status']
            if status == 'ACTIVE':
                LOG.info('{0} - Queried API {1} times before LB ACTIVE'.format(
                    self.name, i))
                LOG.info('{0} - Elapsed time: {1}'.format(self.name,
                    timeit.default_timer() - start_time))
                return
            elif status == 'ERROR':
                LOG.error('LB went into ERROR, aborting')
                raise Exception('ABORT: LB went into ERROR')
        LOG.error('LB wait for ACTIVE {} retries expired, Aborting.'.format(i))
        raise Exception('LB did not go ACTIVE in {} tries, '
                        'Aborting.'.format(i))


class CreateListener(BaseOctaviaTask):
    """Task to create a listener."""

    def execute(self, token, name, lb_id, port):

        LOG.info('{0} - Creating listener: {1}'.format(self.name, name))
        data=('{{"listener": {{"protocol": "HTTP", "protocol_port": {port},'
              '"name": "{name}", "loadbalancer_id": "{lb_id}"}}}}'.format(
            subnet=CONF.test_params.vip_subnet_id, name=name, lb_id=lb_id,
            port=port))

        r = self.post('v2.0/lbaas/listeners', token=token, data=data)

        return r.json()['listener']['id']


class CreatePool(BaseOctaviaTask):
    """Task to create a pool."""

#    def execute(self, token, name, lb_id):
    def execute(self, token, name, listener_id):

        LOG.info('{0} - Creating pool: {1}'.format(self.name, name))
#        data=('{{"pool": {{"loadbalancer_id": "{lb_id}",'
        data=('{{"pool": {{"listener_id": "{listener_id}",'
              '"lb_algorithm": "ROUND_ROBIN", "protocol": "HTTP",'
              '"name": "{name}"}}}}'.format(
#            lb_id=lb_id, name=name))
            listener_id=listener_id, name=name))

        r = self.post('v2.0/lbaas/pools', token=token, data=data)

        return r.json()['pool']['id']


class CreateHealthMonitor(BaseOctaviaTask):
    """Task to create a health monitor."""

    def execute(self, token, name, pool_id):

        LOG.info('{0} - Creating health monitor: {1}'.format(self.name, name))
        data=('{{"healthmonitor": {{"pool_id": "{pool}",'
              '"delay": 5, "max_retries": 1, "timeout": 1, "type": "PING",'
              '"name": "{name}"}}}}'.format(
            pool=pool_id, name=name))

        r = self.post('v2.0/lbaas/healthmonitors', token=token, data=data)

        return r.json()['healthmonitor']['id']


class CreateMember(BaseOctaviaTask):
    """Task to create a member."""

    def execute(self, token, name, pool_id, address, port):

        LOG.info('{0} - Creating member: {1}'.format(self.name, name))
        data=('{{"member": {{"address": "{address}", "protocol_port": {port},'
              '"subnet_id": "{subnet}",'
              '"name": "{name}"}}}}'.format(
                  pool=pool_id, name=name, address=address, port=port,
                  subnet=CONF.test_params.member_subnet_id))

        r = self.post('v2.0/lbaas/pools/{}/members'.format(pool_id),
                      token=token, data=data)

        return r.json()['member']['id']
