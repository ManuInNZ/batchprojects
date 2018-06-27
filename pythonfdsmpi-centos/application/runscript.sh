#!/usr/bin/bash

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
export MPI_PROCESSORS=$3
export INPUTOPENMP=$4
export SHORT_NAME=${PROJECT_NAME::-4}
export USE_RDMA=$5
export NUM_NODES=$6
export PROCS_PER_NODE=$7
echo "# full line"
echo $0 $1 $2 $3 $4 $5 $6 $7
echo "# input file: $INPUT_FILE"
echo "# project: $PROJECT_NAME $SHORT_NAME"
echo "# number of MPI_PROCESSORSes:" $MPI_PROCESSORS
echo "# number of openMP:" $INPUTOPENMP
echo "use RDMA (1=True / 0=False):" $USE_RDMA
echo "nodes list(AZ_BATCH_HOST_LIST): $AZ_BATCH_HOST_LIST"
echo "number of nodes: $NUM_NODES and process per nodes: $PROCS_PER_NODE"
echo "#### cpuinfo ##################################################################################################################################"
cat /proc/cpuinfo | grep 'model name' && cat /proc/cpuinfo | grep processor && cat /proc/cpuinfo | grep 'core id'   
echo "#### inxi ##################################################################################################################################"
inxi -F -c 1
echo "###############################################################################################################################################"

#export LD_LIBRARY_PATH=$AZ_BATCH_NODE_SHARED_DIR:$LD_LIBRARY_PATH
export PATH=./:$PATH

fdsvars=$(find $AZ_BATCH_NODE_SHARED_DIR -name FDS6VARS.sh)
source $fdsvars
export I_MPI_FABRICS=tcp  #no rdma so using tcp here...
echo "fdsvars $fdsvars"
ulimit -s unlimited
cd $AZ_BATCH_TASK_SHARED_DIR
cd share
cp -p $AZ_BATCH_NODE_SHARED_DIR/* .
ls -lh


if [ $USE_RDMA -eq 1 ]
then
    mpivars=$(find /opt/intel -name mpivars.sh)
    source $mpivars
    export I_MPI_FABRICS=shm:dapl  #  using rdma here...
    export I_MPI_DAPL_PROVIDER=ofa-v2-ib0
    export I_MPI_DYNAMIC_CONNECTION=0
    export I_MPI_PIN_DOMAIN=omp
    export FDSNETWORK=infiniband
    export MPI_ROOT=$I_MPI_ROOT
    export OMP_NUM_THREADS=$INPUTOPENMP
    echo "#### env ##################################################################################################################################"
    env
    echo "#### set ##################################################################################################################################"
    set
    echo "###########################################################################################################################################"
    echo "Executing mpirun"
    if [ $PROCS_PER_NODE -eq 0 ]
    then
        echo "mpirun -hosts $AZ_BATCH_HOST_LIST -np $MPI_PROCESSORS fds $PROJECT_NAME"
    else
        echo "mpirun -hosts $AZ_BATCH_HOST_LIST -np $MPI_PROCESSORS -ppn $PROCS_PER_NODE fds $PROJECT_NAME"
    fi
    date
    if [ $PROCS_PER_NODE -eq 0 ]
    then
        mpirun -hosts $AZ_BATCH_HOST_LIST -np $MPI_PROCESSORS fds $PROJECT_NAME
    else
        mpirun -hosts $AZ_BATCH_HOST_LIST -np $MPI_PROCESSORS -ppn $PROCS_PER_NODE fds $PROJECT_NAME
    fi
    echo "done"
    date
else
    export OMP_NUM_THREADS=$INPUTOPENMP
    export I_MPI_PIN_DOMAIN=omp
    # HOSTS_LIST=$(echo $AZ_BATCH_HOST_LIST|sed 's/,/ /g')
    echo "#### env ##################################################################################################################################"
    env
    echo "#### set ##################################################################################################################################"
    set
    echo "###########################################################################################################################################"
    echo "Executing mpiexec"
    if [ $PROCS_PER_NODE -eq 0 ]
    then
        echo "mpiexec -hosts $AZ_BATCH_HOST_LIST -np $MPI_PROCESSORS fds $PROJECT_NAME "
    else 
        echo "mpiexec -hosts $AZ_BATCH_HOST_LIST -np $MPI_PROCESSORS -ppn $PROCS_PER_NODE fds $PROJECT_NAME "
    fi
    date
    if [ $PROCS_PER_NODE -eq 0 ]
    then
        mpiexec -hosts $AZ_BATCH_HOST_LIST -np $MPI_PROCESSORS fds $PROJECT_NAME 
    else 
        mpiexec -hosts $AZ_BATCH_HOST_LIST -np $MPI_PROCESSORS -ppn $PROCS_PER_NODE fds $PROJECT_NAME 
    fi
    echo "done"
    date
fi

zip fds_results.zip * ../stderr.txt ../stdout.txt
zip $SHORT_NAME\.out.zip *.out
cp *.zip ../wd/
cp *.out ../wd/$SHORT_NAME\.out
cp ../stderr.txt ../wd/
cp ../stdout.txt ../wd/
