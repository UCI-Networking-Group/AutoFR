from flask import Flask,request,redirect,Response
import requests
app = Flask(__name__)
SITE_NAME = 'https://easylist-downloads.adblockplus.org/'
excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']

# To get the frozen filter lists, use :
# https://easylist-downloads.adblockplus.org/easylist.txt?addonName=adblockpluschrome&addonVersion=3.7&application=chrome&applicationVersion=78&platform=chromium&platformVersion=78&lastVersion=0&downloadCount=0

@app.route('/')
def index():
    return 'Flask is running!'


@app.route('/<path:path>',methods=['GET'])
def proxy(path):
    global SITE_NAME
    if request.method=='GET':
        print("proxing filter rules")
        url = f'{SITE_NAME}{path}'
        print(url)
        resp = requests.get(url)

        # we force the content from the file
        content = None
        if "easylist" in path:
            # for RL, we should not need this yet
            print("reading content from local EMPTY easylist.txt")
            content = open('easylist-empty.txt', 'r').read()
        elif "anti-cv" in path:
            print("reading content from local abp-filters-anti-cv.txt (RL)")
            content = open('abp-filters-anti-cv.txt', 'r').read()

        #print(content)

        headers = [(name, value) for (name, value) in  resp.raw.headers.items() if name.lower() not in excluded_headers]
        response = Response(content, resp.status_code, headers)
        return response


if __name__ == '__main__':
    app.run(debug=False, port=5000)
