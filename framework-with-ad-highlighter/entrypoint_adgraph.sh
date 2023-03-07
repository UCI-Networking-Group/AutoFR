#!/bin/bash

set -e

PATCH_CHROME_DRIVER=${PATCH_CHROME_DRIVER:-patch_chrome_driver.py}
FLG_AGENT=${FLG_AGENT:-agent_adgraph.py}
OUTPUT_PATH=${OUTPUT_PATH:-/data/output}
URL=${URL:-https://www.cnn.com/}
AD_HIGHLIGHTER_EXT_PATH=${AD_HIGHLIGHTER_EXT_PATH:-/home/user/perceptual-adblocker/}
AGENT_NAME=${AGENT_NAME:-experiment}
WAIT_TIME=${WAIT_TIME:-45}
INIT_STATE_ITERATIONS=${INIT_STATE_ITERATIONS:-4}
CREATE_AGENT_NAME=${CREATE_AGENT_NAME:-False}
CHROME_DRIVER_PATH=${CHROME_DRIVER_PATH:-/home/user/chromedriver}
BROWSER_PATH=${BROWSER_PATH:-/home/user/AdGraph/chrome}
BLOCK_ITEMS_FILE_PATH=${BLOCK_ITEMS_FILE_PATH:-}
DISABLE_ISOLATION=${DISABLE_ISOLATION:-True}
IS_NEW_ADGRAPH=${IS_NEW_ADGRAPH:-True}

mkdir -p "${OUTPUT_PATH}"
chown user:users "${OUTPUT_PATH}"

echo "Starting agent"
cd /home/user

# patch chrome driver
#echo "Patching Chromium Driver"
#su user -c "python3 ${PATCH_CHROME_DRIVER}"
echo "Patching AdGraph Chrome Driver"
su user -c "python3 ${PATCH_CHROME_DRIVER} --chrome_driver_path ${CHROME_DRIVER_PATH}"

# start agent
if [ "${CREATE_AGENT_NAME}" == "True" ]; then
    RANDOM_STR=`echo $RANDOM"-"$RANDOM`
    FULL_AGENT_NAME="${FLG_AGENT}_${AGENT_NAME}_${RANDOM_STR}"
fi

BLOCK_ITEMS_FILE_PATH_PARAM=""
if [ "${BLOCK_ITEMS_FILE_PATH}" != "" ]; then
  BLOCK_ITEMS_FILE_PATH_PARAM="--block_items_path ${BLOCK_ITEMS_FILE_PATH}"
fi

ADGRAPH_VERSION=""
if [ "${IS_NEW_ADGRAPH}" == "True" ]; then
  ADGRAPH_VERSION="--adgraph_version flg-ad-highlighter-adgraph-new"
else
  ADGRAPH_VERSION="--adgraph_version flg-ad-highlighter-adgraph"
fi

echo "doing regular agent with no agent stats"
su user -c "python3 ${FLG_AGENT} ${BLOCK_ITEMS_FILE_PATH_PARAM} ${ADGRAPH_VERSION} --browser_path ${BROWSER_PATH} --chrome_driver_path ${CHROME_DRIVER_PATH} --agent_name ${FULL_AGENT_NAME} --downloads_path ${OUTPUT_PATH} --url \"${URL}\" --ad_highlighter_ext_path ${AD_HIGHLIGHTER_EXT_PATH} --wait_time ${WAIT_TIME} --init_state_iterations ${INIT_STATE_ITERATIONS} --disable_isolation ${DISABLE_ISOLATION}"

echo "DONE"
