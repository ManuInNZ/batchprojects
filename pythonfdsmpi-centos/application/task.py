# python_tutorial_task.py - Batch Python SDK tutorial sample
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

import argparse
import collections
import os
import string
from subprocess import call

import azure.storage.blob as azureblob

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--filepath', required=True,
                        help='The path to the text file to process. The path'
                             'may include a compute node\'s environment'
                             'variables, such as'
                             '$AZ_BATCH_NODE_SHARED_DIR/filename.txt')
    parser.add_argument('--mesh', type=int, required=True,
                        help='The number of meshes for the FDS model.')
    parser.add_argument('--openmp', type=int, required=True,
                        help='The number of OpenMP processors count.')
    parser.add_argument('--rdma', type=int, required=True,
                        help='Should we use RDMA (1 as true/0 as false(default)).')             
    parser.add_argument('--storageaccount', required=True,
                        help='The name the Azure Storage account that owns the'
                             'blob storage container to which to upload'
                             'results.')
    parser.add_argument('--storagecontainer', required=True,
                        help='The Azure Blob storage container to which to'
                             'upload results.')
    parser.add_argument('--sastoken', required=True,
                        help='The SAS token providing write access to the'
                             'Storage container.')
    args = parser.parse_args()

    input_file = os.path.realpath(args.filepath)
    input_project = args.filepath
    input_mesh = args.mesh
    input_openmp = args.openmp
    input_rdma= args.rdma
    #output_file = os.path.realpath('fds_results.zip')
    output_file = 'fds_results.zip'
    run_command = "runscript.sh {} {} {} {} {}".format(input_file, input_project, input_mesh,input_openmp,input_rdma) 
    #call("runscript.sh", shell=True)
    call(run_command, shell=True)


    # Create the blob client using the container's SAS token.
    # This allows us to create a client that provides write
    # access only to the container.
    blob_client = azureblob.BlockBlobService(account_name=args.storageaccount,
                                             sas_token=args.sastoken)

    output_file_path = os.path.realpath(output_file)

    print('Uploading file {} to container [{}]...'.format(
        output_file_path,
        args.storagecontainer))

    blob_client.create_blob_from_path(args.storagecontainer,
                                      output_file,
                                      output_file_path)
