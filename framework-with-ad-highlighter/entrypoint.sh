#!/bin/bash

set -e

PATCH_CHROME_DRIVER=${PATCH_CHROME_DRIVER:-patch_chrome_driver.py}
FLG_AGENT=${FLG_AGENT:-agent_new.py}
OUTPUT_PATH=${OUTPUT_PATH:-/data/output}
URL=${URL:-https://www.cnn.com/}
ADBLOCK_EXT_PATH=${ADBLOCK_EXT_PATH:-/home/user/adblockpluschrome/devenv.chrome}
AD_HIGHLIGHTER_EXT_PATH=${AD_HIGHLIGHTER_EXT_PATH:-/home/user/perceptual-adblocker/}
ADBLOCK_PROXY_PATH=${ADBLOCK_PROXY_PATH:-/home/user/abp_proxy/}
AGENT_NAME=${AGENT_NAME:-experiment}
WAIT_TIME=${WAIT_TIME:-45}
DO_INITIAL_STATE_ONLY=${DO_INITIAL_STATE_ONLY:-False}
INIT_STATE_ITERATIONS=${INIT_STATE_ITERATIONS:-4}
CREATE_AGENT_NAME=${CREATE_AGENT_NAME:-False}
BLOCK_ITEMS_FILE_PATH=${BLOCK_ITEMS_FILE_PATH:-}
SAVE_DISSIMILAR_HASHES=${SAVE_DISSIMILAR_HASHES:-False}

mkdir -p "${OUTPUT_PATH}"
chown user:users "${OUTPUT_PATH}"

# make temporary profile
#tmp_proile_dir=$(mktemp -d)
#if [ -z "$tmp_profile_dir" ]; then echo "var is blank"; else echo "var is set to '$tmp_profile_dir'"; fi
#echo "made temp directory ${tmp_profile_dir}"

# start proxy for adblock plus
cd ${ADBLOCK_PROXY_PATH}
su user -c "python3 subscription_proxy.py &"

echo "Starting agent"
cd /home/user

# patch chrome driver
su user -c "python3 ${PATCH_CHROME_DRIVER}"

# start agent

if [ "${CREATE_AGENT_NAME}" == "True" ]; then
    RANDOM_STR=`echo $RANDOM"-"$RANDOM`
    FULL_AGENT_NAME="${FLG_AGENT}_${AGENT_NAME}_${RANDOM_STR}"
fi

BLOCK_ITEMS_FILE_PATH_PARAM=""
if [ "${BLOCK_ITEMS_FILE_PATH}" != "" ]; then
  BLOCK_ITEMS_FILE_PATH_PARAM="--block_items_path ${BLOCK_ITEMS_FILE_PATH}"
fi

su user -c "python3 ${FLG_AGENT} --save_dissimilar_hashes ${SAVE_DISSIMILAR_HASHES} ${BLOCK_ITEMS_FILE_PATH_PARAM} --agent_name ${FULL_AGENT_NAME} --adblock_proxy_path ${ADBLOCK_PROXY_PATH} --downloads_path ${OUTPUT_PATH} --url \"${URL}\" --adblock_ext_path ${ADBLOCK_EXT_PATH} --ad_highlighter_ext_path ${AD_HIGHLIGHTER_EXT_PATH} --wait_time ${WAIT_TIME} --do_initial_state_only ${DO_INITIAL_STATE_ONLY} --init_state_iterations ${INIT_STATE_ITERATIONS}"


echo "DONE"
