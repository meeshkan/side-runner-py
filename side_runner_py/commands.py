import re
import time

from selenium.common.exceptions import NoAlertPresentException, ElementNotVisibleException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait

from .config import Config
from .exceptions import AssertionFailure, VerificationFailure
from .log import getLogger
from .utils import split_with_re

logger = getLogger(__name__)


def parse_cookes(cookies):
    res = []
    for cookie in cookies.split(";"):
        name, value = cookie.split("=")
        res.append({"name": name.strip(), "value": value.strip()})

    return res


def add_cookes(driver, cookies):
    if cookies is not None:
        cookies = parse_cookes(cookies)
        cookie_names = {cookie["name"] for cookie in cookies}
        old_cookies = driver.get_cookies()
        for cookie in old_cookies:
            if cookie["name"] in cookie_names:
                driver.delete_cookie(cookie["name"])

        for cookie in cookies:
            driver.add_cookie(cookie)


def execute_open(driver, store, test_project, test_suite, test_dict):
    # get url
    # FIXME: url try order impl (environment -> ttest[open].target -> test_suite.url -> test_project.url)
    base_url = test_project.get('url')
    driver.get(base_url)
    add_cookes(driver, test_project.get("cookies"))
    # driver.add_cookie({"name": "user_id", "value": "111796339919137618571"})
    driver.get(base_url)

    # driver.get(base_url + test_dict['target'])


def execute_set_window_size(driver, store, test_project, test_suite, test_dict):
    w, h = test_dict['target'].split('x')
    driver.set_window_size(w, h)


def execute_set_viewport_size(driver, store, test_project, test_suite, test_dict):
    w, h = test_dict['target'].split('x')

    w, h = driver.execute_script("""
        return [window.outerWidth - window.innerWidth + arguments[0],
          window.outerHeight - window.innerHeight + arguments[1]];
        """, w, h)
    driver.set_window_size(w, h)


def execute_execute_script(driver, store, test_project, test_suite, test_dict):
    result = driver.execute_script(test_dict['target'])
    if test_dict.get('value'):
        store[test_dict['value']] = result


def execute_run_script(driver, store, test_project, test_suite, test_dict):
    driver.execute_script(test_dict['target'])


# By.CLASS_NAME         By.ID                 By.NAME               By.TAG_NAME           By.mro(
# By.CSS_SELECTOR       By.LINK_TEXT          By.PARTIAL_LINK_TEXT  By.XPATH
def _get_element_selector_tuple(target_text):
    # FIXME: impl other selector
    text = target_text.split('=', 1)[1]
    if target_text.startswith('id='):
        return (By.ID, text)
    if target_text.startswith('xpath='):
        return (By.XPATH, text)
    if target_text.startswith('linkText='):
        return (By.LINK_TEXT, text)
    if target_text.startswith('css='):
        return (By.CSS_SELECTOR, text)
    if target_text.startswith('name='):
        return (By.NAME, text)


def _wait_element(driver, target_text):
    selector = _get_element_selector_tuple(target_text)
    logger.debug("click selector:", selector)
    condition = expected_conditions.presence_of_element_located(selector)
    element = WebDriverWait(driver, Config.DRIVER_ELEMENT_WAIT).until(condition)
    return element


def execute_click(driver, store, test_project, test_suite, test_dict):
    logger.debug("CLICK:", test_dict)
    element = _wait_element(driver, test_dict['target'])
    ActionChains(driver).click(element).perform()
    logger.debug("element:", element)


def execute_click_at(driver, store, test_project, test_suite, test_dict):
    logger.debug("CLICK AT:", test_dict)
    try:
        offsetx, offsety = ([int(s.strip()) for s in test_dict['value'].split(',')])
    except Exception:
        raise Exception('execute_click_at: illegal coord string: {}'.format(test_dict['value']))
    element = _wait_element(driver, test_dict['target'])
    ActionChains(driver).move_to_element_with_offset(element, offsetx, offsety).click(None).perform()
    logger.debug("element:", element)


def execute_double_click(driver, store, test_project, test_suite, test_dict):
    logger.debug("DOUBLE CLICK:", test_dict)
    element = _wait_element(driver, test_dict['target'])
    ActionChains(driver).double_click(element).perform()
    logger.debug("element:", element)


def execute_type(driver, store, test_project, test_suite, test_dict):
    logger.debug("TYPE:", test_dict)
    element = _wait_element(driver, test_dict['target'])

    # check target input element is or not date type
    # NOTE: send_keys on date-input is corrupted on webdriver (maybe)
    if element.get_attribute("type") == "date":
        (_, element_id) = _get_element_selector_tuple(test_dict['target'])
        script = "document.getElementById('{}').value = '{}';".format(element_id, test_dict['value'])
        driver.execute_script(script)
        return

    element.clear()
    ActionChains(driver).click(element).send_keys_to_element(element, test_dict['value']).perform()

    # NOTE: NOT worked on GeckoDriver
    # element.clear()
    # element.send_keys(test_dict['value'])

    # NOTE: NOT worked on ChromeDriver 83.0.4103.39
    # element.clear()
    # ActionChains(driver).send_keys_to_element(element, test_dict['value']).perform()


def execute_pause(driver, store, test_project, test_suite, test_dict):
    logger.debug("PAUSE:", test_dict['target'], "[ms]")
    time.sleep(float(test_dict['target']) / 1000)


def execute_send_keys(driver, store, test_project, test_suite, test_dict):
    logger.debug("SEND KEYS:", test_dict)
    element = _wait_element(driver, test_dict['target'])

    def to_keys(m):
        return getattr(Keys, m.group(1), m.group(1))

    regexp = re.compile('\\${KEY_([A-Z0-9]+)}')
    keys = split_with_re(regexp, test_dict['value'], to_keys)

    ActionChains(driver).send_keys_to_element(element, *keys).perform()


def execute_mouse_over(driver, store, test_project, test_suite, test_dict):
    pass


def execute_mouse_down_at(driver, store, test_project, test_suite, test_dict):
    pass


def execute_mouse_up_at(driver, store, test_project, test_suite, test_dict):
    pass


def execute_dragndrop(driver, store, test_project, test_suite, test_dict):
    action_chain = ActionChains(driver)
    element = _wait_element(driver, test_dict['source_target'])

    move_x = test_dict["dest_coordinates"][0] - test_dict["source_coordinates"][0]
    move_y = test_dict["dest_coordinates"][1] - test_dict["source_coordinates"][1]

    #action_chain.move_by_offset(test_dict["source_coordinates"][0], test_dict["source_coordinates"][1])

    action_chain.move_to_element(element)#test_dict["source_coordinates"][0], test_dict["source_coordinates"][1])\
    action_chain.click_and_hold()
    action_chain.move_by_offset(move_x, move_y)
    action_chain.pause(2)
    action_chain.release()
    action_chain.pause(2)
    #action_chain.drag_and_drop_by_offset(element, move_x, move_y)
    action_chain.perform()


def execute_mouse_move_at(driver, store, test_project, test_suite, test_dict):
    element = _wait_element(driver, test_dict['target'])
    ActionChains(driver).move_to_element(element).perform()


def _select_by_selector(select, selector):
    text = selector.split('=', 1)[1]
    if selector.startswith('label='):
        return select.select_by_visible_text(text)


def execute_select(driver, store, test_project, test_suite, test_dict):
    element = _wait_element(driver, test_dict['target'])
    _select_by_selector(Select(element), test_dict['value'])


def execute_wait_for_element_present(driver, store, test_project, test_suite, test_dict):
    selector = _get_element_selector_tuple(test_dict['target'])
    timeout_ms = int(test_dict['value'])
    WebDriverWait(driver, timeout_ms / 1000, 1, (NoSuchElementException)) \
        .until(lambda x: x.find_element(*selector))


def execute_wait_for_element_visible(driver, store, test_project, test_suite, test_dict):
    selector = _get_element_selector_tuple(test_dict['target'])
    timeout_ms = int(test_dict['value'])
    WebDriverWait(driver, timeout_ms / 1000, 1, (ElementNotVisibleException, NoSuchElementException)) \
        .until(lambda x: x.find_element(*selector).is_displayed())


def execute_wait_for_element_not_present(driver, store, test_project, test_suite, test_dict):
    selector = _get_element_selector_tuple(test_dict['target'])
    timeout_ms = int(test_dict['value'])
    WebDriverWait(driver, timeout_ms / 1000, 1, (NoSuchElementException)) \
        .until_not(lambda x: x.find_element(*selector))


def execute_wait_for_element_not_visible(driver, store, test_project, test_suite, test_dict):
    selector = _get_element_selector_tuple(test_dict['target'])
    timeout_ms = int(test_dict['value'])
    WebDriverWait(driver, timeout_ms / 1000, 1, (ElementNotVisibleException, NoSuchElementException)) \
        .until_not(lambda x: x.find_element(*selector).is_displayed())


def execute_assert_confirmation(driver, store, test_project, test_suite, test_dict):
    expect = test_dict['target']
    elapsed_seconds = 0

    while True:
        try:
            actual = Alert(driver).text
            if expect in actual:
                return True
            else:
                raise AssertionFailure('execute_assert_confirmation', 'confirmation', expect, actual)
        except NoAlertPresentException:
            # FIXME: make configurable
            time.sleep(1)
            elapsed_seconds += 1
            if elapsed_seconds > Config.DRIVER_ELEMENT_WAIT:
                raise AssertionFailure('execute_assert_confirmation', 'confirmation', expect, '<timed out>')
            else:
                continue


def execute_webdriver_choose_ok_on_visible_confirmation(driver, store, test_project, test_suite, test_dict):
    Alert(driver).accept()


def execute_assert_text(driver, store, test_project, test_suite, test_dict):
    element = _wait_element(driver, test_dict['target'])
    expect = test_dict['value']
    actual = element.text
    logger.info('ASSERT TEXT: expected {}, actual {}'.format(expect, actual))
    if expect != actual:
        raise AssertionFailure('execute_assert_text', test_dict['target'], expect, actual)


def execute_verify_text(driver, store, test_project, test_suite, test_dict):
    expect = test_dict['value']
    element = _wait_element(driver, test_dict['target'])
    actual = element.text
    logger.info('VERIFY TEXT: expected {}, actual {}'.format(test_dict['value'], element.text))
    if expect != actual:
        raise VerificationFailure('execute_verify_text', test_dict['target'], expect, actual)


def execute_assert(driver, store, test_project, test_suite, test_dict):
    expect = test_dict['value']
    actual = store.get(test_dict['target'])
    logger.info('ASSERT: expected {}, actual {}'.format(expect, actual))
    if expect != actual:
        raise AssertionFailure('execute_assert', test_dict['target'], expect, actual)


def execute_verify(driver, store, test_project, test_suite, test_dict):
    expect = test_dict['value']
    actual = store.get(test_dict['target'])
    logger.info('VERIFY: expected {}, actual {}'.format(expect, actual))
    if expect != actual:
        raise VerificationFailure('execute_verify', test_dict['target'], expect, actual)


def execute_store(driver, store, test_project, test_suite, test_dict):
    store[test_dict['value']] = test_dict['target']


def execute_store_text(driver, store, test_project, test_suite, test_dict):
    element = _wait_element(driver, test_dict['target'])
    store[test_dict['value']] = element.text


def execute_store_attribute(driver, store, test_project, test_suite, test_dict):
    locator, attribute = test_dict['target'].rsplit('@', 1)
    element = _wait_element(driver, locator)
    store[test_dict['value']] = element.get_attribute(attribute)


def execute_store_value(driver, store, test_project, test_suite, test_dict):
    # NOTE: This works for any input type element
    element = _wait_element(driver, test_dict['target'])
    store[test_dict['value']] = element.get_attribute('value')


TEST_HANDLER_MAP = {
    'open': execute_open,
    'setWindowSize': execute_set_window_size,
    'setViewportSize': execute_set_viewport_size,
    'executeScript': execute_execute_script,
    'runScript': execute_run_script,
    'click': execute_click,
    'clickAt': execute_click_at,
    'doubleClick': execute_double_click,
    'type': execute_type,
    'pause': execute_pause,
    'sendKeys': execute_send_keys,
    'assertText': execute_assert_text,
    'verifyText': execute_verify_text,
    'mouseOver': execute_mouse_over,
    'select': execute_select,
    'mouseDownAt': execute_mouse_down_at,  # lambda _1, _2, _3, _4, _5: None,
    'mouseUpAt': execute_mouse_move_at,  # lambda _1, _2, _3, _4, _5: None,
    'mouseMoveAt': execute_mouse_up_at,  # lambda _1, _2, _3, _4, _5: None,
    'dragndrop': execute_dragndrop,
    'chooseOkOnNextConfirmation': lambda _1, _2, _3, _4, _5: None,
    'chooseCancelOnNextConfirmation': lambda _1, _2, _3, _4, _5: None,
    'waitForElementPresent': execute_wait_for_element_present,
    'waitForElementVisible': execute_wait_for_element_visible,
    'waitForElementNotPresent': execute_wait_for_element_not_present,
    'waitForElementNotVisible': execute_wait_for_element_not_visible,
    'assertConfirmation': execute_assert_confirmation,
    'webdriverChooseOkOnVisibleConfirmation': execute_webdriver_choose_ok_on_visible_confirmation,
    'assert': execute_assert,
    'verify': execute_verify,
    'store': execute_store,
    'storeText': execute_store_text,
    'storeAttribute': execute_store_attribute,
    'storeValue': execute_store_value,
}
