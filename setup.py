from setuptools import setup

APP = ['py_cocoa.py']
APP_NAME = "Facebook to CSV"
DATA_FILES = ['CocoaWindow.xib']
OPTIONS = {
    'iconfile': 'csv.icns',
    'argv_emulation': True,
    'plist': {
        'CFBundleName': APP_NAME,
        'CFBundleDisplayName': APP_NAME,
        'CFBundleGetInfoString': "Facebook to CSV scraper",
        'CFBundleIdentifier': "com.alex.osx.fbscrape",
        'CFBundleVersion': "0.1.1",
        'CFBundleShortVersionString': "0.1.2",
    },
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
