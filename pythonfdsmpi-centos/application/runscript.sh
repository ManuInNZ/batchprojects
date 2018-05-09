#!/usr/bin/env bash

# some comments to make sure the file is a little over 1K since otherwise it seems that the blob upload does not really understand it....
# some comments to make sure the file is a little over 1K since otherwise it seems that the blob upload does not really understand it....
# some comments to make sure the file is a little over 1K since otherwise it seems that the blob upload does not really understand it....
# some comments to make sure the file is a little over 1K since otherwise it seems that the blob upload does not really understand it....
# some comments to make sure the file is a little over 1K since otherwise it seems that the blob upload does not really understand it....
# some comments to make sure the file is a little over 1K since otherwise it seems that the blob upload does not really understand it....
# some comments to make sure the file is a little over 1K since otherwise it seems that the blob upload does not really understand it....
# some comments to make sure the file is a little over 1K since otherwise it seems that the blob upload does not really understand it....
# some comments to make sure the file is a little over 1K since otherwise it seems that the blob upload does not really understand it....

export SCRIPT_NAME=$0
export INPUT_FILE=$1
export PROJECT_NAME=$2
export MESH=$3
export INPUTOPENMP=$4
export SHORT_NAME=${PROJECT_NAME::-4}
echo "# full line"
echo $0 $1 $2 $3 $4
echo "# input file: $INPUT_FILE"
echo "# project: $PROJECT_NAME $SHORT_NAME"
echo "# number of meshes:" $MESH
echo "# number of openMP:" $INPUTOPENMP

export LD_LIBRARY_PATH=$AZ_BATCH_NODE_SHARED_DIR:$LD_LIBRARY_PATH
export PATH=./:$PATH

fdsvars=$(find $AZ_BATCH_NODE_SHARED_DIR -name FDS6VARS.sh)
source $fdsvars
#source $AZ_BATCH_NODE_SHARED_DIR/FDS/FDS6/bin/FDS6VARS.sh
#export I_MPI_FABRICS=tcp  #no rdma so using tcp here...
export I_MPI_FABRICS=shm:dapl  #  using rdma here...
export I_MPI_DAPL_PROVIDER=ofa-v2-ib0
export I_MPI_DYNAMIC_CONNECTION=0
export I_MPI_PIN_DOMAIN=omp
export FDSNETWORK=infiniband
export OMP_NUM_THREADS=$INPUTOPENMP

cd $AZ_BATCH_TASK_SHARED_DIR
cd share
cp -p $AZ_BATCH_NODE_SHARED_DIR/* .

mpivars=$(find /opt/intel -name mpivars.sh)
source $mpivars
export MPI_ROOT=$I_MPI_ROOT

# circular 8 meshes
# openMP 4
# h16r 16 cores
# 8*4 = sum of cores = 32
# 32 / (number cores per machine - corefactor) * node = ppn


mpirun -hosts $AZ_BATCH_HOST_LIST -np $MESH fds $PROJECT_NAME
#mpiexec -hosts $AZ_BATCH_HOST_LIST -np $MESH fds $PROJECT_NAME 

zip fds_results.zip ${SHORT_NAME}* ../stderr.txt ../stdout.txt
cp fds_results.zip ../wd/
