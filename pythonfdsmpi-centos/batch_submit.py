# batch.py - Batch Python SDK generic application script
#
# Copyright (c) Microsoft Corporation
#
# All rights reserved.
#
# MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

from __future__ import print_function

import datetime
import getopt
import os
import sys
import time

import azure.batch.batch_auth as batchauth
import azure.batch.batch_service_client as batch
import azure.batch.models as batchmodels
import azure.storage.blob as azureblob
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

# to be overloaded with config file

_POOL_ID = 'Pool{}'.format(datetime.datetime.now().strftime("-%y%m%d-%H%M%S"))
_POOL_NODE_COUNT = 1
_POOL_NODE_COUNT_LOW = 0
# _POOL_VM_SIZE = 'BASIC_A2'
#_POOL_VM_SIZE = 'Standard_H16r'
_POOL_VM_SIZE = 'STANDARD_A8'
# _NODE_OS_PUBLISHER = 'Canonical'
_NODE_OS_PUBLISHER = 'Openlogic'
_NODE_OS_OFFER = 'CentOS'
_NODE_OS_SKU = '7.4'
_USE_RDMA = 0

_JOB_ID = 'Job{}'.format(datetime.datetime.now().strftime("-%y%m%d-%H%M%S"))

_TASK_FILE = 'task.py'
_SCRIPT = 'runscript.sh'
_PREPSCRIPT = 'prepscript.sh'
_MESH_COUNT = '1'
_OPENMP_COUNT = '1'


def query_yes_no(question, default="yes"):
    """
    Prompts the user for yes/no input, displaying the specified question text.

    :param str question: The text of the prompt for input.
    :param str default: The default if the user hits <ENTER>. Acceptable values
    are 'yes', 'no', and None.
    :rtype: str
    :return: 'yes' or 'no'
    """
    valid = {'y': 'yes', 'n': 'no'}
    if default is None:
        prompt = ' [y/n] '
    elif default == 'yes':
        prompt = ' [Y/n] '
    elif default == 'no':
        prompt = ' [y/N] '
    else:
        raise ValueError("Invalid default answer: '{}'".format(default))

    while 1:
        choice = input(question + prompt).lower()
        if default and not choice:
            return default
        try:
            return valid[choice[0]]
        except (KeyError, IndexError):
            print("Please respond with 'yes' or 'no' (or 'y' or 'n').\n")


def print_batch_exception(batch_exception):
    """
    Prints the contents of the specified Batch exception.

    :param batch_exception:
    """
    print('-------------------------------------------')
    print('Exception encountered:')
    if batch_exception.error and \
            batch_exception.error.message and \
            batch_exception.error.message.value:
        print(batch_exception.error.message.value)
        if batch_exception.error.values:
            print()
            for mesg in batch_exception.error.values:
                print('{}:\t{}'.format(mesg.key, mesg.value))
    print('-------------------------------------------')


def upload_file_to_container(block_blob_client, container_name, file_path):
    """
    Uploads a local file to an Azure Blob storage container.

    :param block_blob_client: A blob service client.
    :type block_blob_client: `azure.storage.blob.BlockBlobService`
    :param str container_name: The name of the Azure Blob storage container.
    :param str file_path: The local path to the file.
    :rtype: `azure.batch.models.ResourceFile`
    :return: A ResourceFile initialized with a SAS URL appropriate for Batch
    tasks.
    """
    blob_name = os.path.basename(file_path)

    print('Uploading file {} to container [{}]...'.format(file_path,
                                                          container_name))

    block_blob_client.create_blob_from_path(container_name,
                                            blob_name,
                                            file_path)

    sas_token = block_blob_client.generate_blob_shared_access_signature(
        container_name,
        blob_name,
        permission=azureblob.BlobPermissions.READ,
        expiry=datetime.datetime.utcnow() + datetime.timedelta(days=8))

    sas_url = block_blob_client.make_blob_url(container_name,
                                              blob_name,
                                              sas_token=sas_token)

    return batchmodels.ResourceFile(file_path=blob_name,
                                    blob_source=sas_url)


def get_container_sas_token(block_blob_client,
                            container_name, blob_permissions):
    """
    Obtains a shared access signature granting the specified permissions to the
    container.

    :param block_blob_client: A blob service client.
    :type block_blob_client: `azure.storage.blob.BlockBlobService`
    :param str container_name: The name of the Azure Blob storage container.
    :param BlobPermissions blob_permissions:
    :rtype: str
    :return: A SAS token granting the specified permissions to the container.
    """
    # Obtain the SAS token for the container, setting the expiry time and
    # permissions. In this case, no start time is specified, so the shared
    # access signature becomes valid immediately.
    container_sas_token = \
        block_blob_client.generate_container_shared_access_signature(
            container_name,
            permission=blob_permissions,
            expiry=datetime.datetime.utcnow() + datetime.timedelta(days=30))

    return container_sas_token


def create_pool(batch_service_client, pool_id,
                resource_files, publisher, offer, sku):
    """
    Creates a pool of compute nodes with the specified OS settings.

    :param batch_service_client: A Batch service client.
    :type batch_service_client: `azure.batch.BatchServiceClient`
    :param str pool_id: An ID for the new pool.
    :param list resource_files: A collection of resource files for the pool's
    start task.
    :param str publisher: Marketplace image publisher
    :param str offer: Marketplace image offer
    :param str sku: Marketplace image sku
    """
    print('Creating pool [{}]...'.format(pool_id))

    # Create a new pool of Linux compute nodes using an Azure Virtual Machines
    # Marketplace image. For more information about creating pools of Linux
    # nodes, see:
    # https://azure.microsoft.com/documentation/articles/batch-linux-nodes/

    # Specify the commands for the pool's start task. The start task is run
    # on each node as it joins the pool, and when it's rebooted or re-imaged.
    # We use the start task to prep the node for running our task script.
    task_commands = [
        # Copy the python_task.py script to the "shared" directory
        # that all tasks that run on the node have access to. Note that
        # we are using the -p flag with cp to preserve the file uid/gid,
        # otherwise since this start task is run as an admin, it would not
        # be accessible by tasks run as a non-admin user.
        'cp -p {} $AZ_BATCH_NODE_SHARED_DIR'.format(_TASK_FILE),
        'cp -p {} $AZ_BATCH_NODE_SHARED_DIR'.format(_SCRIPT),
        'cp -p {} $AZ_BATCH_NODE_SHARED_DIR'.format(_PREPSCRIPT),
        #'sudo yum -y update',
        'sudo yum -y install nfs-utils',
        # Install pip
        'sudo yum -y install epel-release',
        'sudo yum -y install python-pip',
        'sudo yum -y install htop',
        'sudo yum -y install inxi',
        'sudo pip install azure-storage==0.32.0',
        'mkdir -p /home/fdsuser/.ssh',
        'chmod 700 /home/fdsuser/.ssh',
        'echo "StrictHostKeyChecking no" >> /home/fdsuser/.ssh/config',
        'chmod 600 /home/fdsuser/.ssh/config',
        'export APP_INSIGHTS_APP_ID="{}"'.format(_APP_INSIGHTS_APP_ID),
        'export APP_INSIGHTS_INSTRUMENTATION_KEY="{}"'.format(
            _APP_INSIGHTS_INSTRUMENTATION_KEY),
        'chmod +x $AZ_BATCH_NODE_SHARED_DIR/{}'.format(_SCRIPT),
        'chmod +x $AZ_BATCH_NODE_SHARED_DIR/{}'.format(_PREPSCRIPT),
        'wget  https://raw.githubusercontent.com/Azure/batch-insights/master/centos.sh',
        'sudo -E bash ./centos.sh',
        'export HOME=$AZ_BATCH_NODE_SHARED_DIR',
        'cd $AZ_BATCH_APP_PACKAGE_fds_bundle',
        './FDS_6.6.0-SMV_6.6.0_linux64.sh y',
        # make sure MPI is allowed to run in Ubuntu, without this, this is seen as a security attack....
        # 'sudo sed -i -e "s/kernel.yama.ptrace_scope = 1/kernel.yama.ptrace_scope = 0/" /etc/sysctl.d/10-ptrace.conf',
        # 'sudo sysctl -w kernel.yama.ptrace_scope=0',
        # 'bash -c sudo bash -c echo \"*           hard    memlock         unlimited\" >> /etc/security/limits.conf',
        # 'bash -c sudo bash -c echo \"*           soft    memlock         unlimited\" >> /etc/security/limits.conf',
        'echo \"*           hard    memlock         unlimited\" | sudo tee --append /etc/security/limits.conf',
        'echo \"*           soft    memlock         unlimited\" | sudo tee --append /etc/security/limits.conf'
        # 'bash -c ulimit -a',
        # 'bash -c ulimit -Ha',
        #'sudo tail -4 /etc/security/limits.conf'
    ]

    # Get the node agent SKU and image reference for the virtual machine
    # configuration.
    # For more information about the virtual machine configuration, see:
    # https://azure.microsoft.com/documentation/articles/batch-linux-nodes/
    sku_to_use, image_ref_to_use = \
        common.helpers.select_latest_verified_vm_image_with_node_agent_sku(
            batch_service_client, publisher, offer, sku)
    # user = batchmodels.AutoUserSpecification(
    #    scope=batchmodels.AutoUserScope.pool,
    #    elevation_level=batchmodels.ElevationLevel.admin)
    # print(_POOL_NODE_COUNT)
    # print(type(_POOL_NODE_COUNT))
    # target_low_priority_nodes_count=int(_POOL_NODE_COUNT)-1

    new_pool = batch.models.PoolAddParameter(
        id=pool_id,
        virtual_machine_configuration=batchmodels.VirtualMachineConfiguration(
            image_reference=image_ref_to_use,
            node_agent_sku_id=sku_to_use),
        vm_size=_POOL_VM_SIZE,
        target_low_priority_nodes=_POOL_NODE_COUNT_LOW,
        target_dedicated_nodes=_POOL_NODE_COUNT,
        enable_inter_node_communication=1,
        max_tasks_per_node=1,  # as per mpi article
        start_task=batch.models.StartTask(
            command_line=common.helpers.wrap_commands_in_shell('linux',
                                                               task_commands),
            environment_settings=[batch.models.EnvironmentSetting('APP_INSIGHTS_APP_ID', value=_APP_INSIGHTS_APP_ID),
                                  batch.models.EnvironmentSetting('APP_INSIGHTS_INSTRUMENTATION_KEY', value=_APP_INSIGHTS_INSTRUMENTATION_KEY)],
            user_identity=batch.models.UserIdentity(user_name='fdsuser'),
            wait_for_success=True,
            resource_files=resource_files),
        application_package_references=[batch.models.ApplicationPackageReference(
            'fds_bundle', version='6.6.0')],
        user_accounts=[batch.models.UserAccount(
            'fdsuser', 'makethisaverysecureandrandompassword', elevation_level='admin',
            linux_user_configuration=None)],
    )

    try:
        batch_service_client.pool.add(new_pool)
    except batchmodels.batch_error.BatchErrorException as err:
        print_batch_exception(err)
        raise


def create_job(batch_service_client, job_id, pool_id):
    """
    Creates a job with the specified ID, associated with the specified pool.

    :param batch_service_client: A Batch service client.
    :type batch_service_client: `azure.batch.BatchServiceClient`
    :param str job_id: The ID for the job.
    :param str pool_id: The ID for the pool.
    """
    print('Creating job [{}]...'.format(job_id))

    job = batch.models.JobAddParameter(
        job_id,
        batch.models.PoolInformation(pool_id=pool_id))

    try:
        batch_service_client.job.add(job)
    except batchmodels.batch_error.BatchErrorException as err:
        print_batch_exception(err)
        raise


def add_tasks(batch_service_client, job_id, input_files,
              output_container_name, output_container_sas_token):
    """
    Adds a task for each input file in the collection to the specified job.

    :param batch_service_client: A Batch service client.
    :type batch_service_client: `azure.batch.BatchServiceClient`
    :param str job_id: The ID of the job to which to add the tasks.
    :param list input_files: A collection of input files. One task will be
     created for each input file.
    :param output_container_name: The ID of an Azure Blob storage container to
    which the tasks will upload their results.
    :param output_container_sas_token: A SAS token granting write access to
    the specified Azure Blob storage container.
    """

    task_commands = [
        'bash $AZ_BATCH_NODE_SHARED_DIR/{}'.format(_PREPSCRIPT)
    ]

    print('Adding {} tasks to job [{}]...'.format(len(input_files), job_id))

    tasks = list()

    for idx, input_file in enumerate(input_files):

        command = ['python $AZ_BATCH_NODE_SHARED_DIR/{} '
                   '--filepath {} --mpiprocs {} --openmp {} --rdma {} --storageaccount {} '
                   '--storagecontainer {} --sastoken "{}"'.format(
                       _TASK_FILE,
                       input_file.file_path,
                       _MPI_PROCESSORS,
                       _OPENMP_COUNT,
                       _USE_RDMA,
                       _STORAGE_ACCOUNT_NAME,
                       output_container_name,
                       output_container_sas_token)]

        total_instances = int(_POOL_NODE_COUNT) + int(_POOL_NODE_COUNT_LOW)
        print(f"{total_instances} and type {type(total_instances)} ")
        tasks.append(batch.models.TaskAddParameter(
            'FDS',
            common.helpers.wrap_commands_in_shell('linux', command),
            resource_files=[input_file],
            multi_instance_settings=(batch.models.MultiInstanceSettings(
                coordination_command_line=common.helpers.wrap_commands_in_shell(
                    'linux', task_commands),
                number_of_instances=total_instances)
            ),
            user_identity=batch.models.UserIdentity(user_name='fdsuser'),
        )
        )

    batch_service_client.task.add_collection(job_id, tasks)


def wait_for_tasks_to_complete(batch_service_client, job_id, timeout):
    """
    Returns when all tasks in the specified job reach the Completed state.

    :param batch_service_client: A Batch service client.
    :type batch_service_client: `azure.batch.BatchServiceClient`
    :param str job_id: The id of the job whose tasks should be to monitored.
    :param timedelta timeout: The duration to wait for task completion. If all
    tasks in the specified job do not reach Completed state within this time
    period, an exception will be raised.
    """
    timeout_expiration = datetime.datetime.now() + timeout

    print("Monitoring all tasks for 'Completed' state, timeout in {}..."
          .format(timeout), end='')

    while datetime.datetime.now() < timeout_expiration:
        print('.', end='')
        sys.stdout.flush()
        tasks = batch_service_client.task.list(job_id)

        incomplete_tasks = [task for task in tasks if
                            task.state != batchmodels.TaskState.completed]
        if not incomplete_tasks:
            print()
            return True
        else:
            time.sleep(1)

    print()
    raise RuntimeError("ERROR: Tasks did not reach 'Completed' state within "
                       "timeout period of " + str(timeout))


def download_blobs_from_container(block_blob_client,
                                  container_name, directory_path):
    """
    Downloads all blobs from the specified Azure Blob storage container.

    :param block_blob_client: A blob service client.
    :type block_blob_client: `azure.storage.blob.BlockBlobService`
    :param container_name: The Azure Blob storage container from which to
     download files.
    :param directory_path: The local directory to which to download the files.
    """
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

    print('Downloading all files from container [{}]...'.format(
        container_name))

    container_blobs = block_blob_client.list_blobs(container_name)

    for blob in container_blobs.items:
        destination_file_path = os.path.join(directory_path, blob.name)

        block_blob_client.get_blob_to_path(container_name,
                                           blob.name,
                                           destination_file_path)

        print('  Downloaded blob [{}] from container [{}] to {}'.format(
            blob.name,
            container_name,
            destination_file_path))

    print('  Download complete!')


def get_pool_information(batch_service_client, pool_id, job_id):
    """
    Gets all available pool information be captured

    :param batch_service_client: A Batch service client.
    :type batch_service_client: `azure.batch.BatchServiceClient`
    :param str pool_id: The id of the pool used.
    :param str job_id: The id of the job trigerred. 

    """
    details_gathered = ''

    return details_gathered


def main(argv):
    inputfile = ''
    conffile = ''
    mpicount = 1
    openMPcount = 1
    nodes = 0
    lowprio = 0
    rdma = 0
    vmsku = 'STANDARD_A8'
    os_offer = 'CentOS'
    # outputfile = ''
    helpline = "submit_batch.py -i <inputfile> [-n <nodecount> -m <mpicount>  -p <openMPcount> -r (0|1) -v <vmSKU>]"

    try:
        opts, args = getopt.getopt(
            argv, "hi:c:n:l:m:p:r:v:", ["inputfile=", "conf=", "nodes=", "lowprio=", "mpicount=", "openmp=", "rdma=", "vmsku="])
    except getopt.GetoptError:
        print(helpline)
        sys.exit(2)
    for opt, arg in opts:
        # print('opt:{}\narg:{}'.format(opt,arg))
        if opt == '-h':
            print(helpline)
            print(
                f'Defaults\n\t-n {nodes} as nodecount\n\t-m {mpicount} as mpi processes count\n\t-p {openMPcount} as OpenMPcount\n\tNo RDMA\n\t-v {vmsku} as vmSKU')
            sys.exit()
        elif opt in ("-i", "--inputfile"):
            inputfile = arg
        elif opt in ("-c", "--conf"):
            conffile = arg
        elif opt in ("-n", "--nodes"):
            nodes = arg
        elif opt in ("-l", "--lowprio"):
            lowprio = arg
        elif opt in ("-m", "--mpicount"):
            mpicount = arg
        elif opt in ("-p", "--openmp"):
            openMPcount = arg
        elif opt in ("-r", "--rdma"):
            rdma = int(arg)
            if rdma == 1:
                os_offer = 'CentOS-HPC'
        elif opt in ("-v", "--vmsku"):
            vmsku = arg

    if inputfile == '':
        print(helpline)
        sys.exit()

    totalnodes = int(nodes) + int(lowprio)
    if (totalnodes) == 0:
        print("Needs at least one node!")
        print(helpline)
        sys.exit()

    return inputfile, conffile, nodes, lowprio, mpicount, openMPcount, rdma, os_offer, vmsku


if __name__ == '__main__':

    inputfile, conffile, _POOL_NODE_COUNT, _POOL_NODE_COUNT_LOW, _MPI_PROCESSORS, _OPENMP_COUNT, _USE_RDMA, _NODE_OS_OFFER, _POOL_VM_SIZE = main(
        sys.argv[1:])
    start_time = datetime.datetime.now().replace(microsecond=0)
    print('Sample start: {}'.format(start_time))
    print()

    # Read conf file
    global_config = configparser.ConfigParser()
    if conffile == '':
        global_config.read(common.helpers._SAMPLES_CONFIG_FILE_NAME)
    else:
        global_config.read(conffile)

    # Set up the configuration
    _BATCH_ACCOUNT_KEY = global_config.get('Batch', 'batchaccountkey')
    _BATCH_ACCOUNT_NAME = global_config.get('Batch', 'batchaccountname')
    _BATCH_ACCOUNT_URL = global_config.get('Batch', 'batchserviceurl')

    _STORAGE_ACCOUNT_KEY = global_config.get('Storage', 'storageaccountkey')
    _STORAGE_ACCOUNT_NAME = global_config.get('Storage', 'storageaccountname')

    _APP_INSIGHTS_APP_ID = global_config.get('AppInsights', 'applicationid')
    _APP_INSIGHTS_INSTRUMENTATION_KEY = global_config.get(
        'AppInsights', 'instrumentationkey')
    # storage_account_suffix = global_config.get('Storage', 'storageaccountsuffix')

    # Create the blob client, for use in obtaining references to
    # blob storage containers and uploading files to containers.
    blob_client = azureblob.BlockBlobService(
        account_name=_STORAGE_ACCOUNT_NAME,
        account_key=_STORAGE_ACCOUNT_KEY)

    directory = os.path.expanduser('./result/' + _JOB_ID)
    if not os.path.exists(directory):
        os.makedirs(directory)

    with open(directory + "_pool_description.txt", "w") as text_file:
        print('###################################################################################', file=text_file)
        print(
            f"OS and version used: {_NODE_OS_OFFER} {_NODE_OS_SKU}", file=text_file)
        print(f"Number of dedicated nodes: {_POOL_NODE_COUNT}", file=text_file)
        print(
            f"Number of low priority nodes: {_POOL_NODE_COUNT_LOW}", file=text_file)
        print(f"VM used: {_POOL_VM_SIZE}", file=text_file)
        print(f"File submitted: {inputfile}", file=text_file)
        if _USE_RDMA == 1:
            print('Using RDMA networking', file=text_file)
        else:
            print('Without using RDMA networking', file=text_file)
        print(f"OpenMP threads: {_OPENMP_COUNT}", file=text_file)
        print('###################################################################################', file=text_file)
        text_file.close()

    print('Created blob client')
    # Use the blob client to create the containers in Azure Storage if they
    # don't yet exist.
    app_container_name = 'application{}'.format(
        datetime.datetime.now().strftime("-%y%m%d-%H%M%S"))
    input_container_name = 'input{}'.format(
        datetime.datetime.now().strftime("-%y%m%d-%H%M%S"))
    output_container_name = 'output{}'.format(
        datetime.datetime.now().strftime("-%y%m%d-%H%M%S"))
#    print('Containers: \n{}\n{}\n{}\n'.format(app_container_name,input_container_name,output_container_name))
#    print()
    blob_client.create_container(app_container_name, fail_on_exist=False)
    blob_client.create_container(input_container_name, fail_on_exist=False)
    blob_client.create_container(output_container_name, fail_on_exist=False)

    # Paths to the task script. This script will be executed by the tasks that
    # run on the compute nodes.
    application_file_paths = [os.path.realpath('./application/{}'.format(_TASK_FILE)),
                              os.path.realpath(
                                  './application/{}'.format(_SCRIPT)),
                              os.path.realpath('./application/{}'.format(_PREPSCRIPT))]

    # The collection of data files that are to be processed by the tasks.
    input_file_paths = [os.path.realpath(inputfile)]

    # Upload the application script to Azure Storage. This is the script that
    # will process the data files, and is executed by each of the tasks on the
    # compute nodes.
    starttask_time = datetime.datetime.now().replace(microsecond=0)
    print('Uploading app files start: {}'.format(starttask_time))
    application_files = [
        upload_file_to_container(blob_client, app_container_name, file_path)
        for file_path in application_file_paths]
    finishtask_time = datetime.datetime.now().replace(microsecond=0)
    print()
    print('Uploading app files end: {}'.format(finishtask_time))
    print('Elapsed time: {}'.format(finishtask_time - starttask_time))
    print()

    # Upload the data files. This is the data that will be processed by each of
    # the tasks executed on the compute nodes in the pool.
    starttask_time = datetime.datetime.now().replace(microsecond=0)
    print('Uploading data files start: {}'.format(starttask_time))
    input_files = [
        upload_file_to_container(blob_client, input_container_name, file_path)
        for file_path in input_file_paths]
    finishtask_time = datetime.datetime.now().replace(microsecond=0)
    print()
    print('Uploading data files end: {}'.format(finishtask_time))
    print('Elapsed time: {}'.format(finishtask_time - starttask_time))
    print()

    # Upload the pool description txt to output
    upload_file_to_container(blob_client,
                             output_container_name,
                             os.path.realpath(directory + "_pool_description.txt"))

    # Obtain a shared access signature that provides write access to the output
    # container to which the tasks will upload their output.
    output_container_sas_token = get_container_sas_token(
        blob_client,
        output_container_name,
        azureblob.BlobPermissions.WRITE)

    # Create a Batch service client. We'll now be interacting with the Batch
    # service in addition to Storage
    credentials = batchauth.SharedKeyCredentials(_BATCH_ACCOUNT_NAME,
                                                 _BATCH_ACCOUNT_KEY)

    batch_client = batch.BatchServiceClient(
        credentials,
        base_url=_BATCH_ACCOUNT_URL)

    # Create the pool that will contain the compute nodes that will execute the
    # tasks. The resource files we pass in are used for configuring the pool's
    # start task, which is executed each time a node first joins the pool (or
    # is rebooted or re-imaged).

    starttask_time = datetime.datetime.now().replace(microsecond=0)
    print('Creating pool start: {}'.format(starttask_time))
    create_pool(batch_client,
                _POOL_ID,
                application_files,
                _NODE_OS_PUBLISHER,
                _NODE_OS_OFFER,
                _NODE_OS_SKU)
    finishtask_time = datetime.datetime.now().replace(microsecond=0)
    print()
    print('Creating pool end: {}'.format(finishtask_time))
    print('Elapsed time: {}'.format(finishtask_time - starttask_time))
    print()
    # Create the job that will run the tasks.

    starttask_time = datetime.datetime.now().replace(microsecond=0)
    print('Creating job start: {}'.format(starttask_time))
    create_job(batch_client, _JOB_ID, _POOL_ID)

    # Add the tasks to the job. We need to supply a container shared access
    # signature (SAS) token for the tasks so that they can upload their output
    # to Azure Storage.
    starttask_time = datetime.datetime.now().replace(microsecond=0)
    print('Adding tasks start: {}'.format(starttask_time))

    add_tasks(batch_client,
              _JOB_ID,
              input_files,
              output_container_name,
              output_container_sas_token)

    # Pause execution until tasks reach Completed state.
    starttask_time = datetime.datetime.now().replace(microsecond=0)
    print('Waiting tasks start: {}'.format(starttask_time))

    wait_for_tasks_to_complete(batch_client,
                               _JOB_ID,
                               datetime.timedelta(days=30))

    finishtask_time = datetime.datetime.now().replace(microsecond=0)
    print()
    print('Waiting tasks end: {}'.format(finishtask_time))
    print('Elapsed time: {}'.format(finishtask_time - starttask_time))
    print()

    print("  Success! All tasks reached the 'Completed' state within the "
          "specified timeout period.")

    # Clean up Batch resources (if the user so chooses).
    # if query_yes_no('Delete pool?') == 'yes':
    batch_client.pool.delete(_POOL_ID)

    # if query_yes_no('Delete job?') == 'yes':
    #    batch_client.job.delete(_JOB_ID)

    # Download the task output files from the output Storage container to a
    # local directory. Note that we could have also downloaded the output
    # files directly from the compute nodes themselves.

    # if query_yes_no('Download all results?', default="no") == 'yes':
    #     download_blobs_from_container(blob_client,
    #                                   output_container_name,
    #                                   directory)

    #details = get_pool_information(batch_client, _POOL_ID,_JOB_ID)
    #print(details, file=text_file)
    #print(f"Purchase Amount: {TotalAmount}", file=text_file)

    # Clean up storage resources
    print('Deleting containers...')
    # if query_yes_no('Delete appl and input storage containers?') == 'yes':
    blob_client.delete_container(input_container_name)
    blob_client.delete_container(app_container_name)
    # if query_yes_no('Delete output storage containers?', default="no") == 'yes':
    #    blob_client.delete_container(output_container_name)

    # Print out some timing info
    end_time = datetime.datetime.now().replace(microsecond=0)
    print()
    print('Sample end: {}'.format(end_time))
    print('Elapsed time: {}'.format(end_time - start_time))
    print()

    # print()
    # input('Press ENTER to exit...')
