from setuptools import setup
setup(name='autofr',
    version=1.0,
    description='AutoFR: Automated Filter Rule Generation for Adblocking',
    author='Hieu Le',
    author_email='hieul@uci.edu',
    url='https://github.com/UCI-Networking-Group/AutoFR',
    packages=['autofr'],
    python_requires='>=3.6',
    install_requires=[
        'tldextract',
        'networkx',
        'adblockparser',
        'pandas',
        'requests',
        'numpy',
        'selenium'
    ]
)
