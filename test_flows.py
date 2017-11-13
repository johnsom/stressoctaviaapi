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

import keystone_tasks
import octavia_tasks
from oslo_config import cfg
from taskflow.patterns import linear_flow
from taskflow.patterns import unordered_flow

CONF = cfg.CONF


class TestFlows(object):

    def multiple_members_flow(self):
        """Creates a flow to build an LB with multiple members.

        :returns: The flow for creating the lb
        """
        base_flow = linear_flow.Flow('base_flow')

        base_flow.add(keystone_tasks.GetToken(provides='token'))

        create_lbs_flow = unordered_flow.Flow('create_lbs_flow')

        for i in range(CONF.test_params.load_balancers):
            lb_name = 'lb{}'.format(i)
            create_lbs_flow.add(self._create_lb_subflow(lb_name))

        base_flow.add(create_lbs_flow)

        return base_flow

    def _create_lb_subflow(self, lb_name):

        create_lb_subflow = linear_flow.Flow(
            'create-{}-subflow'.format(lb_name))

        create_lb_subflow.add(
            octavia_tasks.CreateLoadBalancer(name='create-{}'.format(lb_name),
                                             requires='token',
                                             inject={'name': lb_name},
                                             provides='lb_id'))
        create_lb_subflow.add(
            octavia_tasks.WaitForActive(name='wait-{}-create'.format(lb_name),
                                        requires=('token', 'lb_id')))

        create_listeners_flow = unordered_flow.Flow(
            '{}-create-listeners-flow'.format(lb_name))

        for i in range(CONF.test_params.listeners):
            list_name = 'listener{}'.format(i)
            create_listeners_flow.add(
                self._create_listener_subflow(lb_name, list_name, i+1))

        create_lb_subflow.add(create_listeners_flow)

        return create_lb_subflow

    def _create_listener_subflow(self, lb_name, list_name, list_number):

        create_listener_subflow = linear_flow.Flow(
            'create-{0}-{1}-subflow'.format(lb_name, list_name))

        create_listener_subflow.add(
            octavia_tasks.CreateListener(
                name='create-{0}-{1}'.format(lb_name, list_name),
                requires=('token', 'lb_id'),
                inject={'name': list_name, 'port': list_number},
                provides='listener_id'))

        create_listener_subflow.add(
            octavia_tasks.WaitForActive(
                name='wait-{0}-{1}-create'.format(lb_name, list_name),
                requires=('token', 'lb_id')))

        create_pools_flow = unordered_flow.Flow(
            '{0}-{1}-create-pools-flow'.format(lb_name, list_name))

        for i in range(CONF.test_params.pools):
            pool_name = 'pool{}'.format(i)
            create_pools_flow.add(
                self._create_pool_subflow(lb_name, list_name, pool_name))

        create_listener_subflow.add(create_pools_flow)

        return create_listener_subflow

    def _create_pool_subflow(self, lb_name, list_name, pool_name):

        create_pool_subflow = linear_flow.Flow(
            'create-{0}-{1}-{2}-subflow'.format(lb_name, list_name, pool_name))

        create_pool_subflow.add(
            octavia_tasks.CreatePool(
                name='create-{0}-{1}-{2}'.format(
                    lb_name, list_name, pool_name),
#                requires=('token', 'lb_id'),
                requires=('token', 'listener_id'),
                inject={'name': pool_name},
                provides='pool_id'))

        create_pool_subflow.add(
            octavia_tasks.WaitForActive(
                name='wait-{0}-{1}-{2}-create'.format(
                    lb_name, list_name, pool_name),
                requires=('token', 'lb_id')))

        create_pool_children_flow = unordered_flow.Flow(
            '{0}-{1}-{2}-create-children-flow'.format(
                lb_name, list_name, pool_name))

        if CONF.test_params.health_monitors:
            create_pool_children_flow.add(octavia_tasks.CreateHealthMonitor(
                name='create-{0}-{1}-{2}-hm'.format(
                    lb_name, list_name, pool_name),
                requires=('token', 'pool_id'),
                inject={'name': 'healthmonitor1'},
                provides='healthmonitor_id'))
            create_pool_children_flow.add(octavia_tasks.WaitForActive(
                name='wait-{0}-{1}-{2}-hm-create'.format(
                    lb_name, list_name, pool_name),
                requires=('token', 'lb_id')))

        for i in range(CONF.test_params.members):
            member_name = 'member{}'.format(i)
            create_pool_children_flow.add(
                self._create_member_subflow(lb_name, list_name,
                                            pool_name, member_name, i+1))

        create_pool_subflow.add(create_pool_children_flow)

        return create_pool_subflow

    def _create_member_subflow(self, lb_name, list_name,
                               pool_name, member_name, member_number):

        create_member_subflow = linear_flow.Flow(
            'create-{0}-{1}-{2}-{3}-subflow'.format(lb_name, list_name,
                                                    pool_name, member_name))

        create_member_subflow.add(octavia_tasks.CreateMember(
            name='create-{0}-{1}-{2}-{3}'.format(lb_name, list_name,
                                                 pool_name, member_name),
            requires=('token', 'pool_id'),
            inject={'name': member_name, 'address': '172.21.1.11',
                    'port': member_number},
            provides='member_id'))

        create_member_subflow.add(octavia_tasks.WaitForActive(
            name='wait-{0}-{1}-{2}-{3}-create'.format(lb_name, list_name,
                                                      pool_name, member_name),
            requires=('token', 'lb_id')))

        return create_member_subflow
