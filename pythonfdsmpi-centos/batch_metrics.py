###
#
#
#
from __future__ import print_function

import datetime
import getopt
import os
import sys
import time
import math

import azure.batch.batch_auth as batchauth
import azure.batch.batch_service_client as batch
import azure.batch.models as batchmodels


import common.helpers  # noqa

try:
    import configparser
except ImportError:
    import ConfigParser as configparser


try:
    input = raw_input
except NameError:
    pass

sys.path.append('.')
sys.path.append('..')

# Update the Batch and Storage account credential strings below with the values
# unique to your accounts. These are used when constructing connection strings
# for the Batch and Storage client objects.
_BATCH_ACCOUNT_NAME = ''
_BATCH_ACCOUNT_KEY = ''
_BATCH_ACCOUNT_URL = ''

_STORAGE_ACCOUNT_NAME = ''
_STORAGE_ACCOUNT_KEY = ''

_APP_INSIGHTS_APP_ID = ''
_APP_INSIGHTS_INSTRUMENTATION_KEY = ''

_NODE_OS_PUBLISHER = 'Openlogic'
_NODE_OS_OFFER = 'CentOS'
_NODE_OS_SKU = '7.3'


if __name__ == '__main__':

    global_config = configparser.ConfigParser()
    global_config.read(common.helpers._SAMPLES_CONFIG_FILE_NAME)
    # Set up the configuration
    _BATCH_ACCOUNT_KEY = global_config.get('Batch', 'batchaccountkey')
    _BATCH_ACCOUNT_NAME = global_config.get('Batch', 'batchaccountname')
    _BATCH_ACCOUNT_URL = global_config.get('Batch', 'batchserviceurl')

    _STORAGE_ACCOUNT_KEY = global_config.get('Storage', 'storageaccountkey')
    _STORAGE_ACCOUNT_NAME = global_config.get('Storage', 'storageaccountname')

    _APP_INSIGHTS_APP_ID = global_config.get('AppInsights', 'applicationid')
    _APP_INSIGHTS_INSTRUMENTATION_KEY = global_config.get(
        'AppInsights', 'instrumentationkey')
    # Create a Batch service client. We'll now be interacting with the Batch
    # service in addition to Storage
    credentials = batchauth.SharedKeyCredentials(_BATCH_ACCOUNT_NAME,
                                                 _BATCH_ACCOUNT_KEY)

    batch_client = batch.BatchServiceClient(
        credentials,
        base_url=_BATCH_ACCOUNT_URL)

    now = datetime.datetime.utcnow().replace(microsecond=0, tzinfo=None)
    #bobo = batch_client.pool.get_all_lifetime_statistics()
    usage_metrics = batch_client.pool.list_usage_metrics(batchmodels.PoolListUsageMetricsOptions(
        end_time=now,
        start_time=(now - datetime.timedelta(days=7))))

    sum_core_hours = 0.0
    usage_summary = {'Pool': '',
                     'VM Size': '',
                     'End time': (now - datetime.timedelta(days=5)),
                     'Start time': now,
                     'Core hours': 0.0
                     }
    for current_agg_metrics in usage_metrics:
        usage_summary['Pool'] = current_agg_metrics.pool_id
        usage_summary['VM Size'] = current_agg_metrics.vm_size
        if (current_agg_metrics.start_time.replace(tzinfo=None) < usage_summary['Start time']):
            usage_summary['Start time'] = current_agg_metrics.start_time.replace(
                tzinfo=None)
        if (current_agg_metrics.end_time.replace(tzinfo=None) > usage_summary['End time']):
            usage_summary['End time'] = current_agg_metrics.end_time.replace(
                tzinfo=None)
        usage_summary['Core hours'] += current_agg_metrics.total_core_hours
        sum_core_hours += current_agg_metrics.total_core_hours

    # print('Total core hours {}'.format(math.ceil(sum_core_hours)))
    usage_summary['Core hours'] = math.ceil(usage_summary['Core hours'])
    #node_agent_skus = batch_client.account.list_node_agent_skus()
    # print(usage_summary)

    # print(node_agent_skus)
    # for sku in node_agent_skus:
    #     print(sku.os_type)
    #     for image in sku.verified_image_references:
    #         print(image)

    print('Pool ID: {}'.format(usage_summary['Pool']))
    print('VM: {}'.format(usage_summary['VM Size']))
    print('Start time: {}'.format(usage_summary['Start time']))
    print('End time: {}'.format(usage_summary['End time']))
    print('Core hours: {}'.format(usage_summary['Core hours']))

    ###
    # PoolListUsageMetricsOptions()
