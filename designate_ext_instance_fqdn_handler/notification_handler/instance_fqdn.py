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


class InstanceFQDNHandler(BaseAddressHandler):
    """Handler for Nova's notifications"""
    __plugin_name__ = 'nova_fixed'

    def get_exchange_topics(self):
        exchange = cfg.CONF[self.name].control_exchange

        topics = [topic for topic in cfg.CONF[self.name].notification_topics]

        return (exchange, topics)

    def get_event_types(self):
        return [
            'compute.instance.create.end',
            'compute.instance.delete.start',
        ]

    def _get_ip_data(self, addr_dict):
        data = super(NovaFixedHandler, self)._get_ip_data(addr_dict)
        data['label'] = addr_dict['label']
        return data

    def _get_tenant_zones(self, context, tenant_id):
        exclude_zones = cfg.CONF[self.name].exclude_zones
        zones = self.central_api.find_zones(
            criterion={'tenant_id': tenant_id})
        valid_zones = [x for x in zones if not x.name[:-1] in exclude_zones]
        valid_zones.sort(key=lambda x: x.name, reverse=True)
        return valid_zones

    def process_notification(self, context, event_type, payload):
        LOG.debug('InstanceFQDNHandler received notification - %s', event_type)

        tenant_id = payload['tenant_id']
        record_name = payload['display_name']
        fixed_ips = payload['fixed_ips']

        zone = None
        for z in get_tenant_zones(context, tenant_id):
            if instance_name.endswith(z.name[:-1]):
                zone = z
                break

        if not zone:
            LOG.debug('No matching zone for instance %s', instance_name)
            return

        if event_type == 'compute.instance.create.end':
            payload['project'] = context.get("project_name", None)
            self._create(addresses=payload['fixed_ips'],
                         extra=payload,
                         zone_id=zone.zone_id,
                         resource_id=payload['instance_id'],
                         resource_type='instance')

        elif event_type == 'compute.instance.delete.start':
            self._delete(zone_id=zone.zone_id,
                         resource_id=payload['instance_id'],
                         resource_type='instance')
