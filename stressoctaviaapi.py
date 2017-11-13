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

import sys

import concurrent.futures

from oslo_config import cfg
from oslo_log import log as logging
from taskflow import engines as tf_engines
from taskflow.listeners import logging as tf_logging

import test_flows

CONF = cfg.CONF

keystone_opts = [
    cfg.StrOpt('username', required=True,
               help='User to test with.'),
    cfg.StrOpt('password', required=True,
               help='Password for test user.'),
    cfg.StrOpt('project_name', required=True,
               help='Name of the project to test under.'),
    cfg.StrOpt('project_domain_name', required=True,
               help='Domain for the project to test under.'),
    cfg.StrOpt('auth_url', required=True,
               help='URL to the identity service endpoint.'),
]
cfg.CONF.register_opts(keystone_opts, group='keystone_authtoken')

task_flow_opts = [
    cfg.StrOpt('engine',
               default='serial',
               help='TaskFlow engine to use'),
    cfg.IntOpt('max_workers',
               default=5,
               help='The maximum number of workers'),
    cfg.BoolOpt('disable_revert', default=False,
                help='If True, disables the controller worker taskflow '
                     'flows from reverting.  This will leave resources in '
                     'an inconsistent state and should only be used for '
                     'debugging purposes.')
]
cfg.CONF.register_opts(task_flow_opts, group='task_flow')

test_params_opts = [
    cfg.StrOpt('api_endpoint', required=True,
               help='URL for the API endpoint to test.'),
    cfg.StrOpt('test_flow', required=True,
               help='Name of test flow to run.'),
    cfg.StrOpt('vip_subnet_id', required=True,
               help='Subnet to create VIPs on.'),
    cfg.StrOpt('member_subnet_id', required=True,
               help='Subnet to create members on.'),
    cfg.IntOpt('load_balancers',
               default=1, min=1,
               help='Number of load balancers to create.'),
    cfg.IntOpt('listeners',
               default=1,
               help='Number of listeners to create.'),
    cfg.IntOpt('pools',
               default=1,
               help='Number of pools to create.'),
    cfg.IntOpt('health_monitors',
               default=1, min=0, max=1,
               help='Number of health managers to create.'),
    cfg.IntOpt('members',
               default=1, min=1, max=65535,
               help='Number of members to create.'),
    cfg.IntOpt('retries_check_active',
               default=5000,
               help='Number retries to check LB for ACTIVE.'),
]
cfg.CONF.register_opts(test_params_opts, group='test_params')


def main():
    logging.register_options(cfg.CONF)
    cfg.CONF(args=sys.argv[1:],
             project='stressoctaviaapi',
             version='stressoctaviaapi 1.0')
    logging.set_defaults()
    logging.setup(cfg.CONF, 'stressoctaviaapi')
    LOG = logging.getLogger(__name__)

    LOG.debug('***********************Started')

    executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=CONF.task_flow.max_workers)

    test_flows_cls = test_flows.TestFlows()
    flow = getattr(test_flows_cls, CONF.test_params.test_flow)()

    eng = tf_engines.load(
            flow,
            engine=CONF.task_flow.engine,
            executor=executor,
            never_resolve=CONF.task_flow.disable_revert)
    eng.compile()
    eng.prepare()

    with tf_logging.DynamicLoggingListener(eng, log=LOG):

            eng.run()

if __name__ == "__main__":
    main()
