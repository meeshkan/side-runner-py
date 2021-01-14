from dpath.util import merge
from selenium import webdriver
from selenium.webdriver.common.proxy import Proxy, ProxyType
from .config import Config
from .utils import maybe_bool, construct_dict


def initialize(driver_url):
    if len(Config.DESIRED_CAPABILITIES) == 0:
        chrome_options = webdriver.ChromeOptions()

        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1280x1696')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--hide-scrollbars')
        chrome_options.add_argument('--enable-logging')
        chrome_options.add_argument('--log-level=0')
        chrome_options.add_argument('--v=99')
        chrome_options.add_argument('--single-process')
        chrome_options.add_argument('--ignore-certificate-errors')

        chrome_options.binary_location = "/tmp/bin/headless-chromium"        # options.add_experimental_option('prefs', {'intl.accept_languages': 'ja_JP'})
        cap = chrome_options.to_capabilities()
    else:
        cap = {}
        for k, v in [cap.split("=") for cap in Config.DESIRED_CAPABILITIES]:
            k = k.strip("\"'")
            v = maybe_bool(v.strip("\"'"))
            merge(cap, construct_dict(k, v))

    if Config.HTTP_PROXY or Config.HTTPS_PROXY or Config.NO_PROXY:
        proxy = Proxy()
        proxy.sslProxy = Config.HTTPS_PROXY
        proxy.httpProxy = Config.HTTP_PROXY
        proxy.noProxy = Config.NO_PROXY
        proxy.proxyType = ProxyType.MANUAL
        proxy.add_to_capabilities(cap)

    # driver = webdriver.Remote(
    #     command_executor=driver_url,
    #     desired_capabilities=cap)
    chrome_options = webdriver.ChromeOptions()

    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1280x1696')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--hide-scrollbars')
    chrome_options.add_argument('--enable-logging')
    chrome_options.add_argument('--log-level=0')
    chrome_options.add_argument('--v=99')
    chrome_options.add_argument('--single-process')
    chrome_options.add_argument('--ignore-certificate-errors')

    chrome_options.binary_location = "/tmp/bin/headless-chromium"        # options.add_experimental_option('prefs', {'intl.accept_languages': 'ja_JP'})
    driver = webdriver.Chrome("/tmp/bin/chromedriver", chrome_options=chrome_options)

    return driver
