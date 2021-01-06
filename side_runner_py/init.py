from dpath.util import merge
from selenium import webdriver
from selenium.webdriver.common.proxy import Proxy, ProxyType
from .config import Config
from .utils import maybe_bool, construct_dict


def initialize(driver_url):
    if len(Config.DESIRED_CAPABILITIES) == 0:
        options = webdriver.ChromeOptions()
        #options.add_experimental_option('prefs', {'intl.accept_languages': 'ja_JP'})
        cap = options.to_capabilities()
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

    driver = webdriver.Chrome(desired_capabilities=cap)
    # meeshkan_session_id=ed99a7ce-30c5-4055-b620-09832362b0f3
    # lang=ru
    # ajs_group_id=null
    # ajs_anonymous_id=%2236226d82-a849-4869-b56b-6d67582141da%22;
    # _ga=GA1.2.906997567.1608193843;
    # _gcl_au=1.1.1138804193.1608193843;
    # gdpr-user=true;
    # _mkto_trk=id:594-ATC-127&token:_mch-trello.com-1608193844433-79887;
    # gdpr-cookie-consent=accepted;
    # tss=1;
    # mab=5e67510c278e490cf7596fa4;
    # G_ENABLED_IDPS=google;
    # token=5e67510c278e490cf7596fa4%2Fmzf3Jy7qAXcxhAsjvhcih2bovmiAQgYSeymIEW8kyVT19fTC9tY1qCV9uDgABpTZ;
    # hasAccount=atlassian;
    # __cid=d90b36b9-65ae-485b-a8f6-6fcbfb673f4c-fd64d77fa040cfab7d44cfab7d44cfab7d44cf;
    # _gid=GA1.2.986579580.1609749157;
    # dsc=947c5c76210f10a705bd42eb9b15bdbe022ef0a14c9748680baa6c474cb7036d


    return driver
