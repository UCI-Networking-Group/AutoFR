FROM debian:buster

ARG USER_ID
ARG GROUP_ID
ARG FOR_MAC
ARG FOR_MAC_M1

RUN apt-get update \
    && apt-get install -y python3 python3-dev gfortran libatlas-base-dev python3-pip xvfb chromium chromium-driver git fonts-noto fonts-dejavu fonts-freefont-ttf curl libhdf5-dev libnetcdf-dev

RUN curl -sL deb.nodesource.com/setup_13.x | bash -
RUN apt-get install -y nodejs
RUN node -v

RUN if [ -z "$FOR_MAC" ]; then addgroup --gid $GROUP_ID user ; fi
RUN adduser --disabled-password --gecos '' --uid $USER_ID --gid $GROUP_ID user

USER root
RUN chown -R user /usr/local/lib/

USER user
WORKDIR /home/user
RUN pip3 install --user setuptools flask selenium pyvirtualdisplay numpy pandas networkx adblockparser
RUN pip3 install --user --upgrade requests

# build adblock plus, use 3.10.1 version (Dec 14, 2020)
COPY framework-with-ad-highlighter/include.preload.js framework-with-ad-highlighter/contentFiltering.js framework-with-ad-highlighter/hitLogger.js framework-with-ad-highlighter/subscriptions.json ./

USER root
RUN if [ ! -z "$FOR_MAC" ]; then apt-get install -y pkg-config libpixman-1-dev libcairo2-dev libpango1.0-dev libjpeg62-turbo-dev libgif-dev librsvg2-dev libhdf5-dev libnetcdf-dev libblas-dev liblapack-dev libatlas-base-dev gfortran ; fi

USER user
WORKDIR /home/user
RUN git clone https://github.com/adblockplus/adblockpluschrome.git
RUN cd adblockpluschrome && git checkout 9652cf0afb330f242516d2e3c10b755780abf3cc \
    && git submodule update --init --recursive \
    && npm install --force \
    && mv ../include.preload.js . \
    && mv ../contentFiltering.js lib/. \
    && mv ../hitLogger.js lib/. \
    && mv ../subscriptions.json adblockpluscore/data/. \
    && npx gulp devenv -t chrome

# copy over the adb_proxy and get latest easylist
COPY framework-with-ad-highlighter/abp_proxy abp_proxy
USER root
RUN chown -R user abp_proxy
USER user
RUN cd abp_proxy \
    && python3 -c '__import__("urllib.request").request.urlretrieve("https://easylist-downloads.adblockplus.org/easylist.txt", "easylist.txt")'

USER user
# copy in ad-highlighter (this is already built)
COPY ad_highlighter/perceptual-adblocker perceptual-adblocker/

# copy agents
COPY framework-with-ad-highlighter/*agent*.py framework-with-ad-highlighter/entrypoint*.sh ./
COPY *agent*.csv ./
COPY framework-with-ad-highlighter/patch*.py ./

# misc
USER root
ENV IS_INSIDE_DOCKER True
RUN chown user /usr/bin/chromedriver

# add in common code for autofr and install it
USER user
COPY autofr autofr/
COPY setup.py ./
RUN python3 setup.py develop --user

USER root
CMD timeout 10m bash entrypoint.sh
