# Copyright 2013 Hewlett-Packard Development Company, L.P.
#
# Author: Kiall Mac Innes <kiall@hp.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
from oslo_config import cfg
from oslo_log import log as logging

from designate.context import DesignateContext
from designate.objects import Record
from designate.notification_handler.base import NotificationHandler


LOG = logging.getLogger(__name__)

# Setup a config group
cfg.CONF.register_group(cfg.OptGroup(
    name='handler:instance_fqdn',
    title="Configuration for Sample Notification Handler"
))

# Setup the config options
cfg.CONF.register_opts([
    cfg.StrOpt('control-exchange', default='nova'),
    cfg.ListOpt('notification-topics', default=['designate']),
    cfg.ListOpt('exclude-projects', default=[]),
    cfg.ListOpt('exclude-zones', default=[]),
], group='handler:instance_fqdn')


class InstanceFQDNHandler(NotificationHandler):
    """Sample Handler"""
    __plugin_name__ = 'instance_fqdn'

    def get_exchange_topics(self):
        """
        Return a tuple of (exchange, [topics]) this handler wants to receive
        events from.
        """
        exchange = cfg.CONF[self.name].control_exchange
        topics = [topic for topic in cfg.CONF[self.name].notification_topics]
        return exchange, topics

    def get_event_types(self):
        return [
            'compute.instance.create.end',
            'compute.instance.delete.start'
        ]

    def _get_tenant_zones(self, context, tenant_id):
        exclude_zones = cfg.CONF[self.name].exclude_zones
        zones = self.central_api.find_zones(
            criterion={'tenant_id': tenant_id})
        valid_zones = [x for x in zones if not x.name[:-1] in exclude_zones]
        valid_zones.sort(key=lambda x: x.name, reverse=True)
        return valid_zones

    def _create(self, context, tenant_zones, instance_name, fixed_ips):
        selected_zone = None
        for z in tenant_zones:
            if instance_name.endswith(z.name[:-1]):
                selected_zone = z
                break

        if not selected_zone:
            LOG.debug('no valid zone for instance %s found in %s', 
                      record_name, tenant_zones)
            return

        for fixed_ip in fixed_ips:
            recordset_values = {
                'zone_id': z.id,
                'name': instance_name,
                'type': 'A' if fixed_ip['version'] == 4 else 'AAAA'
            }

            record_values = {
                'data': fixed_ip['address'],
            }

            LOG.info('creating record for instance %s with value %s',
                     instance_name, fixed_ip['address'])
            self._create_or_update_recordset(
                context, [Record(**record_values)], **recordset_values
            )

    def _delete(self, context, tenant_zones, instance_name):
        LOG.error('_delete not implemented')
        return
    
    def process_notification(self, context, event_type, payload):
        exclude_projects = cfg.CONF[self.name].exclude_projects
        LOG.debug('handling notification payload %s', payload)

        tenant_id = payload['tenant_id']
        record_name = payload['display_name']
        fixed_ips = payload['fixed_ips']

        if tenant_id in exclude_projects:
            LOG.debug('skipping notification, project(%s) in '
                      'exclude_projects(%s)', tenant_id,
                      exclude_projects, payload)
            return

        elevated_context = DesignateContext().elevated(all_tenants=True)
        tenant_zones = self._get_tenant_zones(elevated_context, tenant_id)

        if event_type == "compute.instance.create.end":
            self._create(context, tenant_zones, record_name,
                                fixed_ips)
        elif event_type == "compute.instance.delete.start":
            self._delete(context, tenant_zones, record_name)
        else
            LOG.warning('unknown event_type %s', event_type)
