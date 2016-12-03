from setuptools import setup

APP = ['py_cocoa.py']
DATA_FILES = ['CocoaWindow.xib']
OPTIONS = {}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
